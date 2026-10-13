/**
 * The browser's tabs and tab groups: the single source of truth.
 *
 * It lives in the Electron main process; the interface renders its snapshots and sends commands. It is plain logic
 * with no Electron imports, so it is unit-tested with `node --test` and also runs inside the page when Comex is opened
 * without Electron (the preview harness).
 *
 * Invariants, kept by every operation:
 *   1. there is at least one tab;
 *   2. every tab belongs to exactly one existing group, and a group with no tabs is deleted;
 *   3. a group's tabs are contiguous in `order`;
 *   4. the active tab exists and is not inside a collapsed group.
 *
 * A group is an identity of its own ({id, name, color, collapsed}); it knows nothing about chats. The agent backend maps
 * a group id to its conversation. A tab the user opens gets a group of its own with no name (shown as a plain tab);
 * a group is shown as a group once it has a name or more than one tab.
 */

export const LAUNCHPAD = 'comex://launchpad';
export const GROUP_COLORS = ['blue', 'red', 'yellow', 'green', 'pink', 'purple', 'cyan', 'orange', 'grey'];
export const ID_PATTERN = /^[A-Za-z0-9_\-:.]{1,100}$/;
const MAX_CLOSED = 25;
const MAX_NAME = 60;
const TAB_FIELDS = ['url', 'title', 'favicon', 'loading', 'canGoBack', 'canGoForward', 'audible', 'error', 'notice', 'agent', 'discarded'];

const newUuid = () => globalThis.crypto.randomUUID();

