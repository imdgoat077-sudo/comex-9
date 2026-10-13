/**
 * Small persistent stores of the browser process: a crash-safe JSON file, browsing history (address bar suggestions),
 * bookmarks, and per-site permission decisions. The logic classes take plain data and are tested with `node --test`;
 * only JsonFile touches the disk.
 */
import fs from 'fs';

/**
 * A JSON file written atomically: the new content goes to `<file>.tmp`, the old file becomes `<file>.bak`, then the tmp
 * file is renamed into place. A crash at any point leaves either the old or the new content readable.
 */
export class JsonFile {
  constructor(file, { delayMs = 400 } = {}) {
    this.file = file;
    this.delayMs = delayMs;
    this._pending = null;
    this._timer = null;
  }

  read(fallback) {
    for (const f of [this.file, `${this.file}.bak`]) {
      try {
        return JSON.parse(fs.readFileSync(f, 'utf8'));
      } catch {
        // missing or corrupt: try the next one
      }
    }
    return fallback;
  }

  /** Save soon (writes are coalesced); flush() saves now. */
  write(data) {
    this._pending = data;
    if (!this._timer) this._timer = setTimeout(() => this.flush(), this.delayMs);
  }

  flush() {
    if (this._timer) clearTimeout(this._timer);
    this._timer = null;
    if (this._pending === null) return;
    const data = this._pending;
    this._pending = null;
    const tmp = `${this.file}.tmp`;
    try {
      fs.writeFileSync(tmp, JSON.stringify(data));
      if (fs.existsSync(this.file)) fs.renameSync(this.file, `${this.file}.bak`);
      fs.renameSync(tmp, this.file);
    } catch (err) {
      console.warn(`[STORE] Could not save ${this.file}: ${err.message}`);
    }
  }
}

// ── history ───────────────────────────────────────────────────────────────────────────────────────

