import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AlertTriangle, Bot, Check, Globe, Plus, RotateCw, Volume2, X } from 'lucide-react';
import './TabStrip.css';

// What the AI is doing in a group (from the chat). Same colours as the page glow and the chat.
const AI_STATE = {
  working: { label: 'Working' },
  done: { label: 'Done' },
  failed: { label: "Couldn't finish" },
  stopped: { label: 'Stopped' },
};

function elapsed(since, now) {
  if (!since) return '';
  const s = Math.max(0, Math.round((now - since) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

function useNow(active) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

/** Split the strip into runs of tabs that share a group (groups are contiguous by contract). */
function segmentsOf(tabs, groups) {
  const byId = Object.fromEntries(groups.map((g) => [g.id, g]));
  const out = [];
  for (const t of tabs) {
    const last = out[out.length - 1];
    if (last && last.group.id === t.groupId) last.tabs.push(t);
    else out.push({ group: byId[t.groupId] || { id: t.groupId, shown: false, color: 'grey', name: '' }, tabs: [t] });
  }
  return out;
}

function GroupChip({ group, title, activity, renaming, onRename, setRenaming, command, onDragStart, onDragEnd, dropProps }) {
  const state = activity?.state && AI_STATE[activity.state] ? activity.state : null;
  const now = useNow(state === 'working');
  const [draft, setDraft] = useState(group.name || '');
  const inputRef = useRef(null);
  useEffect(() => {
    if (renaming) {
      setDraft(group.name || '');
      requestAnimationFrame(() => { inputRef.current?.focus(); inputRef.current?.select(); });
    }
  }, [renaming, group.name]);

  const commit = () => {
    onRename(draft);
    setRenaming();
  };
  const label = group.name || title || `${group.size} tabs`;
  const timer = state === 'working' && activity?.since ? elapsed(activity.since, now) : '';

  return (
    <div
      className={`group-chip ${group.collapsed ? 'collapsed' : ''} ${state ? `ai-${state}` : ''}`}
      style={{ '--group-color': `var(--g-${group.color})` }}
      draggable={!renaming}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      {...dropProps}
    >
      {renaming ? (
        <input
          ref={inputRef}
          className="group-chip-input"
          value={draft}
          maxLength={60}
          aria-label="Group name"
          placeholder="Name this group"
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') setRenaming();
          }}
        />
      ) : (
        <button
          type="button"
          className="group-chip-btn"
          onClick={() => command({ type: 'set-group-collapsed', groupId: group.id, collapsed: !group.collapsed })}
          onDoubleClick={() => setRenaming(group.id)}
          onContextMenu={(e) => { e.preventDefault(); command({ type: 'context-menu', kind: 'group', groupId: group.id }); }}
          onKeyDown={(e) => {
            if (e.key === 'F2') { e.preventDefault(); setRenaming(group.id); }
            if (e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) { e.preventDefault(); command({ type: 'context-menu', kind: 'group', groupId: group.id }); }
          }}
          aria-expanded={!group.collapsed}
          aria-label={`${label}, ${group.size} ${group.size === 1 ? 'tab' : 'tabs'}${state ? `, AI ${AI_STATE[state].label.toLowerCase()}` : ''}. ${group.collapsed ? 'Expand' : 'Collapse'} group`}
          title={`${label} — click to ${group.collapsed ? 'expand' : 'collapse'}, double-click to rename, right-click for more`}
        >
          {state && (
            <span className={`ai-dot ai-${state}`} aria-hidden="true">
              {state === 'done' && <Check size={8} strokeWidth={3.5} />}
              {state === 'failed' && <X size={8} strokeWidth={3.5} />}
            </span>
          )}
          <span className="group-chip-label">{label}</span>
          {timer && <span className="group-chip-timer">{timer}</span>}
          {group.collapsed && <span className="group-chip-count">{group.size}</span>}
        </button>
      )}
    </div>
  );
}

function Tab({ tab, active, grouped, groupColor, soloActivity, focusable, command, onDragStart, onDragEnd, dropProps, dropSide, onShowCard, onHideCard, tabRef }) {
  const aiState = soloActivity?.state && AI_STATE[soloActivity.state] ? soloActivity.state : null;
  const [iconFailed, setIconFailed] = useState(null); // the favicon URL that failed to load, if any
  const title = tab.title || (tab.url && /^https?:/.test(tab.url) ? tab.url.replace(/^https?:\/\//, '') : 'New Tab');
  const status = tab.error ? 'error' : tab.isLoading ? 'loading' : 'idle';
  const icon = tab.error ? <AlertTriangle size={13} className="tab-err-icon" />
    : tab.isLoading ? <RotateCw size={12} className="tab-spinner" />
      : tab.favicon && iconFailed !== tab.favicon ? <img src={tab.favicon} alt="" className="tab-favicon-img" draggable={false} onError={() => setIconFailed(tab.favicon)} />
        : <Globe size={13} className="tab-globe" />;
  return (
    <div
      ref={tabRef}
      role="tab"
      aria-selected={active}
      tabIndex={focusable ? 0 : -1}
      className={`tab ${active ? 'active' : ''} ${grouped ? 'grouped' : ''} tab-${status} ${tab.agentStatus ? `agent agent-${tab.agentStatus}` : ''} ${dropSide ? `drop-${dropSide}` : ''}`}
      style={grouped ? { '--group-color': `var(--g-${groupColor})` } : undefined}
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      {...dropProps}
      onClick={() => command({ type: 'activate', tabId: tab.id })}
      onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); command({ type: 'close-tab', tabId: tab.id }); } }}
      onContextMenu={(e) => { e.preventDefault(); command({ type: 'context-menu', kind: 'tab', tabId: tab.id }); }}
      onMouseEnter={tab.agentStatus ? (e) => onShowCard(tab, e.currentTarget.getBoundingClientRect()) : undefined}
      onMouseLeave={tab.agentStatus ? onHideCard : undefined}
      title={tab.agentStatus ? undefined : `${title}${tab.url && !tab.url.startsWith('comex://') ? `\n${tab.url}` : ''}`}
      aria-label={`${title}${tab.isLoading ? ', loading' : ''}${tab.error ? ', failed to load' : ''}${tab.agentStatus ? `, agent ${tab.agentStatus}` : ''}`}
    >
      <span className="tab-icon" aria-hidden="true">{icon}</span>
      {tab.agentStatus && (
        <span className="tab-agent-badge" aria-hidden="true">
          {tab.agentStatus === 'completed' ? <Check size={10} strokeWidth={2.5} /> : <Bot size={10} />}
        </span>
      )}
      {aiState && <span className={`ai-dot ai-${aiState}`} aria-hidden="true" title={AI_STATE[aiState].label} />}
      <span className="tab-title">{title}</span>
      {tab.isAudible && <Volume2 size={12} className="tab-audio" aria-label="Playing audio" />}
      <button
        type="button"
        className="tab-close"
        tabIndex={-1}
        onClick={(e) => { e.stopPropagation(); command({ type: 'close-tab', tabId: tab.id }); }}
        aria-label={`Close ${title}`}
        title="Close tab (⌘W)"
      >
        <X size={12} />
      </button>
      {tab.agentStatus === 'working' && <span className="tab-agent-track" aria-hidden="true" />}
    </div>
  );
}

