import { app, BrowserWindow, Menu, WebContentsView, clipboard, dialog, ipcMain, session, shell } from 'electron';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { TabManager, LAUNCHPAD, GROUP_COLORS, ID_PATTERN } from './tab_manager.js';
import { ASKABLE, Bookmarks, History, JsonFile, PermissionDecisions, originOf } from './stores.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Securely load .env into process.env if COMEX_INTERNAL_APP_TOKEN is not already set
function loadEnvFile() {
  if (process.env.COMEX_INTERNAL_APP_TOKEN) return;
  try {
    const envPath = path.join(__dirname, '../.env');
    if (fs.existsSync(envPath)) {
      const content = fs.readFileSync(envPath, 'utf8');
      for (const line of content.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const eqIdx = trimmed.indexOf('=');
        if (eqIdx !== -1) {
          const key = trimmed.slice(0, eqIdx).trim();
          const val = trimmed.slice(eqIdx + 1).trim();
          if (!process.env[key]) {
            process.env[key] = val;
          }
        }
      }
    }
  } catch (err) {
    console.warn('[SECURITY] Could not read .env file in main process:', err.message);
  }
}
loadEnvFile();

const internalAppToken = process.env.COMEX_INTERNAL_APP_TOKEN || null;
if (!internalAppToken) {
  console.warn('[SECURITY] COMEX_INTERNAL_APP_TOKEN is not configured! Main-process proxy will fail closed.');
}

