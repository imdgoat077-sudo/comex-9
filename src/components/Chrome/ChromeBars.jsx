import React, { useEffect, useState } from 'react';
import { ExternalLink, Globe, Info, RotateCcw, X } from 'lucide-react';
import './Chrome.css';

/** Saved bookmarks. Click opens in this tab, ⌘-click or middle-click in a new tab, right-click for more. */
export function BookmarkBar({ bookmarks, command }) {
  if (!bookmarks.length) return null;
  const open = (e, url) => {
    if (e.metaKey || e.ctrlKey || e.button === 1) command({ type: 'new-tab', url, activate: false });
    else command({ type: 'navigate', url });
  };
  return (
    <nav className="bookmark-bar" aria-label="Bookmarks">
      {bookmarks.map((b) => (
        <button
          key={b.url}
          type="button"
          className="bookmark-item"
          title={b.url}
          onClick={(e) => open(e, b.url)}
          onAuxClick={(e) => { if (e.button === 1) open(e, b.url); }}
          onContextMenu={(e) => { e.preventDefault(); command({ type: 'context-menu', kind: 'bookmark', url: b.url }); }}
        >
          <Globe size={12} aria-hidden="true" />
          <span>{b.title}</span>
        </button>
      ))}
    </nav>
  );
}

/**
 * Google refuses sign-in from browsers built on an embedded engine such as Comex's (its policy, not a fault of the
 * page). Comex says so plainly and offers your default browser; it does not try to get around the refusal.
 */
export function NoticeBar({ tab, command }) {
  if (tab?.notice?.kind !== 'google-signin-blocked') return null;
  return (
    <div className="notice-bar" role="status">
      <Info size={15} className="notice-icon" aria-hidden="true" />
      <p>
        <strong>Google doesn't allow signing in from embedded browsers like Comex.</strong>{' '}
        You can sign in to your Google account in your default browser. Other sites' sign-in works here.
      </p>
      <button type="button" className="notice-action" onClick={() => command({ type: 'open-external', url: tab.notice.url })}>
        <ExternalLink size={13} /> Open in default browser
      </button>
      <button type="button" className="notice-close" aria-label="Dismiss" onClick={() => command({ type: 'dismiss-notice', tabId: tab.id })}>
        <X size={14} />
      </button>
    </div>
  );
}

/** After a group closes: what closed, with Undo (⇧⌘T does the same), for a few seconds. */
export function ClosedToast({ lastClosed, command }) {
  const [shown, setShown] = useState(null);
  const key = lastClosed ? `${lastClosed.type}|${lastClosed.name}|${lastClosed.count}` : '';
  const [seen, setSeen] = useState(key);
  useEffect(() => {
    if (key === seen) return undefined;
    setSeen(key);
    if (lastClosed?.type !== 'group') { setShown(null); return undefined; }
    setShown(lastClosed);
    const t = setTimeout(() => setShown(null), 8000);
    return () => clearTimeout(t);
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!shown) return null;
  return (
    <div className="closed-toast" role="status">
      <span>Closed “{(shown.name || 'group').slice(0, 30)}” · {shown.count} {shown.count === 1 ? 'tab' : 'tabs'}</span>
      <button type="button" onClick={() => { command({ type: 'reopen-closed' }); setShown(null); }}>
        <RotateCcw size={12} /> Undo
      </button>
    </div>
  );
}
