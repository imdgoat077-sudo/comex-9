import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSuggestions, displayUrl, looksLikeUrl, toNavigableUrl } from './omnibox.js';

test('addresses open, everything else searches', () => {
  const cases = {
    'https://example.com/a?b=1': 'https://example.com/a?b=1',
    'example.com': 'https://example.com',
    'docs.python.org/3/library': 'https://docs.python.org/3/library',
    'localhost:3000': 'http://localhost:3000',
    'localhost': 'http://localhost',
    'localhost:5173/app': 'http://localhost:5173/app',
    '192.168.1.1': 'http://192.168.1.1',
    '10.0.0.5:8080/x': 'http://10.0.0.5:8080/x',
    'myrouter:8080': 'https://myrouter:8080',
    'comex://launchpad': 'comex://launchpad',
  };
  for (const [input, want] of Object.entries(cases)) assert.equal(toNavigableUrl(input), want, input);
  for (const input of ['best headphones', 'what is 2.5 times 4', 'javascript:alert(1)', 'file:///etc/passwd', '999.1.1.1', 'hello']) {
    assert.ok(toNavigableUrl(input).startsWith('https://www.google.com/search?q='), input);
  }
  assert.equal(toNavigableUrl('   '), null);
  assert.equal(looksLikeUrl('github.com'), true);
  assert.equal(looksLikeUrl('github'), false);
  assert.equal(displayUrl('comex://launchpad'), '');
});

test('suggestions: what Enter does first, then tabs, bookmarks, history, each address once', () => {
  const rows = buildSuggestions('git', {
    tabs: [{ id: 't1', url: 'https://github.com/x', title: 'X on GitHub' }, { id: 't2', url: 'https://github.com/me', title: 'Me' }],
    bookmarks: [{ url: 'https://github.com/x', title: 'dup' }, { url: 'https://gitlab.com/', title: 'GitLab' }],
    history: [{ url: 'https://github.com/', title: 'GitHub' }, { url: 'https://gitlab.com/', title: 'GitLab' }],
    activeTabId: 't2',
  });
  assert.equal(rows[0].type, 'search');
  assert.deepEqual(rows.map((r) => r.type), ['search', 'tab', 'bookmark', 'history']);
  assert.equal(rows.find((r) => r.type === 'tab').tabId, 't1');
  assert.deepEqual(buildSuggestions('', {}), []);
  assert.equal(buildSuggestions('github.com', {})[0].type, 'url');
});