// Where the agent service and the interface are. Defaults are the normal app; an isolated test instance overrides them.
const AGENT_URL = (process.env.COMEX_AGENT_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const RENDERER_URL = process.env.COMEX_RENDERER_URL || 'http://localhost:5173';
const DEBUG_SYNC = process.env.COMEX_DEBUG_SYNC === '1';
const IS_MAC = process.platform === 'darwin';

function isAuthorizedSender(event) {
  if (!mainWindow || mainWindow.isDestroyed()) return false;
  if (!event || !event.senderFrame || event.senderFrame !== mainWindow.webContents.mainFrame) {
    console.warn('[SECURITY] Privileged IPC invocation rejected: unauthorized sender frame');
    return false;
  }
  return true;
}

const INTERNAL_URLS = new Set([LAUNCHPAD, 'nexus://launchpad', 'about:blank']);
const isInternalUrl = (url) => !url || INTERNAL_URLS.has(url);

function isSafeNavigationUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') return false;
  const url = rawUrl.trim();
  if (INTERNAL_URLS.has(url)) return true;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
    const port = parsed.port ? parseInt(parsed.port, 10) : (parsed.protocol === 'https:' ? 443 : 80);
    const agentPort = (() => { try { return parseInt(new URL(AGENT_URL).port, 10); } catch { return 8000; } })();
    if ([9222, 8000, 20128, agentPort, parseInt(process.env.COMEX_CDP_PORT || '9222', 10)].includes(port)) {
      console.warn(`[SECURITY] Blocked navigation attempt to internal sensitive port ${port}: ${url}`);
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

const isHttpUrl = (url) => typeof url === 'string' && /^https?:\/\//i.test(url);

// Enable Chrome DevTools Protocol so the agent backend can attach to this browser.
// COMEX_CDP_PORT / COMEX_USER_DATA let a second, isolated instance run beside the normal app (benchmarks and tests).
app.commandLine.appendSwitch('remote-debugging-port', process.env.COMEX_CDP_PORT || '9222');
if (process.env.COMEX_USER_DATA) app.setPath('userData', process.env.COMEX_USER_DATA);

let mainWindow;
const isVisualCursorEnabled = process.env.VISUAL_CURSOR_ENABLED !== 'false';
let cursorWindow = null;

function resetVisualCursor() {
  if (cursorWindow && !cursorWindow.isDestroyed()) {
    cursorWindow.webContents.send('cursor-reset');
  }
}

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// State: the TabManager owns tabs and groups (the interface only renders its snapshots). Views are the native pages
// of tabs, created when a tab is first shown or needed by an agent, so restored tabs do not all load at once.
// ─────────────────────────────────────────────────────────────────────────────────────────────────
let manager = null;
let sessionFile, historyFile, bookmarksFile, permissionsFile;
let history, bookmarks, permissions;
const views = new Map(); // tabId -> WebContentsView
let currentBounds = { x: 0, y: 0, width: 0, height: 0, isHidden: true };
let attachedTabId = null;
let adoptingView = null; // a popup's own page, adopted as the next created tab (keeps window.opener)
const closingGroups = new Set();
const closingTabs = new Set();

function initState() {
  const dir = app.getPath('userData');
  sessionFile = new JsonFile(path.join(dir, 'comex-session.json'));
  historyFile = new JsonFile(path.join(dir, 'comex-history.json'), { delayMs: 2000 });
  bookmarksFile = new JsonFile(path.join(dir, 'comex-bookmarks.json'));
  permissionsFile = new JsonFile(path.join(dir, 'comex-permissions.json'));
  history = new History(historyFile.read([]));
  bookmarks = new Bookmarks(bookmarksFile.read(null));
  permissions = new PermissionDecisions(permissionsFile.read({}));
  manager = TabManager.restore(sessionFile.read(null));
  manager.subscribe(onManagerEvent);
  // every restored tab is a member of its group again (the agent backend keeps chat membership)
  for (const id of manager.order) backendJoin(manager.tab(id).groupId, id, manager.tab(id).kind === 'agent' ? 'agent' : 'main');
}

function onManagerEvent(e) {
  if (e.type === 'tab-created') {
    if (adoptingView) {
      registerView(e.tab.id, adoptingView);
      adoptingView = null;
    } else if (!e.tab.discarded) {
      ensureView(e.tab.id);
    }
    backendJoin(e.tab.groupId, e.tab.id, e.tab.kind === 'agent' ? 'agent' : 'link');
  } else if (e.type === 'tab-closed') {
    onTabClosed(e.tab);
  } else if (e.type === 'activated') {
    activationChanged = true;
  } else if (e.type === 'changed') {
    sessionFile.write(manager.serialize());
    scheduleSync();
  }
}

// Changes arrive in bursts (a group closing emits several events); the view and the interface update once per burst.
let syncScheduled = false;
let activationChanged = false;
function scheduleSync() {
  if (syncScheduled) return;
  syncScheduled = true;
  setImmediate(() => {
    syncScheduled = false;
    syncActiveView();
    pushState();
  });
}

function pushState() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.send('browser-state', browserState());
}

function browserState() {
  return { session: manager.snapshot(), bookmarks: bookmarks.toJSON() };
}

// ── backend (the agent service): chat membership and stopping agents. Never blocks the interface. ──

async function backendPost(pathname, body = {}, timeoutMs = 2500) {
  try {
    const resp = await fetch(`${AGENT_URL}${pathname}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(internalAppToken ? { 'X-Comex-Internal-Token': internalAppToken } : {}) },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    return resp.ok ? await resp.json() : null;
  } catch {
    return null; // the agent service may be down; tabs keep working
  }
}

const backendJoin = (groupId, tabId, role) => backendPost('/chat/groups/join', { group_id: groupId, tab_id: tabId, role });

// ── views ─────────────────────────────────────────────────────────────────────────────────────────

function createTabView(webContents) {
  const view = new WebContentsView({
    ...(webContents ? { webContents } : {}),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  // No user-agent override: pages see the real engine (Chromium with the Electron token), as Electron reports it.
  return view;
}

function registerView(tabId, view) {
  views.set(tabId, view);
  attachTabListeners(tabId, view);
}

// A closed view's webContents is undefined (not a destroyed object), so view.webContents.isDestroyed() throws.
function gone(view) {
  return !view || !view.webContents || view.webContents.isDestroyed();
}

function ensureView(tabId) {
  const existing = views.get(tabId);
  if (!gone(existing)) return existing;
  const tab = manager.tab(tabId);
  if (!tab) return null;
  const view = createTabView();
  registerView(tabId, view);
  loadTabUrl(view, tab.error?.url || tab.url);
  manager.updateTab(tabId, { discarded: false });
  return view;
}

function destroyView(tabId) {
  const view = views.get(tabId);
  views.delete(tabId);
  agentOverlays.delete(tabId);
  if (attachedTabId === tabId) attachedTabId = null;
  if (!view) return;
  detachView(view);
  if (!gone(view)) view.webContents.close();
}

function onTabClosed(tab) {
  closingTabs.add(tab.id);
  destroyView(tab.id);
  closingTabs.delete(tab.id);
  if (closingGroups.has(tab.groupId)) return; // the group's close stops its agents and closes its chat in one call
  backendPost(`/agent/tabs/${encodeURIComponent(tab.id)}/stop`);
  backendPost(`/chat/tabs/${encodeURIComponent(tab.id)}/closed`);
}

function getNavState(webContents) {
  const h = webContents.navigationHistory;
  return { canGoBack: h.canGoBack(), canGoForward: h.canGoForward() };
}

function normalizeUrl(url) {
  if (!url || url === 'about:blank') return LAUNCHPAD;
  return url;
}

function detachView(view) {
  if (!mainWindow || mainWindow.isDestroyed() || !view) return;
  try {
    mainWindow.contentView.removeChildView(view);
  } catch {
    // View was not attached.
  }
}

function loadTabUrl(view, url) {
  if (!url || INTERNAL_URLS.has(url)) {
    view.webContents.loadURL('about:blank').catch(() => {});
    return;
  }
  if (!isSafeNavigationUrl(url)) {
    console.warn('[SECURITY] Blocked navigation to unsafe URL:', url);
    view.webContents.loadURL('about:blank').catch(() => {});
    return;
  }
  view.webContents.loadURL(url).catch(() => {});
}

const sameBounds = (a, b) => a.x === b.x && a.y === b.y && a.width === b.width && a.height === b.height;

/**
 * Show the active tab's page in the frame the interface reported, or nothing (Launchpad, error page, no frame yet).
 * Only what changed is touched: re-adding views on every resize made the drawer drag stutter.
 */
function syncActiveView() {
  if (!mainWindow || mainWindow.isDestroyed() || !manager) return;
  const tab = manager.tab(manager.activeTabId);
  const showable = Boolean(tab) && !currentBounds.isHidden && !isInternalUrl(tab.url) && !tab.error;
  const view = showable ? ensureView(tab.id) : null;
  const tabChanged = activationChanged;
  activationChanged = false;

  if (attachedTabId && (!view || attachedTabId !== tab.id)) {
    const old = views.get(attachedTabId);
    if (old) {
      detachView(old);
      old.setVisible(false);
    }
    attachedTabId = null;
  }
  if (!view) {
    resetVisualCursor();
    updateAgentShield();
    raisePopupLayer();
    return;
  }

  const winBounds = mainWindow.getContentBounds();
  const isFullScreen = mainWindow.isFullScreen();
  const x = Math.max(0, Math.round(currentBounds.x || 0));
  const y = isFullScreen ? Math.max(0, Math.round(currentBounds.y || 0)) : Math.max(70, Math.round(currentBounds.y || 0));
  const maxWidth = Math.max(0, winBounds.width - x);
  const maxHeight = Math.max(0, winBounds.height - y);
  const finalBounds = {
    x,
    y,
    width: Math.min(Math.round(currentBounds.width > 0 ? currentBounds.width : maxWidth), maxWidth),
    height: Math.min(Math.round(currentBounds.height > 0 ? currentBounds.height : maxHeight), maxHeight),
  };

  if (attachedTabId !== tab.id) {
    mainWindow.contentView.addChildView(view);
    view.setVisible(true);
    attachedTabId = tab.id;
    if (tabChanged && !mainWindow.webContents.isFocused()) view.webContents.focus();
  }
  if (!sameBounds(view.getBounds(), finalBounds)) view.setBounds(finalBounds);
  if (DEBUG_SYNC) console.log('[SYNC]', tab.id, JSON.stringify(finalBounds));
  updateAgentShield();
  raisePopupLayer();
}

// ── page events ───────────────────────────────────────────────────────────────────────────────────

const GOOGLE_REJECTED = /\/signin\/rejected|disallowed_useragent|authError=.*(disallowed|rejected)/i;
const GOOGLE_REJECTED_TEXT = /browser or app may not be secure|disallowed_useragent|this browser (is not|isn.t) supported|try using a different browser/i;

/** Google refuses sign-in from embedded browsers. Detect its refusal and let the interface explain it (no workaround). */
async function checkGoogleSignin(tabId, webContents) {
  let u;
  try { u = new URL(webContents.getURL()); } catch { return; }
  if (u.hostname !== 'accounts.google.com') return;
  let blocked = GOOGLE_REJECTED.test(u.pathname + u.search);
  if (!blocked) {
    const text = await webContents.executeJavaScriptInIsolatedWorld(1001, [{ code: "document.body ? document.body.innerText.slice(0, 4000) : ''" }])
      .catch(() => '');
    blocked = GOOGLE_REJECTED_TEXT.test(String(text || ''));
  }
  if (!blocked || !manager.tab(tabId)) return;
  const cont = u.searchParams.get('continue');
  const target = isHttpUrl(cont) ? cont : 'https://accounts.google.com/';
  manager.updateTab(tabId, { notice: { kind: 'google-signin-blocked', url: target } });
  console.log('[AUTH] Google refused sign-in in tab', tabId, 'at', u.pathname);
}

function attachTabListeners(tabId, view) {
  const { webContents } = view;
  const tabNow = () => manager.tab(tabId);
  const agentWorking = () => tabNow()?.agent?.status === 'working';

  webContents.on('did-start-loading', () => manager.updateTab(tabId, { loading: true }));

  webContents.on('did-start-navigation', (details) => {
    if (!details.isMainFrame || details.isSameDocument) return;
    const tab = tabNow();
    if (!tab) return;
    const patch = { error: null };
    try {
      if (tab.notice && new URL(details.url).hostname !== 'accounts.google.com') patch.notice = null;
    } catch { /* keep the notice */ }
    manager.updateTab(tabId, patch);
  });

  webContents.on('did-stop-loading', () => {
    const url = normalizeUrl(webContents.getURL());
    const tab = tabNow();
    manager.updateTab(tabId, {
      loading: false,
      ...(tab?.error ? {} : { url }),
      title: url === LAUNCHPAD ? 'New Tab' : webContents.getTitle(),
      ...getNavState(webContents),
    });
    checkGoogleSignin(tabId, webContents);
  });

  webContents.on('did-fail-load', (_event, code, description, validatedURL, isMainFrame) => {
    if (!isMainFrame || code === -3) return; // -3: aborted (a new navigation replaced it)
    manager.updateTab(tabId, {
      loading: false,
      error: { code, description: String(description || ''), url: validatedURL || tabNow()?.url || '' },
      ...getNavState(webContents),
    });
  });

  webContents.on('render-process-gone', (_event, details) => {
    if (details.reason === 'clean-exit') return;
    manager.updateTab(tabId, { loading: false, error: { code: 'crashed', description: details.reason, url: tabNow()?.url || '' } });
  });

  webContents.on('page-title-updated', (_event, title) => {
    const url = normalizeUrl(webContents.getURL());
    manager.updateTab(tabId, { title: url === LAUNCHPAD ? 'New Tab' : title });
    history.setTitle(webContents.getURL(), title);
  });

  webContents.on('page-favicon-updated', (_event, favicons) => {
    const icon = (favicons || []).find((f) => /^https?:|^data:image\//.test(f));
    if (icon) manager.updateTab(tabId, { favicon: icon });
  });

  webContents.on('did-navigate', (_event, url) => {
    manager.updateTab(tabId, { url: normalizeUrl(url), ...getNavState(webContents) });
    // the address bar suggests what you visited; an agent's own browsing is not your history
    if (!agentWorking()) {
      history.record(url, webContents.getTitle());
      historyFile.write(history.toJSON());
    }
  });

  webContents.on('did-navigate-in-page', (_event, url, isMainFrame) => {
    if (isMainFrame) manager.updateTab(tabId, { url: normalizeUrl(url), ...getNavState(webContents) });
  });

  webContents.on('media-started-playing', () => manager.updateTab(tabId, { audible: true }));
  webContents.on('media-paused', () => manager.updateTab(tabId, { audible: false }));

  webContents.on('before-input-event', (event, input) => handleShortcutInput(event, input));
  webContents.on('context-menu', (_event, params) => showPageMenu(tabId, webContents, params));

  // A page that closes itself (window.close() on a tab a script opened) closes its tab.
  webContents.on('destroyed', () => {
    if (closingTabs.has(tabId) || views.get(tabId)?.webContents !== webContents) return;
    views.delete(tabId);
    if (manager.tab(tabId)) manager.closeTab(tabId, { record: false });
  });

  webContents.setWindowOpenHandler(({ url, disposition }) => handleWindowOpen(tabId, webContents, url, disposition));
}

/**
 * New windows from a page.
 *  - An agent is working in the tab: open the link in that same tab, so the work stays where the agent is.
 *  - A popup (window.open with a size, as sign-in and payment flows use): a real popup window that keeps
 *    window.opener, so the flow can report back to the page and close itself.
 *  - A new tab (target=_blank, middle click): a tab next to its opener, in the opener's group, keeping the opener
 *    relationship the page asked for (the page's own noopener still applies).
 */
function handleWindowOpen(tabId, webContents, url, disposition) {
  if (!isHttpUrl(url) || !isSafeNavigationUrl(url)) return { action: 'deny' };
  const opener = manager.tab(tabId);
  if (!opener) return { action: 'deny' };
  if (opener.agent?.status === 'working') {
    loadTabUrl({ webContents }, url);
    return { action: 'deny' };
  }
  if (disposition === 'new-window') {
    return {
      action: 'allow',
      overrideBrowserWindowOptions: {
        parent: mainWindow,
        autoHideMenuBar: true,
        webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
      },
    };
  }
  return {
    action: 'allow',
    outlivesOpener: true,
    createWindow: (options) => {
      const view = createTabView(options.webContents);
      adoptingView = view;
      manager.createTab({
        url,
        groupId: opener.groupId,
        after: tabId,
        activate: disposition !== 'background-tab',
      });
      return view.webContents;
    },
  };
}

/** Popup windows (sign-in, payment) get the same protections as tabs, and Google's refusal is detected there too. */
function setupPopupWindow(win, openerTabId) {
  const wc = win.webContents;
  wc.setWindowOpenHandler(({ url }) => (isHttpUrl(url) && isSafeNavigationUrl(url)
    ? { action: 'allow', overrideBrowserWindowOptions: { parent: mainWindow, webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true } } }
    : { action: 'deny' }));
  wc.on('did-stop-loading', () => { if (manager.tab(openerTabId)) checkGoogleSignin(openerTabId, wc); });
  wc.on('before-input-event', (event, input) => {
    if (input.type === 'keyDown' && input.key.toLowerCase() === 'w' && (IS_MAC ? input.meta : input.control) && !input.shift && !input.alt) {
      event.preventDefault();
      win.close();
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// Commands: one implementation each, used by keyboard shortcuts, the menu bar, context menus and the interface.
// ─────────────────────────────────────────────────────────────────────────────────────────────────
const activeTab = () => manager.tab(manager.activeTabId);
const activeView = () => (manager.activeTabId ? views.get(manager.activeTabId) : null);
const visibleTabIds = () => manager.order.filter((id) => !manager.group(manager.tab(id).groupId).collapsed);
const uiCommand = (type, data = {}) => { if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('ui-command', { type, ...data }); };

function focusOmnibox() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.focus();
  uiCommand('focus-omnibox');
}

function newTab({ url = LAUNCHPAD, groupId, after, activate = true } = {}) {
  const tab = manager.createTab({ url, groupId: groupId && manager.group(groupId) ? groupId : undefined, after, activate });
  if (activate && url === LAUNCHPAD) focusOmnibox();
  return tab;
}

function navigate(tabId, url) {
  const tab = manager.tab(tabId);
  if (!tab || typeof url !== 'string') return;
  if (!INTERNAL_URLS.has(url) && !isSafeNavigationUrl(url)) return;
  manager.updateTab(tabId, { url: normalizeUrl(INTERNAL_URLS.has(url) ? '' : url), error: null, notice: null, loading: !INTERNAL_URLS.has(url) });
  const view = views.get(tabId) || ensureView(tabId);
  if (view) loadTabUrl(view, url);
}

function reload(tabId, ignoreCache = false) {
  const tab = manager.tab(tabId);
  if (!tab) return;
  if (tab.error) return navigate(tabId, tab.error.url || tab.url); // Reload on an error page retries the address
  const view = views.get(tabId);
  if (!view || isInternalUrl(tab.url)) return;
  if (ignoreCache) view.webContents.reloadIgnoringCache();
  else view.webContents.reload();
}

function closeTab(tabId) {
  if (!manager.tab(tabId)) return;
  manager.closeTab(tabId);
}

/** Close a group with all its tabs (worker tabs included) after asking when that would lose more than one tab or work. */
async function closeGroup(groupId, { confirm = true } = {}) {
  const ids = manager.tabsInGroup(groupId);
  if (!ids.length) return false;
  const working = ids.filter((id) => manager.tab(id).agent?.status === 'working').length;
  if (confirm && (ids.length > 1 || working)) {
    const name = manager.group(groupId).name || manager.tab(ids[0]).title || 'this group';
    const { response } = await dialog.showMessageBox(mainWindow, {
      type: 'warning',
      buttons: ['Close Group', 'Cancel'],
      defaultId: 0,
      cancelId: 1,
      message: `Close “${name.slice(0, 60)}”?`,
      detail: `This closes ${ids.length} ${ids.length === 1 ? 'tab' : 'tabs'}${working ? ' and stops the AI working in this group' : ''}. `
        + 'Its chat stays in History. You can reopen the group with ⇧⌘T.',
    });
    if (response !== 0) return false;
  }
  // One backend call stops the group's agents and closes its chat; the tabs close at once, without waiting for it.
  closingGroups.add(groupId);
  backendPost(`/chat/groups/${encodeURIComponent(groupId)}/close`);
  manager.closeGroup(groupId);
  closingGroups.delete(groupId);
  return true;
}

function moveTab(tabId, opts) {
  const res = manager.moveTab(tabId, opts);
  if (!res) return;
  if (res.toGroup !== res.fromGroup) backendJoin(res.toGroup, tabId, 'link');
  if (res.emptied) backendPost(`/chat/groups/${encodeURIComponent(res.emptied)}/close`);
}

function createGroup(tabIds, name, color) {
  const { group, emptied } = manager.createGroup({ tabIds, name, color });
  for (const id of manager.tabsInGroup(group.id)) backendJoin(group.id, id, 'link');
  for (const gid of emptied) backendPost(`/chat/groups/${encodeURIComponent(gid)}/close`);
  return group;
}

function ungroup(groupId) {
  for (const { tabId, groupId: gid } of manager.ungroup(groupId)) backendJoin(gid, tabId, 'main');
}

function selectRelativeTab(step) {
  const ids = visibleTabIds();
  const i = ids.indexOf(manager.activeTabId);
  if (i < 0 || ids.length < 2) return;
  manager.setActive(ids[(i + step + ids.length) % ids.length]);
}

function zoom(delta) {
  const view = activeView();
  if (!view) return;
  view.webContents.setZoomLevel(delta === 0 ? 0 : view.webContents.getZoomLevel() + delta);
}

const COMMANDS = {
  'new-tab': () => newTab(),
  'reopen-closed': () => manager.reopenClosed(),
  'close-tab': () => closeTab(manager.activeTabId),
  'focus-omnibox': () => focusOmnibox(),
  reload: () => reload(manager.activeTabId),
  'hard-reload': () => reload(manager.activeTabId, true),
  stop: () => activeView()?.webContents.stop(),
  back: () => { const v = activeView(); if (v && v.webContents.navigationHistory.canGoBack()) v.webContents.navigationHistory.goBack(); },
  forward: () => { const v = activeView(); if (v && v.webContents.navigationHistory.canGoForward()) v.webContents.navigationHistory.goForward(); },
  'next-tab': () => selectRelativeTab(1),
  'prev-tab': () => selectRelativeTab(-1),
  'last-tab': () => { const ids = visibleTabIds(); manager.setActive(ids[ids.length - 1]); },
  'toggle-assistant': () => uiCommand('toggle-assistant'),
  'zoom-in': () => zoom(0.5),
  'zoom-out': () => zoom(-0.5),
  'zoom-reset': () => zoom(0),
  devtools: () => activeView()?.webContents.openDevTools({ mode: 'detach' }),
  shortcuts: () => uiCommand('show-shortcuts'),
};
for (let n = 1; n <= 8; n += 1) COMMANDS[`tab-${n}`] = () => { const id = visibleTabIds()[n - 1]; if (id) manager.setActive(id); };

// Keyboard shortcuts: matched in every page and in the interface (before-input-event), so they work wherever the focus
// is; the menu bar lists them too. A matched key never reaches the page.
const MOD = IS_MAC ? 'meta' : 'control';
const SHORTCUTS = [
  { id: 'new-tab', label: 'New Tab', accel: 'CmdOrCtrl+T', key: 't', mods: [MOD] },
  { id: 'reopen-closed', label: 'Reopen Closed Tab', accel: 'CmdOrCtrl+Shift+T', key: 't', mods: [MOD, 'shift'] },
  { id: 'close-tab', label: 'Close Tab', accel: 'CmdOrCtrl+W', key: 'w', mods: [MOD] },
  { id: 'focus-omnibox', label: 'Open Location…', accel: 'CmdOrCtrl+L', key: 'l', mods: [MOD] },
  { id: 'reload', label: 'Reload This Page', accel: 'CmdOrCtrl+R', key: 'r', mods: [MOD] },
  { id: 'hard-reload', label: 'Force Reload This Page', accel: 'CmdOrCtrl+Shift+R', key: 'r', mods: [MOD, 'shift'] },
  { id: 'stop', label: 'Stop', accel: 'CmdOrCtrl+.', key: '.', mods: [MOD] },
  { id: 'back', label: 'Back', accel: 'CmdOrCtrl+[', key: '[', mods: [MOD] },
  { id: 'forward', label: 'Forward', accel: 'CmdOrCtrl+]', key: ']', mods: [MOD] },
  { id: 'next-tab', label: 'Select Next Tab', accel: 'Ctrl+Tab', code: 'Tab', mods: ['control'] },
  { id: 'prev-tab', label: 'Select Previous Tab', accel: 'Ctrl+Shift+Tab', code: 'Tab', mods: ['control', 'shift'] },
  { id: 'next-tab', accel: 'CmdOrCtrl+Alt+Right', code: 'ArrowRight', mods: [MOD, 'alt'], hidden: true },
  { id: 'prev-tab', accel: 'CmdOrCtrl+Alt+Left', code: 'ArrowLeft', mods: [MOD, 'alt'], hidden: true },
  ...Array.from({ length: 8 }, (_, i) => ({ id: `tab-${i + 1}`, label: `Tab ${i + 1}`, accel: `CmdOrCtrl+${i + 1}`, key: String(i + 1), mods: [MOD], hidden: true })),
  { id: 'last-tab', label: 'Last Tab', accel: 'CmdOrCtrl+9', key: '9', mods: [MOD], hidden: true },
  { id: 'toggle-assistant', label: 'Assistant', accel: 'CmdOrCtrl+J', key: 'j', mods: [MOD] },
  { id: 'zoom-in', label: 'Zoom In', accel: 'CmdOrCtrl+=', key: '=', mods: [MOD] },
  { id: 'zoom-in', accel: 'CmdOrCtrl+Plus', key: '+', mods: [MOD, 'shift'], hidden: true },
  { id: 'zoom-out', label: 'Zoom Out', accel: 'CmdOrCtrl+-', key: '-', mods: [MOD] },
  { id: 'zoom-reset', label: 'Actual Size', accel: 'CmdOrCtrl+0', key: '0', mods: [MOD] },
  { id: 'devtools', label: 'Developer Tools for This Page', accel: 'CmdOrCtrl+Alt+I', code: 'KeyI', mods: [MOD, 'alt'] },
  { id: 'shortcuts', label: 'Keyboard Shortcuts', accel: 'CmdOrCtrl+/', key: '/', mods: [MOD] },
];
const ALL_MODS = ['meta', 'control', 'shift', 'alt'];

function matchShortcut(input) {
  if (input.type !== 'keyDown') return null;
  const key = String(input.key || '').toLowerCase();
  return SHORTCUTS.find((s) => ALL_MODS.every((m) => Boolean(input[m]) === s.mods.includes(m))
    && (s.code ? input.code === s.code : key === s.key)) || null;
}

function handleShortcutInput(event, input) {
  if (process.env.COMEX_DEBUG_KEYS === '1' && input.type === 'keyDown') console.log('[KEY]', JSON.stringify({ key: input.key, code: input.code, meta: input.meta, control: input.control, shift: input.shift, alt: input.alt }));
  const s = matchShortcut(input);
  if (!s) return;
  event.preventDefault();
  COMMANDS[s.id]?.();
}

function buildAppMenu() {
  const item = (id) => {
    const s = SHORTCUTS.find((x) => x.id === id && !x.hidden) || SHORTCUTS.find((x) => x.id === id);
    return {
      label: s.label,
      accelerator: s.accel,
      // In a sign-in popup, Close Tab closes that popup; other commands act on the browser window.
      click: (_item, win) => {
        if (win && mainWindow && win !== mainWindow) {
          if (id === 'close-tab') win.close();
          return;
        }
        COMMANDS[id]?.();
      },
    };
  };
  const hidden = SHORTCUTS.filter((s) => s.hidden).map((s) => ({
    label: s.label || s.id, accelerator: s.accel, visible: false, acceleratorWorksWhenHidden: true, click: () => COMMANDS[s.id]?.(),
  }));
  const template = [
    ...(IS_MAC ? [{ role: 'appMenu' }] : []),
    { label: 'File', submenu: [item('new-tab'), item('reopen-closed'), { type: 'separator' }, item('focus-omnibox'), { type: 'separator' }, item('close-tab'), { label: 'Close Window', accelerator: 'CmdOrCtrl+Shift+W', role: 'close' }] },
    { role: 'editMenu' },
    { label: 'View', submenu: [item('reload'), item('hard-reload'), item('stop'), { type: 'separator' }, item('zoom-in'), item('zoom-out'), item('zoom-reset'), { type: 'separator' }, item('toggle-assistant'), { type: 'separator' }, item('devtools'), { role: 'togglefullscreen' }] },
    { label: 'History', submenu: [item('back'), item('forward')] },
    { label: 'Tab', submenu: [item('next-tab'), item('prev-tab'), { type: 'separator' }, ...hidden] },
    { role: 'windowMenu' },
    { role: 'help', submenu: [item('shortcuts')] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template.map((m) => (m.submenu ? { ...m, submenu: m.submenu.filter(Boolean) } : m))));
}

// ── context menus (native, so they draw above pages) ──────────────────────────────────────────────

const COLOR_NAMES = { blue: 'Blue', red: 'Red', yellow: 'Yellow', green: 'Green', pink: 'Pink', purple: 'Purple', cyan: 'Cyan', orange: 'Orange', grey: 'Grey' };

function groupLabel(groupId) {
  const g = manager.group(groupId);
  const ids = manager.tabsInGroup(groupId);
  return g?.name || `${manager.tab(ids[0])?.title || 'Group'}${ids.length > 1 ? ` + ${ids.length - 1}` : ''}`;
}

function showTabMenu(tabId) {
  const tab = manager.tab(tabId);
  if (!tab) return;
  const inShownGroup = manager.isShownGroup(tab.groupId) && manager.tabsInGroup(tab.groupId).length > 1;
  const idx = manager.order.indexOf(tabId);
  const others = manager.order.filter((id) => id !== tabId);
  const toRight = manager.order.slice(idx + 1);
  const shownGroups = [...new Set(manager.order.map((id) => manager.tab(id).groupId))]
    .filter((gid) => gid !== tab.groupId && manager.isShownGroup(gid));
  Menu.buildFromTemplate([
    { label: 'New Tab to the Right', click: () => newTab({ after: tabId, groupId: inShownGroup ? tab.groupId : undefined }) },
    {
      label: 'Add Tab to Group',
      submenu: [
        { label: 'New Group', click: () => { const g = createGroup([tabId]); uiCommand('rename-group', { groupId: g.id }); } },
        ...(shownGroups.length ? [{ type: 'separator' }] : []),
        ...shownGroups.map((gid) => ({ label: groupLabel(gid).slice(0, 40), click: () => moveTab(tabId, { groupId: gid }) })),
      ],
    },
    ...(inShownGroup || manager.group(tab.groupId)?.name ? [{ label: 'Remove from Group', click: () => moveTab(tabId, { ungroup: true }) }] : []),
    { type: 'separator' },
    { label: 'Reload', click: () => reload(tabId) },
    { label: 'Duplicate', click: () => manager.duplicateTab(tabId) },
    { type: 'separator' },
    { label: 'Close Tab', accelerator: 'CmdOrCtrl+W', registerAccelerator: false, click: () => closeTab(tabId) },
    { label: 'Close Other Tabs', enabled: others.length > 0, click: () => manager.closeTabs(others, tabId) },
    { label: 'Close Tabs to the Right', enabled: toRight.length > 0, click: () => manager.closeTabs(toRight) },
    { type: 'separator' },
    { label: 'Reopen Closed Tab', accelerator: 'CmdOrCtrl+Shift+T', registerAccelerator: false, enabled: manager.closed.length > 0, click: () => manager.reopenClosed() },
  ]).popup({ window: mainWindow });
}

function showGroupMenu(groupId) {
  const g = manager.group(groupId);
  if (!g) return;
  Menu.buildFromTemplate([
    { label: 'New Tab in Group', click: () => newTab({ groupId }) },
    { label: 'Rename Group…', click: () => uiCommand('rename-group', { groupId }) },
    { label: 'Color', submenu: GROUP_COLORS.map((c) => ({ label: COLOR_NAMES[c], type: 'radio', checked: g.color === c, click: () => manager.setGroupColor(groupId, c) })) },
    { label: g.collapsed ? 'Expand Group' : 'Collapse Group', click: () => manager.setGroupCollapsed(groupId, !g.collapsed) },
    { type: 'separator' },
    { label: 'Ungroup', click: () => ungroup(groupId) },
    { label: 'Close Group…', click: () => closeGroup(groupId) },
  ]).popup({ window: mainWindow });
}

function showBookmarkMenu(url) {
  Menu.buildFromTemplate([
    { label: 'Open in New Tab', click: () => newTab({ url }) },
    { label: 'Copy Link Address', click: () => clipboard.writeText(url) },
    { type: 'separator' },
    { label: 'Remove Bookmark', click: () => { bookmarks.remove(url); bookmarksFile.write(bookmarks.toJSON()); pushState(); } },
  ]).popup({ window: mainWindow });
}

function showPageMenu(tabId, webContents, params) {
  const tab = manager.tab(tabId);
  if (!tab) return;
  const nav = webContents.navigationHistory;
  const items = [];
  const groupForLinks = manager.isShownGroup(tab.groupId) ? tab.groupId : undefined;
  if (isHttpUrl(params.linkURL)) {
    items.push(
      { label: 'Open Link in New Tab', click: () => newTab({ url: params.linkURL, after: tabId, groupId: groupForLinks, activate: false }) },
      { label: 'Copy Link Address', click: () => clipboard.writeText(params.linkURL) },
      { type: 'separator' },
    );
  }
  if (params.mediaType === 'image' && isHttpUrl(params.srcURL)) {
    items.push(
      { label: 'Open Image in New Tab', click: () => newTab({ url: params.srcURL, after: tabId, groupId: groupForLinks, activate: false }) },
      { label: 'Copy Image Address', click: () => clipboard.writeText(params.srcURL) },
      { type: 'separator' },
    );
  }
  if (params.isEditable) {
    items.push(
      { role: 'undo', enabled: params.editFlags.canUndo },
      { role: 'redo', enabled: params.editFlags.canRedo },
      { type: 'separator' },
      { role: 'cut', enabled: params.editFlags.canCut },
      { role: 'copy', enabled: params.editFlags.canCopy },
      { role: 'paste', enabled: params.editFlags.canPaste },
      { role: 'selectAll' },
      { type: 'separator' },
    );
  } else if (params.selectionText && params.selectionText.trim()) {
    const text = params.selectionText.trim();
    items.push(
      { role: 'copy' },
      { label: `Search Google for “${text.length > 30 ? `${text.slice(0, 30)}…` : text}”`, click: () => newTab({ url: `https://www.google.com/search?q=${encodeURIComponent(text)}`, after: tabId, groupId: groupForLinks }) },
      { type: 'separator' },
    );
  }
  items.push(
    { label: 'Back', enabled: nav.canGoBack(), click: () => nav.goBack() },
    { label: 'Forward', enabled: nav.canGoForward(), click: () => nav.goForward() },
    { label: 'Reload', click: () => reload(tabId) },
    { type: 'separator' },
    { label: 'Inspect', click: () => webContents.inspectElement(params.x, params.y) },
  );
  Menu.buildFromTemplate(items).popup({ window: mainWindow });
}

// ── window ────────────────────────────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    // Benchmark instances open without taking keyboard focus from whatever the user is doing
    ...(process.env.COMEX_BENCH_WINDOW === '1' ? { show: false, focusable: false } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      allowRunningInsecureContent: false,
    },
  });

  if (process.env.COMEX_BENCH_WINDOW === '1') mainWindow.once('ready-to-show', () => mainWindow.showInactive());

  // The React shell should never try to open a new browser window.
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  mainWindow.webContents.on('before-input-event', (event, input) => handleShortcutInput(event, input));

  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL(RENDERER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    // The pages go with the window; their tabs stay in the session and reload when the window opens again.
    for (const id of [...views.keys()]) {
      const v = views.get(id);
      views.delete(id);
      if (!gone(v)) { closingTabs.add(id); v.webContents.close(); closingTabs.delete(id); }
      if (manager.tab(id)) manager.updateTab(id, { discarded: id !== manager.activeTabId });
    }
    attachedTabId = null;
    agentShield = null;
    popupLayer = null;
    mainWindow = null;
  });

  if (isVisualCursorEnabled) {
    createCursorWindow();
  }
}

