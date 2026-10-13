// node --test electron/   (TabManager: the browser's tabs and groups)
import test from 'node:test';
import assert from 'node:assert/strict';
import { TabManager, LAUNCHPAD } from './tab_manager.js';

let n = 0;
const make = () => TabManager.fresh({ newId: () => `id${++n}`, now: () => 1000 });
const order = (m) => m.order.map((id) => m.tab(id).title || id);
const contiguous = (m) => {
  const seen = new Set();
  let prev = null;
  for (const id of m.order) {
    const g = m.tab(id).groupId;
    if (g !== prev && seen.has(g)) return false;
    seen.add(g);
    prev = g;
  }
  return true;
};
const invariants = (m) => {
  assert.ok(m.order.length >= 1, 'at least one tab');
  assert.ok(contiguous(m), 'groups are contiguous');
  for (const id of m.order) assert.ok(m.groups.has(m.tab(id).groupId), 'every tab has a group');
  for (const gid of m.groups.keys()) assert.ok(m.tabsInGroup(gid).length > 0, 'no empty groups');
  assert.ok(m.tabs.has(m.activeTabId), 'active tab exists');
  assert.equal(m.group(m.tab(m.activeTabId).groupId).collapsed, false, 'active tab is visible');
};

test('a fresh browser has one Launchpad tab in a group of its own', () => {
  const m = make();
  assert.equal(m.order.length, 1);
  assert.equal(m.tab(m.activeTabId).url, LAUNCHPAD);
  assert.equal(m.isShownGroup(m.tab(m.activeTabId).groupId), false);
  invariants(m);
});

test('new tabs get their own group; tabs opened in a group join it, at its end', () => {
  const m = make();
  const a = m.createTab({ url: 'https://a.test', title: 'A' });
  const b = m.createTab({ url: 'https://b.test', title: 'B' });
  assert.notEqual(a.groupId, b.groupId);
  const a2 = m.createTab({ url: 'https://a2.test', title: 'A2', groupId: a.groupId });
  assert.deepEqual(order(m).slice(1), ['A', 'A2', 'B']);
  assert.equal(m.activeTabId, a2.id);
  assert.equal(m.isShownGroup(a.groupId), true);
  invariants(m);
});

test('an agent tab with an unknown group id creates that group (its chat)', () => {
  const m = make();
  const t = m.createTab({ id: 'tab_worker_1', groupId: 'grp-chat', kind: 'agent', activate: false });
  assert.equal(t.groupId, 'grp-chat');
  assert.equal(t.kind, 'agent');
  assert.throws(() => m.createTab({ id: 'tab_worker_1' }), /duplicate/);
  invariants(m);
});

test('a tab never lands in the middle of another group', () => {
  const m = make();
  const a = m.createTab({ title: 'A' });
  m.createTab({ title: 'A2', groupId: a.groupId });
  const x = m.createTab({ title: 'X', index: 2 }); // between A and A2
  assert.deepEqual(order(m).slice(1), ['A', 'A2', 'X']);
  m.moveTab(x.id, { index: 2 });
  assert.ok(contiguous(m));
  invariants(m);
});

test('closing the active tab picks a neighbour in the same group first', () => {
  const m = make();
  const a = m.createTab({ title: 'A' });
  const a2 = m.createTab({ title: 'A2', groupId: a.groupId });
  m.createTab({ title: 'B' });
  m.setActive(a.id);
  m.closeTab(a.id);
  assert.equal(m.activeTabId, a2.id);
  invariants(m);
});

test('closing the last tab leaves a fresh Launchpad tab', () => {
  const m = make();
  const only = m.activeTabId;
  m.closeTab(only);
  assert.equal(m.order.length, 1);
  assert.notEqual(m.activeTabId, only);
  assert.equal(m.tab(m.activeTabId).url, LAUNCHPAD);
  invariants(m);
});

test('closing a group closes all and only its tabs, and drops the group', () => {
  const m = make();
  const keep = m.createTab({ title: 'Keep' });
  const g = m.createGroup({ tabIds: [m.createTab({ title: 'G1' }).id], name: 'Trip' }).group;
  m.createTab({ title: 'G2', groupId: g.id });
  m.createTab({ title: 'W', groupId: g.id, kind: 'agent', id: 'tab_w', activate: true });
  const events = [];
  m.subscribe((e) => events.push(e.type));
  const closed = m.closeGroup(g.id);
  assert.equal(closed.length, 3);
  assert.equal(m.group(g.id), null);
  assert.ok(m.tabs.has(keep.id));
  assert.equal(events.filter((e) => e === 'tab-closed').length, 3);
  assert.ok(!closed.includes(m.activeTabId));
  invariants(m);
});

