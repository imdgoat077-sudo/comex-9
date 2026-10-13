import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowRight, Clock, Globe, Info, Lock, RotateCw, Search, Sparkles, Star, X, AppWindow } from 'lucide-react';
import { buildSuggestions, displayUrl, isInternalUrl, toNavigableUrl } from '../../shell/omnibox';
import { popupTheme, toNativeRect } from '../../shell/geometry';
import './Toolbar.css';

const ROW_H = 34;
const popupBridge = () => (typeof window !== 'undefined' ? window.nexusNative?.browser?.popup : undefined);
const ROW_ICONS = { search: Search, url: Globe, history: Clock, tab: AppWindow, bookmark: Star };

/** Address bar: what you type opens an address or searches; suggestions come from history, open tabs and bookmarks. */
const Omnibox = forwardRef(function Omnibox({ tab, tabs, bookmarks, command }, ref) {
  const [text, setText] = useState(displayUrl(tab?.url));
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef(null);
  const formRef = useRef(null);
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const query = useRef(0);

  useImperativeHandle(ref, () => ({ focus: () => { inputRef.current?.focus(); inputRef.current?.select(); } }), []);

  // follow the tab's address unless you are typing
  useEffect(() => { if (!editing) setText(displayUrl(tab?.url)); }, [tab?.id, tab?.url, editing]);

  // suggestions: drawn by the native popup layer in Electron (pages are above the interface), inline otherwise
  const popup = popupBridge();
  useEffect(() => {
    if (!popup) return undefined;
    if (!editing || !rows.length || !formRef.current) { popup.hide(); return undefined; }
    const rect = formRef.current.getBoundingClientRect();
    const height = rows.length * ROW_H + 8;
    popup.show({
      kind: 'suggest',
      rect: toNativeRect({ left: rect.left, top: rect.bottom + 4, width: rect.width, height }, { padX: 10, padBottom: 12 }),
      items: rows.map(({ type, title, subtitle }) => ({ type, title, subtitle })),
      selected,
      theme: popupTheme(),
    });
    return undefined;
  }, [popup, editing, rows, selected]);
  useEffect(() => () => popup?.hide(), [popup]);
  const chooseRef = useRef(null);
  useEffect(() => (popup ? popup.onEvent((e) => { if (e?.type === 'pick') chooseRef.current?.(rowsRef.current[e.index]); }) : undefined), [popup]);

  const suggest = async (value) => {
    const n = ++query.current;
    const history = value.trim() ? (await command({ type: 'history-query', text: value })) || [] : [];
    if (n !== query.current) return; // a newer keystroke won
    setRows(buildSuggestions(value, { history, tabs, bookmarks, activeTabId: tab?.id }));
    setSelected(0);
  };

  const close = () => { setRows([]); setSelected(0); };
  const finish = () => { close(); setEditing(false); inputRef.current?.blur(); };

  const choose = (row) => {
    if (!row) return;
    if (row.type === 'tab' && row.tabId) command({ type: 'activate', tabId: row.tabId });
    else command({ type: 'navigate', tabId: tab?.id, url: row.url });
    finish();
  };
  chooseRef.current = choose;

  const submit = (e) => {
    e.preventDefault();
    if (rows.length && rows[selected]) return choose(rows[selected]);
    const url = toNavigableUrl(text);
    if (url) choose({ type: 'url', url });
  };

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown' && rows.length) { e.preventDefault(); setSelected((s) => (s + 1) % rows.length); }
    else if (e.key === 'ArrowUp' && rows.length) { e.preventDefault(); setSelected((s) => (s - 1 + rows.length) % rows.length); }
    else if (e.key === 'Escape') {
      e.preventDefault();
      if (rows.length) close();
      else { setText(displayUrl(tab?.url)); finish(); }
    }
  };

  const internal = isInternalUrl(tab?.url);
  const secure = tab?.url?.startsWith('https://');
  const badge = internal ? <Search size={13} /> : tab?.error ? <AlertTriangle size={13} className="omni-warn" />
    : secure ? <Lock size={12} /> : <span className="omni-insecure"><Info size={13} /> Not secure</span>;
  const badgeTitle = internal ? '' : tab?.error ? 'This page could not be loaded' : secure ? 'Connection is encrypted (HTTPS)' : 'This page is not encrypted (HTTP)';
  const isBookmarked = !internal && bookmarks.some((b) => b.url === tab?.url);

  return (
    <div className={`omnibox ${editing ? 'focused' : ''}`}>
      <form ref={formRef} onSubmit={submit} className="omnibox-form" role="search">
        <span className="omni-badge" title={badgeTitle}>{badge}</span>
        <input
          ref={inputRef}
          className="omni-input"
          value={text}
          placeholder="Search Google or type an address"
          aria-label="Address and search bar"
          aria-autocomplete="list"
          aria-expanded={rows.length > 0}
          spellCheck={false}
          autoComplete="off"
          onChange={(e) => { setText(e.target.value); setEditing(true); suggest(e.target.value); }}
          onFocus={(e) => { setEditing(true); e.target.select(); }}
          onBlur={() => setTimeout(() => { close(); setEditing(false); }, 120)}
          onKeyDown={onKeyDown}
        />
        {!internal && tab?.url && (
          <button
            type="button"
            className={`omni-star ${isBookmarked ? 'on' : ''}`}
            onClick={() => command({ type: 'toggle-bookmark', url: tab.url, title: tab.title })}
            aria-label={isBookmarked ? 'Remove bookmark' : 'Bookmark this page'}
            aria-pressed={isBookmarked}
            title={isBookmarked ? 'Remove bookmark' : 'Bookmark this page'}
          >
            <Star size={14} fill={isBookmarked ? 'currentColor' : 'none'} />
          </button>
        )}
      </form>
      {!popup && editing && rows.length > 0 && (
        <div className="omni-list" role="listbox">
          {rows.map((row, i) => {
            const Icon = ROW_ICONS[row.type] || Globe;
            return (
              <div key={`${row.type}:${row.url}`} role="option" aria-selected={i === selected} className={`omni-row ${i === selected ? 'sel' : ''}`}
                onMouseDown={(e) => { e.preventDefault(); choose(row); }}>
                <Icon size={14} className="omni-row-icon" />
                <span className="omni-row-title">{row.title}</span>
                {row.subtitle && <span className="omni-row-sub">{row.subtitle}</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

/** The toolbar: back, forward, reload or stop, the address bar, and the assistant. */
const Toolbar = forwardRef(function Toolbar({ tab, tabs, bookmarks, command, isChatOpen, onToggleChat, unreadCount }, ref) {
  const loading = Boolean(tab?.isLoading);
  return (
    <div className="toolbar">
      <div className="toolbar-nav">
        <button className="tool-btn" disabled={!tab?.canGoBack} onClick={() => command({ type: 'back' })} aria-label="Back" title="Back (⌘[)">
          <ArrowLeft size={16} />
        </button>
        <button className="tool-btn" disabled={!tab?.canGoForward} onClick={() => command({ type: 'forward' })} aria-label="Forward" title="Forward (⌘])">
          <ArrowRight size={16} />
        </button>
        {loading ? (
          <button className="tool-btn" onClick={() => command({ type: 'stop' })} aria-label="Stop loading" title="Stop (⌘.)">
            <X size={16} />
          </button>
        ) : (
          <button className="tool-btn" disabled={isInternalUrl(tab?.url)} onClick={() => command({ type: 'reload' })} aria-label="Reload" title="Reload (⌘R)">
            <RotateCw size={15} />
          </button>
        )}
      </div>
      <Omnibox ref={ref} tab={tab} tabs={tabs} bookmarks={bookmarks} command={command} />
      <button className={`assistant-btn ${isChatOpen ? 'active' : ''}`} onClick={onToggleChat} aria-pressed={isChatOpen} title="Assistant (⌘J)">
        <Sparkles size={14} />
        <span className="assistant-label">Assistant</span>
        {unreadCount > 0 && <span className="assistant-unread" aria-label={`${unreadCount} unread`}>{unreadCount}</span>}
      </button>
      {loading && <span className="toolbar-progress" aria-hidden="true" />}
    </div>
  );
});

export default Toolbar;
