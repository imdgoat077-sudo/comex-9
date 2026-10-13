import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { Bookmarks, History, JsonFile, PermissionDecisions, originOf } from './stores.js';

test('JsonFile writes atomically and falls back to the backup', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'comex-store-'));
  const file = path.join(dir, 'session.json');
  const f = new JsonFile(file);
  assert.deepEqual(f.read({ empty: true }), { empty: true });
  f.write({ v: 1 }); f.flush();
  f.write({ v: 2 }); f.flush();
  assert.deepEqual(new JsonFile(file).read(null), { v: 2 });
  fs.writeFileSync(file, '{ corrupt');
  assert.deepEqual(new JsonFile(file).read(null), { v: 1 }); // the previous good copy
});

test('history suggests by address prefix first, then title; frequent pages rank higher', () => {
  const h = new History();
  const now = 10 * 86400000;
  h.record('https://github.com/anthropics', 'Anthropic on GitHub', now);
  h.record('https://www.gitlab.com/', 'GitLab', now);
  for (let i = 0; i < 5; i += 1) h.record('https://github.com/', 'GitHub', now);
  h.record('https://news.ycombinator.com/', 'Hacker News', now);
  assert.deepEqual(h.query('git', 6, now).map((e) => e.url)[0], 'https://github.com/');
  assert.deepEqual(h.query('hacker', 6, now).map((e) => e.url), ['https://news.ycombinator.com/']);
  assert.deepEqual(h.query('', 6, now), []);
  h.record('javascript:alert(1)', 'x');
  assert.equal(h.toJSON().some((e) => e.url.startsWith('javascript')), false);
});

test('bookmarks toggle and reject unsafe URLs', () => {
  const b = new Bookmarks([]);
  assert.equal(b.toggle('https://a.test/', 'A'), true);
  assert.equal(b.has('https://a.test/'), true);
  assert.equal(b.toggle('https://a.test/', 'A'), false);
  assert.equal(b.add('file:///etc/passwd', 'x'), false);
  assert.ok(new Bookmarks().list.length > 0); // first run: defaults
});

test('permissions: harmless ones allowed, unknown ones denied, the rest asked once per site', () => {
  const p = new PermissionDecisions();
  const site = originOf('https://meet.example.com/room/1');
  assert.equal(site, 'https://meet.example.com');
  assert.equal(p.decide(site, 'fullscreen'), 'allow');
  assert.equal(p.decide(site, 'unknown'), 'deny');
  assert.equal(p.decide(site, 'hid'), 'deny');
  assert.equal(p.decide(site, 'media', { mediaTypes: ['audio', 'video'] }), 'ask');
  p.remember(site, 'media', { mediaTypes: ['audio'] }, true);
  assert.equal(p.decide(site, 'media', { mediaTypes: ['audio'] }), 'allow');
  assert.equal(p.decide(site, 'media', { mediaTypes: ['audio', 'video'] }), 'ask'); // camera not decided yet
  p.remember(site, 'geolocation', {}, false);
  assert.equal(p.decide(site, 'geolocation'), 'deny');
  assert.equal(p.decide('https://other.example', 'geolocation'), 'ask');
  assert.equal(p.decide('file://', 'geolocation'), 'deny');
  assert.equal(p.decide(originOf('chrome://settings'), 'notifications'), 'deny');
});
