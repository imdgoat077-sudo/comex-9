import { useCallback, useEffect, useRef, useState } from 'react';
import { TabManager, LAUNCHPAD } from '../../electron/tab_manager.js';

/**
 * The browser state and its commands. In Electron the main process owns tabs and groups: this hook renders its
 * snapshots and sends commands. Opened without Electron (the preview harness), the same TabManager runs here instead,
 * without real pages, so the interface behaves the same.
 */
const native = () => (typeof window !== 'undefined' ? window.nexusNative?.browser : undefined);

function hostTitle(url) {
  if (!url || url === LAUNCHPAD) return 'New Tab';
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
}

/** The preview stand-in for the main process: the same TabManager and the commands that make sense without pages. */
function createLocalHost(onState) {
  const m = TabManager.fresh();
  let bookmarks = [
    { url: 'https://www.google.com/', title: 'Google' },
    { url: 'https://github.com/', title: 'GitHub' },
    { url: 'https://www.wikipedia.org/', title: 'Wikipedia' },
  ];
  const emit = () => onState({ session: m.snapshot(), bookmarks });
  m.subscribe((e) => { if (e.type === 'changed') emit(); });
  const commands = {
    'new-tab': (c) => m.createTab({ url: c.url || LAUNCHPAD, groupId: c.groupId && m.group(c.groupId) ? c.groupId : undefined, after: c.after, activate: c.activate !== false, title: hostTitle(c.url) }).id,
    activate: (c) => m.setActive(c.tabId),
    'close-tab': (c) => m.closeTab(c.tabId),
    'close-tabs': (c) => m.closeTabs(c.tabIds || [], c.focusId || null),
    'close-group': (c) => m.closeGroup(c.groupId),
    navigate: (c) => m.updateTab(c.tabId, { url: c.url === LAUNCHPAD ? LAUNCHPAD : c.url, title: hostTitle(c.url), error: null }),
    'move-tab': (c) => m.moveTab(c.tabId, c),
    'move-group': (c) => m.moveGroup(c.groupId, c.index),
    'create-group': (c) => m.createGroup({ tabIds: c.tabIds, name: c.name, color: c.color }).group.id,
    'rename-group': (c) => m.renameGroup(c.groupId, c.name),
    'set-group-color': (c) => m.setGroupColor(c.groupId, c.color),
    'set-group-collapsed': (c) => m.setGroupCollapsed(c.groupId, c.collapsed),
    ungroup: (c) => m.ungroup(c.groupId),
    'reopen-closed': () => m.reopenClosed().map((t) => t.id),
    duplicate: (c) => m.duplicateTab(c.tabId)?.id,
    'dismiss-notice': (c) => m.updateTab(c.tabId, { notice: null }),
    'toggle-bookmark': (c) => {
      const has = bookmarks.some((b) => b.url === c.url);
      bookmarks = has ? bookmarks.filter((b) => b.url !== c.url) : [...bookmarks, { url: c.url, title: c.title || c.url }];
      emit();
      return !has;
    },
    'history-query': () => [],
  };
  return {
    manager: m,
    getState: async () => ({ session: m.snapshot(), bookmarks }),
    command: async (c) => {
      const fn = commands[c.type];
      const tabId = c.tabId === undefined ? m.activeTabId : c.tabId;
      return fn ? fn({ ...c, tabId }) : null;
    },
  };
}

export function useBrowser() {
  const [state, setState] = useState(null);
  const hostRef = useRef(null);

  useEffect(() => {
    const bridge = native();
    if (bridge) {
      let alive = true;
      const off = bridge.onState((s) => { if (alive) setState(s); });
      bridge.getState().then((s) => { if (alive) setState((prev) => prev || s); });
      hostRef.current = { command: (c) => bridge.command(c) };
      return () => { alive = false; off(); };
    }
    const host = createLocalHost(setState);
    hostRef.current = host;
    window.__comexPreviewTabs = host.manager; // the preview harness drives tabs through this
    host.getState().then(setState);
    return undefined;
  }, []);

  const command = useCallback((cmd) => hostRef.current?.command(cmd) ?? Promise.resolve(null), []);
  return { state, command, isNative: Boolean(native()) };
}

/** Interface commands sent by the main process (shortcuts, menus): focus the address bar, rename a group... */
export function useUiCommands(handlers) {
  const ref = useRef(handlers);
  ref.current = handlers;
  useEffect(() => {
    const bridge = native();
    if (!bridge) return undefined;
    return bridge.onUiCommand((cmd) => ref.current[cmd?.type]?.(cmd));
  }, []);
}