/** A URL a restored tab may open; anything else restores as the Launchpad. */
export function isRestorableUrl(url) {
  if (url === LAUNCHPAD) return true;
  try {
    const u = new URL(url);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

export class TabManager {
  constructor({ newId = newUuid, now = Date.now } = {}) {
    this._newId = newId;
    this._now = now;
    this.tabs = new Map();
    this.groups = new Map();
    this.order = [];
    this.activeTabId = null;
    this.closed = [];
    this._listeners = new Set();
    this._colorTurn = 0;
  }

  /** Start with one Launchpad tab (a fresh browser). */
  static fresh(opts) {
    const m = new TabManager(opts);
    m.createTab({ url: LAUNCHPAD });
    return m;
  }

  // ── events ──────────────────────────────────────────────────────────────────────────────────────

  /** fn({type, ...}) for 'tab-created' {tab}, 'tab-closed' {tab}, 'activated' {tabId, previous}, 'changed'. */
  subscribe(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }

  _emit(event) {
    for (const fn of this._listeners) fn(event);
  }

  _changed() {
    this._emit({ type: 'changed' });
  }

  // ── queries ─────────────────────────────────────────────────────────────────────────────────────

  tab(id) {
    return this.tabs.get(id) || null;
  }

  group(id) {
    return this.groups.get(id) || null;
  }

  tabsInGroup(groupId) {
    return this.order.filter((id) => this.tabs.get(id).groupId === groupId);
  }

  /** [start, end] indexes of a group's block in `order`, or null. */
  _block(groupId) {
    const start = this.order.findIndex((id) => this.tabs.get(id).groupId === groupId);
    if (start < 0) return null;
    let end = start;
    while (end + 1 < this.order.length && this.tabs.get(this.order[end + 1]).groupId === groupId) end += 1;
    return [start, end];
  }

  /** A group the interface shows as a group (named, or holding several tabs). */
  isShownGroup(groupId) {
    const g = this.groups.get(groupId);
    return Boolean(g) && (Boolean(g.name) || this.tabsInGroup(groupId).length > 1);
  }

  snapshot() {
    const seen = new Set();
    const groups = [];
    for (const id of this.order) {
      const gid = this.tabs.get(id).groupId;
      if (!seen.has(gid)) {
        seen.add(gid);
        groups.push({ ...this.groups.get(gid), shown: this.isShownGroup(gid), size: this.tabsInGroup(gid).length });
      }
    }
    const last = this.closed[this.closed.length - 1];
    return {
      tabs: this.order.map((id) => publicTab(this.tabs.get(id))),
      groups,
      activeTabId: this.activeTabId,
      canReopen: this.closed.length > 0,
      lastClosed: last ? { type: last.type, name: last.group?.name || last.tabs[0]?.title || '', count: last.tabs.length } : null,
    };
  }

  // ── persistence ─────────────────────────────────────────────────────────────────────────────────

  serialize() {
    return {
      version: 1,
      activeTabId: this.activeTabId,
      groups: [...this.groups.values()].map(({ id, name, color, collapsed, createdAt }) => ({ id, name, color, collapsed, createdAt })),
      tabs: this.order.map((id) => {
        const t = this.tabs.get(id);
        const url = t.error?.url || t.url;
        return { id: t.id, groupId: t.groupId, url, title: t.title, favicon: t.favicon, kind: t.kind };
      }),
    };
  }

  /**
   * Rebuild from serialize() output. Anything malformed is dropped, never trusted: unknown fields, bad ids, unsafe URLs
   * (restored as the Launchpad), tabs of missing groups (given a group of their own). Restored tabs are "discarded":
   * their pages load when first shown, so a restart does not load every tab at once.
   */
  static restore(data, opts) {
    const m = new TabManager(opts);
    if (!data || data.version !== 1 || !Array.isArray(data.tabs)) return TabManager.fresh(opts);
    for (const g of Array.isArray(data.groups) ? data.groups : []) {
      if (!g || !ID_PATTERN.test(g.id || '') || m.groups.has(g.id)) continue;
      m.groups.set(g.id, {
        id: g.id,
        name: typeof g.name === 'string' ? g.name.slice(0, MAX_NAME) : '',
        color: GROUP_COLORS.includes(g.color) ? g.color : GROUP_COLORS[0],
        collapsed: g.collapsed === true,
        createdAt: Number.isFinite(g.createdAt) ? g.createdAt : m._now(),
      });
    }
    for (const t of data.tabs) {
      if (!t || !ID_PATTERN.test(t.id || '') || m.tabs.has(t.id)) continue;
      const groupId = m.groups.has(t.groupId) ? t.groupId : m._addGroup().id;
      m.tabs.set(t.id, makeTab({
        id: t.id,
        groupId,
        url: isRestorableUrl(t.url) ? t.url : LAUNCHPAD,
        title: typeof t.title === 'string' ? t.title.slice(0, 300) : '',
        favicon: typeof t.favicon === 'string' && /^https?:|^data:image\//.test(t.favicon) ? t.favicon : null,
        kind: t.kind === 'agent' ? 'agent' : 'user',
        discarded: true,
        createdAt: m._now(),
      }));
      m.order.push(t.id);
    }
    if (!m.order.length) return TabManager.fresh(opts);
    // contiguity: each group's tabs move up to its first tab (a stable regroup)
    const firstIndex = new Map();
    m.order.forEach((id, i) => { const g = m.tabs.get(id).groupId; if (!firstIndex.has(g)) firstIndex.set(g, i); });
    m.order = m.order.map((id, i) => [id, i]).sort((a, b) => {
      const ga = firstIndex.get(m.tabs.get(a[0]).groupId);
      const gb = firstIndex.get(m.tabs.get(b[0]).groupId);
      return ga - gb || a[1] - b[1];
    }).map(([id]) => id);
    for (const gid of [...m.groups.keys()]) if (!m.tabsInGroup(gid).length) m.groups.delete(gid);
    m._colorTurn = m.groups.size;
    const active = m.tabs.has(data.activeTabId) ? data.activeTabId : m.order[0];
    m.activeTabId = active;
    m.groups.get(m.tabs.get(active).groupId).collapsed = false;
    m.tabs.get(active).discarded = false;
    return m;
  }

  // ── groups ──────────────────────────────────────────────────────────────────────────────────────

  _addGroup({ id, name = '', color } = {}) {
    const gid = id && ID_PATTERN.test(id) && !this.groups.has(id) ? id : `g-${this._newId()}`;
    const g = {
      id: gid,
      name: (name || '').trim().slice(0, MAX_NAME),
      color: GROUP_COLORS.includes(color) ? color : GROUP_COLORS[this._colorTurn++ % GROUP_COLORS.length],
      collapsed: false,
      createdAt: this._now(),
    };
    this.groups.set(gid, g);
    return g;
  }

  _dropGroupIfEmpty(groupId) {
    if (this.groups.has(groupId) && !this.tabsInGroup(groupId).length) {
      this.groups.delete(groupId);
      return true;
    }
    return false;
  }

  /** Put the given tabs in a new group, together where the first of them is. */
  createGroup({ tabIds = [], name = '', color } = {}) {
    const ids = this.order.filter((id) => tabIds.includes(id));
    if (!ids.length) throw new Error('A group needs at least one tab.');
    const g = this._addGroup({ name, color });
    const at = this.order.indexOf(ids[0]);
    const before = this.order.slice(0, at).filter((id) => !ids.includes(id)).length;
    const oldGroups = new Set(ids.map((id) => this.tabs.get(id).groupId));
    this.order = this.order.filter((id) => !ids.includes(id));
    for (const id of ids) this.tabs.get(id).groupId = g.id;
    this.order.splice(this._safeIndex(before, g.id), 0, ...ids);
    const emptied = [...oldGroups].filter((gid) => this._dropGroupIfEmpty(gid));
    this._repairActive();
    this._changed();
    return { group: g, emptied };
  }

  renameGroup(groupId, name) {
    const g = this.groups.get(groupId);
    if (!g) return false;
    g.name = String(name || '').trim().slice(0, MAX_NAME);
    this._changed();
    return true;
  }

  setGroupColor(groupId, color) {
    const g = this.groups.get(groupId);
    if (!g || !GROUP_COLORS.includes(color)) return false;
    g.color = color;
    this._changed();
    return true;
  }

  /** Collapse or expand. Collapsing the active tab's group moves you to a neighbouring tab outside it (none: refused). */
  setGroupCollapsed(groupId, collapsed) {
    const g = this.groups.get(groupId);
    if (!g) return false;
    if (collapsed && this.tabs.get(this.activeTabId)?.groupId === groupId) {
      const outside = this._neighbourOutside(groupId);
      if (!outside) return false;
      this._activate(outside);
    }
    g.collapsed = Boolean(collapsed);
    this._changed();
    return true;
  }

  /** Dissolve a group: the first tab keeps the group (and so its chat) without a name; the others get their own. */
  ungroup(groupId) {
    const ids = this.tabsInGroup(groupId);
    if (!ids.length) return [];
    const g = this.groups.get(groupId);
    g.name = '';
    g.collapsed = false;
    const created = [];
    for (const id of ids.slice(1)) {
      const solo = this._addGroup();
      this.tabs.get(id).groupId = solo.id;
      created.push({ tabId: id, groupId: solo.id });
    }
    this._changed();
    return created;
  }

  /** Move a whole group so that it starts at `index` (counted without the group's own tabs). */
  moveGroup(groupId, index) {
    const ids = this.tabsInGroup(groupId);
    if (!ids.length) return false;
    this.order = this.order.filter((id) => !ids.includes(id));
    this.order.splice(this._safeIndex(index, groupId), 0, ...ids);
    this._changed();
    return true;
  }

  // ── tabs ────────────────────────────────────────────────────────────────────────────────────────

  /**
   * Open a tab. Without a group it gets a group of its own; with a group id it joins that group (created if the id is
   * new: an agent's tab names its chat's group). It goes after `after` when given, else at the end of its group, else
   * at `index`, else at the end; never in the middle of another group.
   */
  createTab({ url = LAUNCHPAD, groupId, index, after, activate = true, kind = 'user', id, title = '', agent = null, discarded = false } = {}) {
    if (id !== undefined && (!ID_PATTERN.test(id) || this.tabs.has(id))) throw new Error(`Invalid or duplicate tab id: ${id}`);
    let g = groupId && this.groups.get(groupId);
    if (!g) g = this._addGroup({ id: groupId });
    const tab = makeTab({
      id: id || `t-${this._newId()}`,
      groupId: g.id,
      url: url || LAUNCHPAD,
      title,
      kind: kind === 'agent' ? 'agent' : kind === 'popup' ? 'popup' : 'user',
      agent,
      discarded,
      createdAt: this._now(),
      loading: !discarded && url !== LAUNCHPAD,
    });
    const block = this._block(g.id);
    let at;
    if (after && this.tabs.has(after) && this.tabs.get(after).groupId === g.id) at = this.order.indexOf(after) + 1;
    else if (block) at = block[1] + 1;
    else if (after && this.tabs.has(after)) at = this._safeIndex(this.order.indexOf(after) + 1, g.id);
    else if (Number.isInteger(index)) at = this._safeIndex(index, g.id);
    else at = this.order.length;
    this.tabs.set(tab.id, tab);
    this.order.splice(at, 0, tab.id);
    this._emit({ type: 'tab-created', tab });
    if (activate || !this.activeTabId) this._activate(tab.id);
    this._changed();
    return tab;
  }

  duplicateTab(id) {
    const t = this.tabs.get(id);
    if (!t) return null;
    return this.createTab({ url: t.error?.url || t.url, groupId: t.groupId, after: id, title: t.title });
  }

  setActive(id) {
    if (!this.tabs.has(id) || id === this.activeTabId) return false;
    this._activate(id);
    this._changed();
    return true;
  }

  _activate(id) {
    const previous = this.activeTabId;
    const t = this.tabs.get(id);
    this.groups.get(t.groupId).collapsed = false;
    t.discarded = false;
    this.activeTabId = id;
    this._emit({ type: 'activated', tabId: id, previous });
  }

  /** Change what a tab shows (title, loading, agent state...). Only known fields; returns whether anything changed. */
  updateTab(id, patch = {}) {
    const t = this.tabs.get(id);
    if (!t) return false;
    let changed = false;
    for (const key of TAB_FIELDS) {
      if (!(key in patch)) continue;
      const value = patch[key];
      if (JSON.stringify(t[key]) === JSON.stringify(value)) continue;
      t[key] = value;
      changed = true;
    }
    if (changed) this._changed();
    return changed;
  }

  /**
   * Move a tab: into another group (`groupId`), out of its group (`ungroup`), and/or to `index` (counted without the
   * tab itself). Returns {fromGroup, toGroup, emptied}: the backend moves the tab's chat membership accordingly.
   */
  moveTab(id, { index, groupId, ungroup = false } = {}) {
    const t = this.tabs.get(id);
    if (!t) return null;
    const fromGroup = t.groupId;
    const oldIndex = this.order.indexOf(id);
    let toGroup = fromGroup;
    if (ungroup) {
      if (this.tabsInGroup(fromGroup).length > 1) toGroup = this._addGroup().id;
      else this.groups.get(fromGroup).name = '';
    } else if (groupId && groupId !== fromGroup) {
      if (!this.groups.has(groupId)) return null;
      toGroup = groupId;
    }
    this.order.splice(oldIndex, 1);
    t.groupId = toGroup;
    let at;
    const block = this._block(toGroup);
    if (block) {
      const wanted = Number.isInteger(index) ? index : block[1] + 1;
      at = Math.min(Math.max(wanted, block[0]), block[1] + 1);
    } else {
      // leaving a group: just past its block, unless an index says where
      const fromBlock = this._block(fromGroup);
      const fallback = fromBlock && toGroup !== fromGroup ? fromBlock[1] + 1 : oldIndex;
      at = this._safeIndex(Number.isInteger(index) ? index : fallback, toGroup);
    }
    this.order.splice(at, 0, id);
    const emptied = toGroup !== fromGroup && this._dropGroupIfEmpty(fromGroup) ? fromGroup : null;
    if (this.activeTabId === id) this.groups.get(toGroup).collapsed = false;
    this._repairActive();
    this._changed();
    return { fromGroup, toGroup, emptied };
  }

  /** Close a tab. The last tab is replaced by a fresh Launchpad tab. Returns {tab, emptiedGroup} or null. */
  closeTab(id, { record = true } = {}) {
    const tab = this.tabs.get(id);
    if (!tab) return null;
    const idx = this.order.indexOf(id);
    if (record) this._remember({ type: 'tab', tabs: [this._record(tab, idx)] });
    if (this.order.length === 1) this.createTab({ url: LAUNCHPAD, activate: true });
    const wasActive = this.activeTabId === id;
    this.order.splice(this.order.indexOf(id), 1);
    this.tabs.delete(id);
    const emptiedGroup = this._dropGroupIfEmpty(tab.groupId) ? tab.groupId : null;
    if (wasActive) this._activate(this._pickAfterClose(idx, tab.groupId));
    this._emit({ type: 'tab-closed', tab });
    this._changed();
    return { tab, emptiedGroup };
  }

  /** Close several tabs at once (a run's leftover agent tabs) and optionally focus one that stays. */
  closeTabs(ids = [], focusId = null) {
    const closed = [];
    for (const id of ids) {
      if (id === focusId) continue;
      const res = this.closeTab(id);
      if (res) closed.push(res);
    }
    if (focusId && this.tabs.has(focusId)) this.setActive(focusId);
    return closed;
  }

  /** Close a group and all its tabs (remembered as one entry for reopen). Returns the closed tab ids. */
  closeGroup(groupId) {
    const ids = this.tabsInGroup(groupId);
    if (!ids.length) return [];
    const [start, end] = this._block(groupId);
    const group = { ...this.groups.get(groupId) };
    this._remember({ type: 'group', group, tabs: ids.map((id, i) => this._record(this.tabs.get(id), start + i)) });
    if (ids.length === this.order.length) this.createTab({ url: LAUNCHPAD, activate: true });
    const activeInside = ids.includes(this.activeTabId);
    const next = activeInside ? (this.order[end + 1] && !ids.includes(this.order[end + 1]) ? this.order[end + 1] : this.order[start - 1]) : null;
    const closedTabs = ids.map((id) => this.tabs.get(id));
    this.order = this.order.filter((id) => !ids.includes(id));
    for (const id of ids) this.tabs.delete(id);
    this.groups.delete(groupId);
    if (activeInside) this._activate(next && this.tabs.has(next) ? this._visible(next) : this.order[0]);
    for (const tab of closedTabs) this._emit({ type: 'tab-closed', tab });
    this._changed();
    return ids;
  }

  /** Reopen the last closed tab or group, in its group and place. Returns the reopened tabs. */
  reopenClosed() {
    const entry = this.closed.pop();
    if (!entry) return [];
    let groupId = entry.tabs[0].groupId;
    if (entry.type === 'group') {
      const g = entry.group;
      groupId = this._addGroup({ id: this.groups.has(g.id) ? undefined : g.id, name: g.name, color: g.color }).id;
    }
    const opened = [];
    for (const rec of entry.tabs) {
      // a closed tab goes back to its group; if that group is gone it is recreated with the same id (and so the same chat)
      const gid = entry.type === 'group' ? groupId : rec.groupId;
      const tab = this.createTab({
        url: rec.url, title: rec.title, groupId: gid, index: rec.index, activate: false, kind: rec.kind === 'agent' ? 'agent' : 'user',
        after: opened.length ? opened[opened.length - 1].id : undefined,
      });
      opened.push(tab);
    }
    this._activate(opened[0].id);
    this._changed();
    return opened;
  }

  // ── helpers ─────────────────────────────────────────────────────────────────────────────────────

  _record(tab, index) {
    return { url: tab.error?.url || tab.url, title: tab.title, groupId: tab.groupId, kind: tab.kind, index };
  }

  _remember(entry) {
    this.closed.push(entry);
    if (this.closed.length > MAX_CLOSED) this.closed.shift();
  }

  /** An insert position for a tab of `groupId` near `index` that does not split another group's block. */
  _safeIndex(index, groupId) {
    let at = Math.min(Math.max(Number.isInteger(index) ? index : this.order.length, 0), this.order.length);
    const left = at > 0 ? this.tabs.get(this.order[at - 1]).groupId : null;
    const right = at < this.order.length ? this.tabs.get(this.order[at]).groupId : null;
    if (left && left === right && left !== groupId) at = this._block(left)[1] + 1;
    return at;
  }

  /** After closing the tab at `idx`: the next tab of the same group, else the one to its right, else its left. */
  _pickAfterClose(idx, groupId) {
    const right = this.order[idx];
    const left = this.order[idx - 1];
    for (const id of [right, left]) if (id && this.tabs.get(id).groupId === groupId) return id;
    return this._visible(right || left || this.order[0]);
  }

  /** The tab itself if its group is expanded, else the nearest tab in an expanded group (expanding if none). */
  _visible(id) {
    const ok = (tid) => !this.groups.get(this.tabs.get(tid).groupId).collapsed;
    if (ok(id)) return id;
    const i = this.order.indexOf(id);
    for (let d = 1; d < this.order.length; d += 1) {
      for (const j of [i + d, i - d]) if (j >= 0 && j < this.order.length && ok(this.order[j])) return this.order[j];
    }
    return id; // every group is collapsed: _activate expands this one
  }

  _neighbourOutside(groupId) {
    const block = this._block(groupId);
    if (!block) return null;
    const candidates = [this.order[block[1] + 1], this.order[block[0] - 1]].filter(Boolean);
    for (const id of candidates) {
      const v = this._visible(id);
      if (this.tabs.get(v).groupId !== groupId) return v;
    }
    return null;
  }

  _repairActive() {
    if (!this.tabs.has(this.activeTabId)) this._activate(this.order[0]);
    else this.groups.get(this.tabs.get(this.activeTabId).groupId).collapsed = false;
  }
}

function makeTab(fields) {
  return {
    id: fields.id,
    groupId: fields.groupId,
    url: fields.url,
    title: fields.title || '',
    favicon: fields.favicon || null,
    kind: fields.kind || 'user',
    loading: Boolean(fields.loading),
    canGoBack: false,
    canGoForward: false,
    audible: false,
    error: null,
    notice: null,
    agent: fields.agent || null,
    discarded: Boolean(fields.discarded),
    createdAt: fields.createdAt,
  };
}

/** The shape the interface (and the chat) reads; field names match what the chat drawer already uses. */
function publicTab(t) {
  return {
    id: t.id,
    groupId: t.groupId,
    url: t.url,
    title: t.title,
    favicon: t.favicon,
    kind: t.kind,
    isLoading: t.loading,
    canGoBack: t.canGoBack,
    canGoForward: t.canGoForward,
    isAudible: t.audible,
    error: t.error,
    notice: t.notice,
    discarded: t.discarded,
    agentStatus: t.agent?.status || null,
    agentStep: t.agent?.step || '',
    agentLabel: t.agent?.label || '',
    agentSince: t.agent?.since || null,
  };
}