function createCursorWindow() {
  if (!isVisualCursorEnabled || !mainWindow || mainWindow.isDestroyed()) return;
  if (cursorWindow && !cursorWindow.isDestroyed()) return;

  const winBounds = mainWindow.getContentBounds();
  cursorWindow = new BrowserWindow({
    parent: mainWindow,
    width: winBounds.width || 1400,
    height: winBounds.height || 900,
    x: winBounds.x,
    y: winBounds.y,
    frame: false,
    transparent: true,
    hasShadow: false,
    focusable: false,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'cursor_preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  cursorWindow.setIgnoreMouseEvents(true, { forward: true });
  cursorWindow.setAlwaysOnTop(true, 'pop-up-menu');
  cursorWindow.loadFile(path.join(__dirname, 'cursor_overlay.html'));
  cursorWindow.showInactive();
  cursorWindow.webContents.on('did-fail-load', (_e, code, desc) => {
    console.error('[CURSOR] Overlay HTML failed to load:', code, desc);
  });

  const syncCursorBounds = () => {
    if (!cursorWindow || cursorWindow.isDestroyed() || !mainWindow || mainWindow.isDestroyed()) return;
    cursorWindow.setBounds(mainWindow.getContentBounds());
  };

  mainWindow.on('resize', syncCursorBounds);
  mainWindow.on('move', syncCursorBounds);
  mainWindow.once('ready-to-show', syncCursorBounds);
  mainWindow.on('minimize', () => {
    resetVisualCursor();
  });
}

// ── permissions: nothing is granted silently ──────────────────────────────────────────────────────

let permissionQueue = Promise.resolve();

/** Ask the user, one request at a time (dialogs never stack). Resolves {allow, remember}. */
function askPermission(webContents, origin, permission, details) {
  const run = async () => {
    if (!webContents || webContents.isDestroyed()) return { allow: false, remember: false };
    const host = new URL(origin).host;
    let what = ASKABLE[permission];
    if (permission === 'media') {
      const t = new Set(details.mediaTypes || []);
      what = t.has('video') && t.has('audio') ? 'use your camera and microphone' : t.has('video') ? 'use your camera' : 'use your microphone';
    }
    if (permission === 'openExternal' && details.externalURL) {
      try { what = `open a “${new URL(details.externalURL).protocol.replace(':', '')}” link in another app`; } catch { /* keep generic */ }
    }
    const top = originOf(webContents.getURL());
    const parent = BrowserWindow.fromWebContents(webContents) || mainWindow;
    const { response, checkboxChecked } = await dialog.showMessageBox(parent, {
      type: 'question',
      buttons: ['Allow', 'Block'],
      defaultId: 1,
      cancelId: 1,
      message: `${host} wants to ${what}`,
      detail: top && top !== origin ? `It is embedded in ${new URL(top).host}.` : 'You can change this later by clearing site data.',
      checkboxLabel: 'Remember my decision for this site',
      checkboxChecked: true,
    });
    return { allow: response === 0, remember: checkboxChecked };
  };
  const result = permissionQueue.then(run, run);
  permissionQueue = result.catch(() => {});
  return result;
}

function installPermissionHandlers() {
  const ses = session.defaultSession;
  ses.setPermissionRequestHandler((webContents, permission, callback, details = {}) => {
    const origin = originOf(details.requestingUrl || (webContents && !webContents.isDestroyed() ? webContents.getURL() : ''));
    const decision = permissions.decide(origin, permission, details);
    if (decision !== 'ask') {
      if (decision === 'deny' && !(permission in ASKABLE) && permission !== 'unknown') console.log('[PERMISSION] denied', permission, 'for', origin || '(internal page)');
      callback(decision === 'allow');
      return;
    }
    askPermission(webContents, origin, permission, details).then(({ allow, remember }) => {
      if (remember) {
        permissions.remember(origin, permission, details, allow);
        permissionsFile.write(permissions.toJSON());
      }
      callback(allow);
    }, () => callback(false));
  });
  ses.setPermissionCheckHandler((_webContents, permission, requestingOrigin, details = {}) => {
    const origin = originOf(requestingOrigin || details.requestingUrl || '');
    const mediaTypes = details.mediaType && details.mediaType !== 'unknown' ? [details.mediaType] : undefined;
    return permissions.decide(origin, permission, { mediaTypes }) === 'allow';
  });
  ses.setDevicePermissionHandler(() => false);
  // USB, HID, serial and Bluetooth device pickers are not offered: requests are cancelled.
  ses.on('select-hid-device', (event, _details, callback) => { event.preventDefault(); callback(); });
  ses.on('select-serial-port', (event, _ports, _wc, callback) => { event.preventDefault(); callback(''); });
  ses.on('select-usb-device', (event, _details, callback) => { event.preventDefault(); callback(); });
}

app.on('web-contents-created', (_event, contents) => {
  contents.on('will-attach-webview', (event) => event.preventDefault());
  contents.on('select-bluetooth-device', (event, _devices, callback) => { event.preventDefault(); callback(''); });
  contents.on('did-create-window', (win) => {
    const openerTabId = [...views.entries()].find(([, v]) => v.webContents === contents)?.[0];
    setupPopupWindow(win, openerTabId);
  });
});

app.whenReady().then(() => {
  initState();
  installPermissionHandlers();
  buildAppMenu();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('before-quit', () => {
  if (!manager) return;
  sessionFile.write(manager.serialize());
  sessionFile.flush();
  historyFile.flush();
  bookmarksFile.flush();
  permissionsFile.flush();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Ask Chromium for the exact DevTools target id of a tab, so the agent backend can bind a worker
// to it over CDP without URL-hash tricks.
async function getDevToolsTargetId(webContents) {
  const dbg = webContents.debugger;
  const wasAttached = dbg.isAttached();
  if (!wasAttached) dbg.attach('1.3');
  try {
    const { targetInfo } = await dbg.sendCommand('Target.getTargetInfo');
    return targetInfo.targetId;
  } finally {
    if (!wasAttached) dbg.detach();
  }
}

const AGENT_TAB_ID_PATTERN = /^[a-zA-Z0-9_\-:]{1,100}$/;
const AGENT_TAB_STATUSES = new Set(['working', 'completed', 'failed', 'cancelled', 'blocked']);

// ---------------------------------------------------------------------------------------------
// Agent shield: while an agent works in the tab you are looking at, a transparent native view is
// stacked above that tab. It draws the amber corner lights and a status pill, and because the user's
// mouse and keyboard land on it the page underneath cannot be used. The agent is unaffected: its input
// is sent through the debugging protocol straight to the page, never through this view.
// ---------------------------------------------------------------------------------------------
const agentOverlays = new Map(); // tabId -> { status, step, holdUntil }
let agentShield = null;
let agentShieldReady = false;
let agentShieldAttached = false;

function ensureAgentShield() {
  if (!gone(agentShield)) return agentShield;
  agentShield = new WebContentsView({
    webPreferences: {
      preload: path.join(__dirname, 'agent_shield_preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  agentShield.setBackgroundColor('#00000000');
  agentShield.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  agentShield.webContents.on('will-navigate', (event) => event.preventDefault());
  agentShield.webContents.on('before-input-event', (event, input) => handleShortcutInput(event, input));
  agentShieldReady = false;
  agentShieldAttached = false;
  agentShield.webContents
    .loadFile(path.join(__dirname, 'agent_shield.html'))
    .then(() => { agentShieldReady = true; pushAgentShieldState(true); })
    .catch((err) => console.warn('[SHIELD] Could not load shield page:', err.message));
  return agentShield;
}

function pushAgentShieldState(fresh = false) {
  if (gone(agentShield) || !agentShieldReady) return;
  const state = agentOverlays.get(manager.activeTabId);
  if (!state) return;
  const payload = JSON.stringify({ status: state.status, step: state.step || '' });
  agentShield.webContents.executeJavaScript(`window.__shield(${payload}, ${fresh ? 'true' : 'false'})`, true)
    .catch(() => { /* shield page is reloading */ });
}

function detachAgentShield() {
  if (agentShield && agentShieldAttached && mainWindow && !mainWindow.isDestroyed()) {
    try { mainWindow.contentView.removeChildView(agentShield); } catch { /* already detached */ }
  }
  agentShieldAttached = false;
}

// Show the shield above the active tab while its agent works (and briefly after, to show the result);
// otherwise remove it. Call after anything that changes the active tab, its bounds or its agent state.
function updateAgentShield() {
  if (!mainWindow || mainWindow.isDestroyed() || !manager) return;
  const state = agentOverlays.get(manager.activeTabId);
  const view = manager.activeTabId ? views.get(manager.activeTabId) : null;
  const viewShown = !gone(view) && attachedTabId === manager.activeTabId;
  const active = state && (state.status === 'working' || Date.now() < (state.holdUntil || 0));
  if (!viewShown || !active) {
    detachAgentShield();
    return;
  }
  const shield = ensureAgentShield();
  const wasAttached = agentShieldAttached;
  if (!sameBounds(shield.getBounds(), view.getBounds())) shield.setBounds(view.getBounds());
  const kids = mainWindow.contentView.children;
  if (!wasAttached || kids.indexOf(shield) < kids.indexOf(view)) mainWindow.contentView.addChildView(shield); // keeps it above the tab view
  agentShieldAttached = true;
  pushAgentShieldState(!wasAttached);
  // Keyboard input must not reach the locked page either.
  if (!wasAttached && state.status === 'working' && view.webContents.isFocused()) {
    shield.webContents.focus();
  }
}

// Safety net: while a shield is up, make sure it still matches the page it covers.
setInterval(() => {
  if (!agentShieldAttached || gone(agentShield) || !mainWindow || mainWindow.isDestroyed()) return;
  const view = manager.activeTabId ? views.get(manager.activeTabId) : null;
  if (gone(view)) return;
  if (!sameBounds(view.getBounds(), agentShield.getBounds())) updateAgentShield();
}, 400);

// ---------------------------------------------------------------------------------------------
// Popup layer: address-bar suggestions and hover cards reach below the toolbar, over the page. The
// interface cannot draw there (pages are native views above it), so they are drawn by one small
// transparent view stacked on top, fed by the interface. It never takes part in navigation.
// ---------------------------------------------------------------------------------------------
let popupLayer = null;
let popupReady = false;
let popupShown = false;
let popupPayload = null;

function ensurePopupLayer() {
  if (!gone(popupLayer)) return popupLayer;
  popupLayer = new WebContentsView({
    webPreferences: { preload: path.join(__dirname, 'chrome_popup_preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  popupLayer.setBackgroundColor('#00000000');
  popupLayer.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  popupLayer.webContents.on('will-navigate', (event) => event.preventDefault());
  popupReady = false;
  popupLayer.webContents.loadFile(path.join(__dirname, 'chrome_popup.html'))
    .then(() => { popupReady = true; if (popupPayload) popupLayer.webContents.send('popup-render', popupPayload); })
    .catch((err) => console.warn('[POPUP] Could not load popup layer:', err.message));
  return popupLayer;
}

function raisePopupLayer() {
  if (!popupShown || !popupLayer || !mainWindow || mainWindow.isDestroyed()) return;
  const kids = mainWindow.contentView.children;
  if (kids[kids.length - 1] !== popupLayer) mainWindow.contentView.addChildView(popupLayer);
}

function hidePopupLayer() {
  popupShown = false;
  popupPayload = null;
  if (popupLayer && mainWindow && !mainWindow.isDestroyed()) {
    try { mainWindow.contentView.removeChildView(popupLayer); } catch { /* not attached */ }
  }
}

const finite = (v) => typeof v === 'number' && Number.isFinite(v);

ipcMain.on('popup-show', (event, payload) => {
  if (!isAuthorizedSender(event) || !payload || typeof payload !== 'object') return;
  const r = payload.rect || {};
  if (![r.x, r.y, r.width, r.height].every(finite)) return;
  const win = mainWindow.getContentBounds();
  const bounds = {
    x: Math.max(0, Math.round(r.x)),
    y: Math.max(0, Math.round(r.y)),
    width: Math.max(1, Math.min(Math.round(r.width), win.width)),
    height: Math.max(1, Math.min(Math.round(r.height), win.height)),
  };
  const layer = ensurePopupLayer();
  layer.setBounds(bounds);
  popupPayload = { kind: String(payload.kind || ''), items: Array.isArray(payload.items) ? payload.items.slice(0, 12) : [], selected: payload.selected | 0, card: payload.card || null, theme: payload.theme || {} };
  if (popupReady) layer.webContents.send('popup-render', popupPayload);
  popupShown = true;
  raisePopupLayer();
});

ipcMain.on('popup-hide', (event) => {
  if (!isAuthorizedSender(event)) return;
  hidePopupLayer();
});

ipcMain.on('popup-pick', (event, index) => {
  if (!popupLayer || event.sender !== popupLayer.webContents) return;
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('popup-event', { type: 'pick', index: index | 0 });
});

// ---------------------------------------------------------------------------------------------
// Interface IPC: state, commands, bounds.
// ---------------------------------------------------------------------------------------------
const validId = (v) => typeof v === 'string' && ID_PATTERN.test(v);
const optId = (v) => (v === undefined || v === null ? undefined : validId(v) ? v : null);

ipcMain.handle('browser-state', (event) => {
  if (!isAuthorizedSender(event)) throw new Error('Unauthorized sender');
  return browserState();
});

ipcMain.handle('browser-command', async (event, cmd = {}) => {
  if (!isAuthorizedSender(event)) throw new Error('Unauthorized sender');
  const tabId = cmd.tabId === undefined ? manager.activeTabId : cmd.tabId;
  const tid = validId(tabId) ? tabId : null;
  switch (cmd.type) {
    case 'new-tab': {
      const groupId = optId(cmd.groupId);
      const after = optId(cmd.after);
      if (groupId === null || after === null) return null;
      const url = typeof cmd.url === 'string' && (INTERNAL_URLS.has(cmd.url) || isSafeNavigationUrl(cmd.url)) ? cmd.url : LAUNCHPAD;
      return newTab({ url, groupId, after, activate: cmd.activate !== false }).id;
    }
    case 'activate': return tid ? manager.setActive(tid) : false;
    case 'close-tab': if (tid) closeTab(tid); return true;
    case 'close-tabs': {
      const ids = Array.isArray(cmd.tabIds) ? cmd.tabIds.filter(validId) : [];
      manager.closeTabs(ids, optId(cmd.focusId) || null);
      return true;
    }
    case 'close-group': return validId(cmd.groupId) ? closeGroup(cmd.groupId, { confirm: cmd.confirm !== false }) : false;
    case 'navigate': if (tid) navigate(tid, cmd.url); return true;
    case 'back': case 'forward': case 'stop': case 'reload': case 'hard-reload':
      if (tid && tid !== manager.activeTabId) manager.setActive(tid);
      COMMANDS[cmd.type]();
      return true;
    case 'move-tab':
      if (!tid) return false;
      moveTab(tid, { index: Number.isInteger(cmd.index) ? cmd.index : undefined, groupId: optId(cmd.groupId) || undefined, ungroup: cmd.ungroup === true });
      return true;
    case 'move-group': return validId(cmd.groupId) && Number.isInteger(cmd.index) ? manager.moveGroup(cmd.groupId, cmd.index) : false;
    case 'create-group': {
      const ids = Array.isArray(cmd.tabIds) ? cmd.tabIds.filter(validId) : [];
      return ids.length ? createGroup(ids, typeof cmd.name === 'string' ? cmd.name : '', cmd.color).id : null;
    }
    case 'rename-group': return validId(cmd.groupId) ? manager.renameGroup(cmd.groupId, String(cmd.name || '')) : false;
    case 'set-group-color': return validId(cmd.groupId) ? manager.setGroupColor(cmd.groupId, cmd.color) : false;
    case 'set-group-collapsed': return validId(cmd.groupId) ? manager.setGroupCollapsed(cmd.groupId, cmd.collapsed === true) : false;
    case 'ungroup': if (validId(cmd.groupId)) ungroup(cmd.groupId); return true;
    case 'reopen-closed': return manager.reopenClosed().map((t) => t.id);
    case 'duplicate': return tid ? manager.duplicateTab(tid)?.id : null;
    case 'dismiss-notice': return tid ? manager.updateTab(tid, { notice: null }) : false;
    case 'open-external':
      // Only web addresses, only from the interface: used by "Open in default browser" on the sign-in notice.
      if (isHttpUrl(cmd.url)) await shell.openExternal(cmd.url);
      return true;
    case 'toggle-bookmark': {
      if (!isHttpUrl(cmd.url)) return false;
      const on = bookmarks.toggle(cmd.url, typeof cmd.title === 'string' ? cmd.title : '');
      bookmarksFile.write(bookmarks.toJSON());
      pushState();
      return on;
    }
    case 'history-query': return history.query(typeof cmd.text === 'string' ? cmd.text.slice(0, 200) : '', 6);
    case 'context-menu':
      if (cmd.kind === 'tab' && tid) showTabMenu(tid);
      else if (cmd.kind === 'group' && validId(cmd.groupId)) showGroupMenu(cmd.groupId);
      else if (cmd.kind === 'bookmark' && isHttpUrl(cmd.url)) showBookmarkMenu(cmd.url);
      return true;
    case 'shortcut': if (typeof cmd.id === 'string' && COMMANDS[cmd.id]) COMMANDS[cmd.id](); return true;
    default:
      return null;
  }
});

// Test hook (only with COMEX_TEST_HOOKS=1, for the isolated live-test instance): send a key press into a tab's page
// through Electron's input pipeline, the way a real key press arrives, to check that shortcuts work from inside pages.
if (process.env.COMEX_TEST_HOOKS === '1') {
  ipcMain.handle('test-send-key', (event, { tabId, keyCode, modifiers = [] } = {}) => {
    if (!isAuthorizedSender(event)) throw new Error('Unauthorized sender');
    const view = views.get(tabId === 'ui' ? null : tabId);
    const wc = tabId === 'ui' ? mainWindow.webContents : view?.webContents;
    if (!wc) return false;
    wc.focus();
    wc.sendInputEvent({ type: 'keyDown', keyCode, modifiers });
    wc.sendInputEvent({ type: 'char', keyCode, modifiers });
    wc.sendInputEvent({ type: 'keyUp', keyCode, modifiers });
    return true;
  });
}

ipcMain.on('tabs-set-bounds', (event, bounds) => {
  if (!isAuthorizedSender(event) || !bounds || typeof bounds !== 'object') return;
  currentBounds = {
    x: finite(bounds.x) ? bounds.x : 0,
    y: finite(bounds.y) ? bounds.y : 0,
    width: finite(bounds.width) ? bounds.width : 0,
    height: finite(bounds.height) ? bounds.height : 0,
    isHidden: bounds.isHidden === true,
  };
  syncActiveView();
});

// ---------------------------------------------------------------------------------------------
// Agent backend IPC (called by the agent service through the interface page over CDP).
// ---------------------------------------------------------------------------------------------

// Visible tab opened for a multi-agent worker: shown in its chat's group so the user can watch it.
ipcMain.handle('tabs-open-agent', async (event, { tabId, url, label, groupId } = {}) => {
  if (!isAuthorizedSender(event)) throw new Error('Unauthorized sender');
  if (typeof tabId !== 'string' || !AGENT_TAB_ID_PATTERN.test(tabId)) throw new Error('Invalid agent tab id');
  if (manager.tab(tabId)) throw new Error(`Tab ${tabId} already exists`);
  const safeLabel = typeof label === 'string' ? label.slice(0, 120) : '';
  const safeGroup = typeof groupId === 'string' && AGENT_TAB_ID_PATTERN.test(groupId) ? groupId : undefined;
  const safeUrl = typeof url === 'string' && isSafeNavigationUrl(url) ? url : LAUNCHPAD;
  // Bring the work into view only if you are looking at this chat's group and no other agent of it is shown yet.
  const viewingGroup = safeGroup && activeTab()?.groupId === safeGroup;
  const othersWorking = safeGroup && manager.tabsInGroup(safeGroup).some((id) => manager.tab(id).kind === 'agent' && manager.tab(id).agent?.status === 'working');
  const tab = manager.createTab({
    id: tabId,
    url: safeUrl,
    groupId: safeGroup,
    kind: 'agent',
    title: safeLabel,
    activate: Boolean(viewingGroup && !othersWorking),
    agent: { status: 'working', step: safeLabel, label: safeLabel, since: Date.now() },
  });
  // A worker tab exists to be worked in: it is marked working from the moment it opens.
  agentOverlays.set(tabId, { status: 'working', step: safeLabel, holdUntil: 0 });
  const view = ensureView(tab.id);
  return getDevToolsTargetId(view.webContents);
});

// One tab's debugging target, address and title, so the backend can let a group's agent move to that tab.
ipcMain.handle('tabs-get-info', async (event, tabId) => {
  if (!isAuthorizedSender(event)) throw new Error('Unauthorized sender');
  if (!validId(tabId) || !manager.tab(tabId)) return null;
  const view = ensureView(tabId);
  if (gone(view)) return null;
  return {
    tabId,
    targetId: await getDevToolsTargetId(view.webContents),
    url: view.webContents.getURL(),
    title: view.webContents.getTitle(),
  };
});

// The agent moved to another tab of its group: show that tab.
ipcMain.on('tabs-request-activate', (event, tabId) => {
  if (!isAuthorizedSender(event)) return;
  if (validId(tabId)) manager.setActive(tabId);
});

const cleanStep = (step) => (typeof step === 'string' ? step.replace(/\s+/g, ' ').trim().slice(0, 120) : '');

ipcMain.on('tabs-set-agent-status', (event, tabId, status, step) => {
  if (!isAuthorizedSender(event)) return;
  const tab = validId(tabId) ? manager.tab(tabId) : null;
  if (!tab) return;
  const children = [...agentOverlays.entries()].filter(([, child]) => child.parent === tabId).map(([id]) => id);
  // "idle" clears the marker (used a few seconds after a single-agent run ends in the user's own tab)
  if (status === 'idle') {
    agentOverlays.delete(tabId);
    manager.updateTab(tabId, { agent: null });
    for (const id of children) { agentOverlays.delete(id); manager.updateTab(id, { agent: null }); }
    updateAgentShield();
    return;
  }
  if (!AGENT_TAB_STATUSES.has(status)) return;
  const prev = agentOverlays.get(tabId);
  const nextStep = status === 'working' ? (cleanStep(step) || (prev && prev.status === 'working' ? prev.step : '')) : '';
  // A finished agent keeps the shield up for a moment so the result ("Done") is seen, then lets go.
  const holdUntil = status === 'working' ? 0 : Date.now() + 1500;
  agentOverlays.set(tabId, { status, step: nextStep, holdUntil });
  const since = status === 'working' && tab.agent?.status === 'working' ? tab.agent.since : Date.now();
  manager.updateTab(tabId, { agent: { status, step: nextStep, label: tab.agent?.label || '', since } });
  for (const id of children) {
    agentOverlays.set(id, { status, step: nextStep, holdUntil, parent: tabId });
    manager.updateTab(id, { agent: { status, step: nextStep, label: '', since } });
  }
  updateAgentShield();
  if (holdUntil) setTimeout(updateAgentShield, 1560);
});

// Which tab the user is looking at, as a debugging target id. The backend asks for this at the start of a run so a
// single agent works in the tab on screen, instead of guessing from the order of Chrome's target list.
ipcMain.handle('tabs-get-active-target', async (event) => {
  if (!isAuthorizedSender(event)) throw new Error('Unauthorized sender');
  // The Launchpad tab has a blank page too: a single agent started there works in it.
  const view = ensureView(manager.activeTabId);
  if (gone(view)) return null;
  return { tabId: manager.activeTabId, targetId: await getDevToolsTargetId(view.webContents) };
});

// The Stop button on the shield: hand the request to the React shell, which owns stopping agents.
ipcMain.on('agent-shield-stop', (event) => {
  if (gone(agentShield) || event.sender !== agentShield.webContents) return;
  uiCommand('agent-stop', { tabId: manager.activeTabId });
});

// Live step text for a working agent; ignored unless the tab is currently marked as working, so a late
// progress event can never flip a finished tab back to "working".
ipcMain.on('tabs-set-agent-step', (event, tabId, step) => {
  if (!isAuthorizedSender(event)) return;
  const state = agentOverlays.get(tabId);
  const tab = manager.tab(tabId);
  if (!state || state.status !== 'working' || !tab) return;
  const next = cleanStep(step);
  if (!next || next === state.step) return;
  state.step = next;
  manager.updateTab(tabId, { agent: { ...(tab.agent || {}), status: 'working', step: next } });
  if (tabId === manager.activeTabId) pushAgentShieldState();
});

ipcMain.on('cursor-animate', (event, data) => {
  if (!isAuthorizedSender(event)) return;
  if (!isVisualCursorEnabled) return;
  if (!cursorWindow || cursorWindow.isDestroyed()) {
    createCursorWindow();
  }
  if (!cursorWindow || cursorWindow.isDestroyed()) {
    console.error('[CURSOR] Could not create cursorWindow!');
    return;
  }

  // Background-tab filtering: only animate if event is for the active foreground tab
  const isTargetActive = !data?.tabId || data.tabId === 'active_tab' || data.tabId === manager.activeTabId;
  if (!isTargetActive) return;
  // Coordinate translation: currentBounds.x + target_x, currentBounds.y + target_y
  cursorWindow.webContents.send('cursor-animate', {
    x: Math.round((currentBounds.x || 0) + (data?.x || 0)),
    y: Math.round((currentBounds.y || 0) + (data?.y || 0)),
    action: data?.action || 'click',
  });
});

ipcMain.on('cursor-reset', (event) => {
  if (!isAuthorizedSender(event)) return;
  resetVisualCursor();
});

// ============================================================================
// Narrowly Scoped Main-Process Agent Request Proxy
// Attaches internalAppToken strictly within trusted main process code.
// The renderer never receives the reusable internal application credential.
// ============================================================================

function cleanAgentPayload(payload) {
  const cleanPayload = { ...payload };
  delete cleanPayload.contextToken; // Remove any renderer-provided credential field
  delete cleanPayload.workerId;     // Renderer initiates user tasks, never worker impersonation
  delete cleanPayload.workerToken;
  if (!cleanPayload.tabId || cleanPayload.tabId === manager.activeTabId) {
    cleanPayload.tabId = 'active_tab';
  }
  return cleanPayload;
}

ipcMain.handle('agent-run', async (event, payload) => {
  if (!isAuthorizedSender(event)) {
    throw new Error('Unauthorized IPC sender');
  }
  if (!payload || typeof payload !== 'object' || typeof payload.task !== 'string') {
    throw new Error('Invalid request payload schema: task is required.');
  }
  if (!internalAppToken) {
    throw new Error('COMEX_INTERNAL_APP_TOKEN is not configured (fail closed).');
  }
  const resp = await fetch(`${AGENT_URL}/agent/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Comex-Internal-Token': internalAppToken },
    body: JSON.stringify(cleanAgentPayload(payload)),
  });
  return await resp.json();
});

ipcMain.handle('agent-stop', async (event, taskId) => {
  if (!isAuthorizedSender(event)) throw new Error('Unauthorized IPC sender');
  if (typeof taskId !== 'string' || !taskId) throw new Error('Invalid taskId');
  if (!internalAppToken) throw new Error('COMEX_INTERNAL_APP_TOKEN is not configured (fail closed).');

  const resp = await fetch(`${AGENT_URL}/agent/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Comex-Internal-Token': internalAppToken },
    body: JSON.stringify({ taskId }),
  });
  return await resp.json();
});

const activeAgentStreams = new Map();

ipcMain.handle('agent-stream-start', async (event, { streamId, payload }) => {
  if (!isAuthorizedSender(event)) throw new Error('Unauthorized IPC sender');
  if (typeof streamId !== 'string' || !streamId) throw new Error('Invalid streamId');
  if (!payload || typeof payload !== 'object' || typeof payload.task !== 'string') {
    throw new Error('Invalid request payload schema: task is required.');
  }
  if (!internalAppToken) {
    throw new Error('COMEX_INTERNAL_APP_TOKEN is not configured (fail closed).');
  }

  const controller = new AbortController();
  activeAgentStreams.set(streamId, controller);

  try {
    const resp = await fetch(`${AGENT_URL}/agent/run/stream`, {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', 'X-Comex-Internal-Token': internalAppToken },
      body: JSON.stringify(cleanAgentPayload(payload)),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(`agent-stream-error:${streamId}`, `HTTP ${resp.status}: ${errText}`);
      }
      activeAgentStreams.delete(streamId);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const textChunk = decoder.decode(value, { stream: true });
      if (!mainWindow || mainWindow.isDestroyed()) break;
      mainWindow.webContents.send(`agent-stream-chunk:${streamId}`, textChunk);
    }

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send(`agent-stream-end:${streamId}`);
    }
  } catch (err) {
    if (err.name !== 'AbortError' && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send(`agent-stream-error:${streamId}`, err.message || String(err));
    }
  } finally {
    activeAgentStreams.delete(streamId);
  }
});

ipcMain.on('agent-stream-abort', (event, streamId) => {
  if (!isAuthorizedSender(event)) return;
  const controller = activeAgentStreams.get(streamId);
  if (controller) {
    controller.abort();
    activeAgentStreams.delete(streamId);
  }
});