test('reopening a closed group brings back its tabs, name, colour and id', () => {
  const m = make();
  const t = m.createTab({ url: 'https://x.test', title: 'X' });
  const { group } = m.createGroup({ tabIds: [t.id], name: 'Work', color: 'green' });
  m.createTab({ url: 'https://y.test', title: 'Y', groupId: group.id });
  m.closeGroup(group.id);
  assert.equal(m.snapshot().lastClosed.type, 'group');
  const back = m.reopenClosed();
  assert.equal(back.length, 2);
  const g = m.group(back[0].groupId);
  assert.equal(g.id, group.id);
  assert.equal(g.name, 'Work');
  assert.equal(g.color, 'green');
  assert.deepEqual(back.map((b) => b.url), ['https://x.test', 'https://y.test']);
  invariants(m);
});

test('a closed tab reopens in its group, recreating the group if it is gone', () => {
  const m = make();
  const t = m.createTab({ url: 'https://solo.test' });
  const gid = t.groupId;
  m.closeTab(t.id);
  assert.equal(m.group(gid), null);
  const [back] = m.reopenClosed();
  assert.equal(back.groupId, gid);
  invariants(m);
});

test('moving tabs between groups, out of a group, and reordering within one', () => {
  const m = make();
  const a = m.createTab({ title: 'A' });
  const a2 = m.createTab({ title: 'A2', groupId: a.groupId });
  const b = m.createTab({ title: 'B' });
  const res = m.moveTab(b.id, { groupId: a.groupId, index: 2 }); // between A and A2
  assert.equal(res.toGroup, a.groupId);
  assert.equal(res.emptied, res.fromGroup); // B's own group is gone
  assert.deepEqual(order(m).slice(1), ['A', 'B', 'A2']);
  const out = m.moveTab(a2.id, { ungroup: true });
  assert.notEqual(out.toGroup, a.groupId);
  assert.deepEqual(order(m).slice(1), ['A', 'B', 'A2']);
  m.moveTab(b.id, { index: 99 }); // clamped inside its group
  assert.deepEqual(order(m).slice(1), ['A', 'B', 'A2']);
  invariants(m);
});

test('moving a whole group keeps it together', () => {
  const m = make();
  const a = m.createTab({ title: 'A' });
  m.createTab({ title: 'A2', groupId: a.groupId });
  m.createTab({ title: 'B' });
  m.moveGroup(a.groupId, 99);
  assert.deepEqual(order(m).slice(1), ['B', 'A', 'A2']);
  invariants(m);
});

test('collapsing the active group moves to a tab outside it; activating a tab expands its group', () => {
  const m = make();
  const a = m.createTab({ title: 'A' });
  m.createTab({ title: 'A2', groupId: a.groupId });
  const b = m.createTab({ title: 'B' });
  m.setActive(a.id);
  assert.equal(m.setGroupCollapsed(a.groupId, true), true);
  assert.equal(m.activeTabId, b.id);
  m.setActive(a.id);
  assert.equal(m.group(a.groupId).collapsed, false);
  invariants(m);
});

test('a group that holds every tab cannot be collapsed', () => {
  const m = make();
  const first = m.activeTabId;
  m.createTab({ title: 'A2', groupId: m.tab(first).groupId });
  assert.equal(m.setGroupCollapsed(m.tab(first).groupId, true), false);
  invariants(m);
});

test('ungroup keeps the chat with the first tab and gives the others their own', () => {
  const m = make();
  const a = m.createTab({ title: 'A' });
  const a2 = m.createTab({ title: 'A2', groupId: a.groupId });
  m.renameGroup(a.groupId, 'Named');
  const created = m.ungroup(a.groupId);
  assert.equal(m.tab(a.id).groupId, a.groupId);
  assert.equal(m.group(a.groupId).name, '');
  assert.equal(created[0].tabId, a2.id);
  invariants(m);
});

test('rename and colour are validated', () => {
  const m = make();
  const gid = m.tab(m.activeTabId).groupId;
  m.renameGroup(gid, '  ' + 'x'.repeat(100));
  assert.equal(m.group(gid).name.length, 60);
  assert.equal(m.setGroupColor(gid, 'chartreuse'), false);
  assert.equal(m.setGroupColor(gid, 'red'), true);
});