const MAX_HISTORY = 3000;
const strip = (url) => url.replace(/^https?:\/\//, '').replace(/^www\./, '');

export class History {
  constructor(entries = []) {
    this.entries = new Map();
    for (const e of Array.isArray(entries) ? entries : []) {
      if (e && typeof e.url === 'string' && /^https?:\/\//.test(e.url)) {
        this.entries.set(e.url, { url: e.url, title: String(e.title || ''), visits: Number(e.visits) || 1, last: Number(e.last) || 0 });
      }
    }
  }

  record(url, title, now = Date.now()) {
    if (!/^https?:\/\//.test(url || '')) return;
    const e = this.entries.get(url) || { url, title: '', visits: 0, last: 0 };
    e.visits += 1;
    e.last = now;
    if (title) e.title = String(title).slice(0, 300);
    this.entries.delete(url); // keep insertion order = recency, for trimming
    this.entries.set(url, e);
    while (this.entries.size > MAX_HISTORY) this.entries.delete(this.entries.keys().next().value);
  }

  setTitle(url, title) {
    const e = this.entries.get(url);
    if (e && title) e.title = String(title).slice(0, 300);
  }

  /** Pages matching what was typed: address prefix first, then address or title matches; frequent and recent first. */
  query(text, limit = 6, now = Date.now()) {
    const q = String(text || '').trim().toLowerCase();
    if (!q) return [];
    const words = q.split(/\s+/);
    const scored = [];
    for (const e of this.entries.values()) {
      const addr = strip(e.url).toLowerCase();
      const title = e.title.toLowerCase();
      let base = 0;
      if (addr.startsWith(strip(q))) base = 3;
      else if (addr.includes(q)) base = 2;
      else if (words.every((w) => title.includes(w) || addr.includes(w))) base = 1;
      if (!base) continue;
      const days = Math.max(0, (now - e.last) / 86400000);
      scored.push([base * (1 + Math.log(e.visits)) / (1 + days / 7), e]);
    }
    return scored.sort((a, b) => b[0] - a[0]).slice(0, limit).map(([, e]) => ({ url: e.url, title: e.title }));
  }

  toJSON() {
    return [...this.entries.values()];
  }
}

// ── bookmarks ─────────────────────────────────────────────────────────────────────────────────────

export const DEFAULT_BOOKMARKS = [
  { url: 'https://www.google.com/', title: 'Google' },
  { url: 'https://github.com/', title: 'GitHub' },
  { url: 'https://www.wikipedia.org/', title: 'Wikipedia' },
  { url: 'https://news.ycombinator.com/', title: 'Hacker News' },
  { url: 'https://www.youtube.com/', title: 'YouTube' },
];

export class Bookmarks {
  constructor(list) {
    const src = Array.isArray(list) ? list : DEFAULT_BOOKMARKS;
    this.list = src.filter((b) => b && /^https?:\/\//.test(b.url || '')).map((b) => ({ url: b.url, title: String(b.title || b.url).slice(0, 200) }));
  }

  has(url) {
    return this.list.some((b) => b.url === url);
  }

  add(url, title) {
    if (!/^https?:\/\//.test(url || '') || this.has(url)) return false;
    this.list.push({ url, title: String(title || url).slice(0, 200) });
    return true;
  }

  remove(url) {
    const before = this.list.length;
    this.list = this.list.filter((b) => b.url !== url);
    return this.list.length !== before;
  }

  toggle(url, title) {
    return this.has(url) ? (this.remove(url), false) : (this.add(url, title), true);
  }

  toJSON() {
    return this.list;
  }
}

// ── permissions ───────────────────────────────────────────────────────────────────────────────────

/** Granted without asking, as in Chrome: harmless or needed by ordinary pages. */
export const AUTO_ALLOW = new Set(['fullscreen', 'clipboard-sanitized-write', 'pointerLock', 'mediaKeySystem', 'keyboardLock']);

/** Asked of the user; the text completes "<site> wants to …". Anything not listed here or above is denied. */
export const ASKABLE = {
  media: 'use your camera or microphone',
  geolocation: 'know your location',
  notifications: 'show notifications',
  'clipboard-read': 'see text and images you copy',
  midi: 'use your MIDI devices',
  midiSysex: 'control and reprogram your MIDI devices',
  'idle-detection': 'know when you are actively using this device',
  'window-management': 'manage windows on all your displays',
  'storage-access': 'use its cookies and site data while embedded in another site',
  'top-level-storage-access': 'use its cookies and site data while embedded in another site',
  openExternal: 'open a link in another app',
  fileSystem: 'see or edit files on your computer',
};

/** The decision keys a request covers: one per media type, so camera and microphone are decided separately. */
export function permissionKeys(permission, details = {}) {
  if (permission === 'media') {
    const types = (details.mediaTypes && details.mediaTypes.length ? details.mediaTypes : ['audio', 'video']).slice().sort();
    return types.map((t) => `media:${t}`);
  }
  if (permission === 'openExternal' && details.externalURL) {
    try { return [`openExternal:${new URL(details.externalURL).protocol}`]; } catch { return ['openExternal:?']; }
  }
  return [permission];
}

export class PermissionDecisions {
  constructor(data) {
    this.map = data && typeof data === 'object' && !Array.isArray(data) ? { ...data } : {};
  }

  /** 'allow' | 'deny' | 'ask' for a request from `origin` (an https://host origin, never a full URL). */
  decide(origin, permission, details = {}) {
    if (AUTO_ALLOW.has(permission)) return 'allow';
    if (!(permission in ASKABLE) || !/^https?:\/\//.test(origin || '')) return 'deny';
    const states = permissionKeys(permission, details).map((k) => this.map[`${origin}|${k}`]);
    if (states.some((s) => s === 'deny')) return 'deny';
    if (states.every((s) => s === 'allow')) return 'allow';
    return 'ask';
  }

  remember(origin, permission, details, allow) {
    for (const k of permissionKeys(permission, details)) this.map[`${origin}|${k}`] = allow ? 'allow' : 'deny';
  }

  forget(origin) {
    for (const k of Object.keys(this.map)) if (k.startsWith(`${origin}|`)) delete this.map[k];
  }

  toJSON() {
    return this.map;
  }
}

export function originOf(url) {
  try {
    const u = new URL(url);
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.origin : '';
  } catch {
    return '';
  }
}
