// What the address bar does with what you type, and the suggestions under it. Plain functions (tested with node --test).

export const LAUNCHPAD = 'comex://launchpad';
const INTERNAL = new Set([LAUNCHPAD, 'nexus://launchpad', 'about:blank']);
export const isInternalUrl = (url) => !url || INTERNAL.has(url);

const SEARCH = 'https://www.google.com/search?q=';
const HOST_PORT_PATH = /^(?<host>[^\s/?#:]+)(?::(?<port>\d{1,5}))?(?<rest>[/?#]\S*)?$/;
const IPV4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
const TLD = /\.[a-z][a-z0-9-]{1,62}$/i;

/** The address to open for what was typed: a URL as-is, a host (with optional port and path) as a URL, else a search. */
export function toNavigableUrl(raw) {
  const value = String(raw || '').trim();
  if (!value) return null;
  if (INTERNAL.has(value)) return value;
  if (/^https?:\/\//i.test(value)) return value;
  if (/^[a-z][a-z0-9+.-]*:/i.test(value) && !HOST_PORT_PATH.exec(value)?.groups.port) return SEARCH + encodeURIComponent(value);
  if (!/\s/.test(value)) {
    const m = HOST_PORT_PATH.exec(value);
    if (m) {
      const { host, port } = m.groups;
      const ip = IPV4.exec(host);
      if (host === 'localhost' || (ip && ip.slice(1).every((n) => Number(n) <= 255))) return `http://${value}`;
      if (port || TLD.test(host)) return `https://${value}`;
    }
  }
  return SEARCH + encodeURIComponent(value);
}

/** True when Enter would open an address rather than search. */
export const looksLikeUrl = (raw) => {
  const u = toNavigableUrl(raw);
  return Boolean(u) && !u.startsWith(SEARCH);
};

/** Text for the address bar: internal pages show nothing, so the bar invites a search. */
export const displayUrl = (url) => (isInternalUrl(url) ? '' : url || '');

const strip = (url) => String(url || '').replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '');

/**
 * The rows under the address bar: first what Enter does (open the address or search for the text), then open tabs
 * to switch to, bookmarks and history that match. Each address appears once.
 */
export function buildSuggestions(text, { history = [], tabs = [], bookmarks = [], activeTabId = null, limit = 8 } = {}) {
  const q = String(text || '').trim();
  if (!q) return [];
  const low = q.toLowerCase();
  const matches = (url, title) => strip(url).toLowerCase().includes(low) || String(title || '').toLowerCase().includes(low);
  const rows = [];
  const seen = new Set();
  const add = (row) => {
    const key = row.url ? strip(row.url) : `search:${row.title}`;
    if (seen.has(key) || rows.length >= limit) return;
    seen.add(key);
    rows.push(row);
  };
  const url = toNavigableUrl(q);
  if (looksLikeUrl(q)) add({ type: 'url', title: strip(url), subtitle: 'Open address', url });
  else add({ type: 'search', title: q, subtitle: 'Google Search', url });
  for (const t of tabs) {
    if (t.id !== activeTabId && !isInternalUrl(t.url) && matches(t.url, t.title)) add({ type: 'tab', title: t.title || strip(t.url), subtitle: 'Switch to this tab', url: t.url, tabId: t.id });
  }
  for (const b of bookmarks) if (matches(b.url, b.title)) add({ type: 'bookmark', title: b.title || strip(b.url), subtitle: strip(b.url), url: b.url });
  for (const h of history) add({ type: 'history', title: h.title || strip(h.url), subtitle: strip(h.url), url: h.url });
  return rows;
}