/**
 * The tab strip: tabs and tab groups, drawn from the main process's state. Drag a tab to reorder it, onto another
 * group's tab to move it there, onto a plain tab to take it out of its group; drag a group's chip to move the group.
 */
export default function TabStrip({ session, groupActivity = {}, groupTitles = {}, command, renamingGroupId, setRenamingGroupId, onShowCard, onHideCard }) {
  const { tabs, groups, activeTabId } = session;
  const segments = segmentsOf(tabs, groups);
  const [drag, setDrag] = useState(null); // { kind: 'tab' | 'group', id }
  const [drop, setDrop] = useState(null); // { tabId, side } for the indicator
  const scrollRef = useRef(null);
  const tabRefs = useRef(new Map());
  const [edges, setEdges] = useState({ left: false, right: false });

  // keep the active tab in view, and show fades where tabs overflow
  useLayoutEffect(() => {
    tabRefs.current.get(activeTabId)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [activeTabId]);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    const update = () => setEdges({ left: el.scrollLeft > 2, right: el.scrollLeft + el.clientWidth < el.scrollWidth - 2 });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    el.addEventListener('scroll', update, { passive: true });
    return () => { ro.disconnect(); el.removeEventListener('scroll', update); };
  }, [tabs.length]);

  const onWheel = (e) => {
    const el = scrollRef.current;
    if (el && Math.abs(e.deltaY) > Math.abs(e.deltaX)) el.scrollLeft += e.deltaY;
  };

  // ── drag and drop ──
  const orderIds = tabs.map((t) => t.id);
  const tabById = Object.fromEntries(tabs.map((t) => [t.id, t]));
  const groupById = Object.fromEntries(groups.map((g) => [g.id, g]));
  const isShown = (gid) => Boolean(groupById[gid]?.shown);

  const sideOf = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    return e.clientX < r.left + r.width / 2 ? 'before' : 'after';
  };
  const tabDropProps = (target) => ({
    onDragOver: (e) => {
      if (!drag || (drag.kind === 'tab' && drag.id === target.id)) return;
      if (drag.kind === 'group' && target.groupId === drag.id) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const side = sideOf(e);
      if (!drop || drop.tabId !== target.id || drop.side !== side) setDrop({ tabId: target.id, side });
    },
    onDragLeave: () => setDrop((d) => (d && d.tabId === target.id ? null : d)),
    onDrop: (e) => {
      e.preventDefault();
      const side = sideOf(e);
      setDrop(null);
      if (!drag) return;
      if (drag.kind === 'tab') {
        const without = orderIds.filter((id) => id !== drag.id);
        const index = without.indexOf(target.id) + (side === 'after' ? 1 : 0);
        if (isShown(target.groupId)) command({ type: 'move-tab', tabId: drag.id, index, groupId: target.groupId });
        else command({ type: 'move-tab', tabId: drag.id, index, ungroup: isShown(tabById[drag.id]?.groupId) });
      } else {
        // a group lands before or after the whole run the target tab belongs to
        const without = orderIds.filter((id) => tabById[id].groupId !== drag.id);
        const seg = without.filter((id) => tabById[id].groupId === target.groupId);
        const anchor = side === 'before' ? without.indexOf(seg[0]) : without.indexOf(seg[seg.length - 1]) + 1;
        command({ type: 'move-group', groupId: drag.id, index: anchor });
      }
      setDrag(null);
    },
  });
  const chipDropProps = (group, firstTab) => ({
    onDragOver: (e) => {
      if (!drag || drag.kind !== 'tab') return;
      e.preventDefault();
      if (!drop || drop.tabId !== firstTab.id || drop.side !== 'before') setDrop({ tabId: firstTab.id, side: 'before' });
    },
    onDrop: (e) => {
      e.preventDefault();
      setDrop(null);
      if (drag?.kind !== 'tab') return;
      const without = orderIds.filter((id) => id !== drag.id);
      command({ type: 'move-tab', tabId: drag.id, groupId: group.id, index: without.indexOf(firstTab.id) });
      setDrag(null);
    },
  });
  const endDropProps = {
    onDragOver: (e) => { if (drag) e.preventDefault(); },
    onDrop: (e) => {
      e.preventDefault();
      setDrop(null);
      if (drag?.kind === 'tab') command({ type: 'move-tab', tabId: drag.id, index: orderIds.length - 1, ungroup: isShown(tabById[drag.id]?.groupId) });
      if (drag?.kind === 'group') command({ type: 'move-group', groupId: drag.id, index: orderIds.length });
      setDrag(null);
    },
  };
  const startDrag = (kind, id) => (e) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', id);
    onHideCard?.();
    setDrag({ kind, id });
  };
  const endDrag = () => { setDrag(null); setDrop(null); };

  // ── keyboard: arrows move between tabs, Enter opens, Delete closes, the menu key opens the tab menu ──
  const visibleIds = segments.flatMap((s) => (s.group.shown && s.group.collapsed ? [] : s.tabs.map((t) => t.id)));
  const onKeyDown = (e) => {
    const id = e.target?.getAttribute?.('role') === 'tab' ? [...tabRefs.current.entries()].find(([, el]) => el === e.target)?.[0] : null;
    if (!id) return;
    const i = visibleIds.indexOf(id);
    const focus = (j) => { e.preventDefault(); tabRefs.current.get(visibleIds[(j + visibleIds.length) % visibleIds.length])?.focus(); };
    if (e.key === 'ArrowRight') focus(i + 1);
    else if (e.key === 'ArrowLeft') focus(i - 1);
    else if (e.key === 'Home') focus(0);
    else if (e.key === 'End') focus(visibleIds.length - 1);
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); command({ type: 'activate', tabId: id }); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); command({ type: 'close-tab', tabId: id }); }
    else if (e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) { e.preventDefault(); command({ type: 'context-menu', kind: 'tab', tabId: id }); }
  };

  return (
    <div className={`tab-strip ${edges.left ? 'fade-left' : ''} ${edges.right ? 'fade-right' : ''} ${drag ? 'dragging' : ''}`}>
      <div className="tab-strip-scroll" ref={scrollRef} role="tablist" aria-label="Tabs" onWheel={onWheel} onKeyDown={onKeyDown}>
        {segments.map(({ group, tabs: segTabs }) => {
          const shown = group.shown;
          const activity = groupActivity[group.id];
          return (
            <div key={group.id} className={`tab-run ${shown ? 'is-group' : ''} ${shown && group.collapsed ? 'collapsed' : ''}`}
              style={shown ? { '--group-color': `var(--g-${group.color})` } : undefined} role="presentation">
              {shown && (
                <GroupChip
                  group={group}
                  title={groupTitles[group.id]}
                  activity={activity}
                  renaming={renamingGroupId === group.id}
                  onRename={(name) => command({ type: 'rename-group', groupId: group.id, name })}
                  setRenaming={(gid) => setRenamingGroupId(gid || null)}
                  command={command}
                  onDragStart={startDrag('group', group.id)}
                  onDragEnd={endDrag}
                  dropProps={chipDropProps(group, segTabs[0])}
                />
              )}
              {!(shown && group.collapsed) && segTabs.map((tab) => (
                <Tab
                  key={tab.id}
                  tab={tab}
                  tabRef={(el) => { if (el) tabRefs.current.set(tab.id, el); else tabRefs.current.delete(tab.id); }}
                  active={tab.id === activeTabId}
                  focusable={tab.id === activeTabId}
                  grouped={shown}
                  groupColor={group.color}
                  soloActivity={shown ? null : activity}
                  command={command}
                  onDragStart={startDrag('tab', tab.id)}
                  onDragEnd={endDrag}
                  dropProps={tabDropProps(tab)}
                  dropSide={drop?.tabId === tab.id ? drop.side : null}
                  onShowCard={onShowCard}
                  onHideCard={onHideCard}
                />
              ))}
            </div>
          );
        })}
        <div className="tab-strip-end" {...endDropProps}>
          <button type="button" className="new-tab-btn" onClick={() => command({ type: 'new-tab' })} aria-label="New tab" title="New tab (⌘T)">
            <Plus size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