test('session restore: same ids, groups and order; unsafe data dropped; pages load lazily', () => {
  const m = make();
  const a = m.createTab({ url: 'https://a.test', title: 'A' });
  const { group } = m.createGroup({ tabIds: [a.id], name: 'Research', color: 'purple' });
  m.createTab({ url: 'https://a2.test', title: 'A2', groupId: group.id });
  m.setGroupCollapsed(group.id, true);
  const data = JSON.parse(JSON.stringify(m.serialize()));
  data.tabs.push({ id: 'evil', groupId: 'nope', url: 'javascript:alert(1)', title: 'E' });
  data.tabs.push({ id: '../../bad id', url: 'https://x.test' });
  const r = TabManager.restore(data, { newId: () => `r${++n}` });
  assert.deepEqual(r.order.slice(0, 3), m.order);
  assert.equal(r.group(group.id).name, 'Research');
  assert.equal(r.group(group.id).collapsed, true);
  assert.equal(r.tab('evil').url, LAUNCHPAD);
  assert.equal(r.tab('../../bad id'), null);
  assert.equal(r.activeTabId, m.activeTabId);
  assert.equal(r.tab(a.id).discarded, true);
  assert.equal(r.tab(r.activeTabId).discarded, false);
  invariants(r);
});

test('restore of garbage gives a fresh browser', () => {
  for (const bad of [null, {}, { version: 2, tabs: [] }, { version: 1, tabs: 'x' }, { version: 1, tabs: [] }]) {
    const r = TabManager.restore(bad);
    assert.equal(r.order.length, 1);
    invariants(r);
  }
});

test('restore regroups tabs that were saved apart', () => {
  const data = { version: 1, activeTabId: 't1', groups: [{ id: 'g1' }, { id: 'g2' }],
    tabs: [{ id: 't1', groupId: 'g1', url: LAUNCHPAD }, { id: 't2', groupId: 'g2', url: LAUNCHPAD }, { id: 't3', groupId: 'g1', url: LAUNCHPAD }] };
  const r = TabManager.restore(data);
  assert.deepEqual(r.order, ['t1', 't3', 't2']);
  invariants(r);
});

test('updateTab only accepts known fields and reports changes', () => {
  const m = make();
  const id = m.activeTabId;
  let changes = 0;
  m.subscribe((e) => { if (e.type === 'changed') changes += 1; });
  assert.equal(m.updateTab(id, { title: 'T', groupId: 'hijack' }), true);
  assert.equal(m.tab(id).groupId !== 'hijack', true);
  assert.equal(m.updateTab(id, { title: 'T' }), false);
  assert.equal(changes, 1);
});

test('snapshot exposes the fields the chat reads', () => {
  const m = make();
  const t = m.createTab({ url: 'https://a.test', kind: 'agent', id: 'tab_a', agent: { status: 'working', step: 'Opening', label: 'Find', since: 5 } });
  const s = m.snapshot().tabs.find((x) => x.id === t.id);
  assert.equal(s.agentStatus, 'working');
  assert.equal(s.agentLabel, 'Find');
  assert.equal(s.groupId, t.groupId);
  assert.equal(typeof s.isLoading, 'boolean');
});

test('random operations never break the invariants', () => {
  let seed = 7;
  const rnd = (k) => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % k; };
  const m = make();
  for (let i = 0; i < 2000; i += 1) {
    const ids = m.order;
    const pick = () => ids[rnd(ids.length)];
    const gids = [...m.groups.keys()];
    const g = () => gids[rnd(gids.length)];
    switch (rnd(12)) {
      case 0: m.createTab({ groupId: rnd(2) ? g() : undefined, index: rnd(ids.length + 1) }); break;
      case 1: m.closeTab(pick()); break;
      case 2: m.closeGroup(g()); break;
      case 3: m.moveTab(pick(), { groupId: g(), index: rnd(ids.length + 1) }); break;
      case 4: m.moveTab(pick(), { ungroup: true, index: rnd(ids.length + 1) }); break;
      case 5: m.moveGroup(g(), rnd(ids.length + 1)); break;
      case 6: m.setGroupCollapsed(g(), Boolean(rnd(2))); break;
      case 7: m.setActive(pick()); break;
      case 8: m.reopenClosed(); break;
      case 9: m.createGroup({ tabIds: [pick(), pick()], name: 'n' }); break;
      case 10: m.ungroup(g()); break;
      default: m.duplicateTab(pick());
    }
    invariants(m);
  }
  invariants(TabManager.restore(JSON.parse(JSON.stringify(m.serialize()))));
});
