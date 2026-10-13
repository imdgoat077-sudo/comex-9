# Comex browser UX, tab groups and Google sign-in: Phase 0 audit and proposal

Status: proposal for approval. No production code was changed for this phase.
Audited: `electron/main.js`, `electron/preload.js`, `src/App.jsx`, `src/components/Navbar/*`, `src/components/Canvas/BrowserCanvas.jsx`,
`src/components/Bookmarks/*`, `src/components/Modals/ShortcutsModal.jsx`, the tab parts of `ChatDrawer.jsx`, the chat/group
endpoints in `agent_service.py` and `services/chat_store.py`. Electron 43.4.0 (Chromium 150.0.7871.224).

---

## 1. Current state

### What exists and works
- **Tabs.** Each one is a native `WebContentsView` held in `views` in the main process. The React UI holds a parallel `tabs` array.
  - Create, close, switch, back, forward, reload and navigate go over IPC (`tabs-*`).
  - Title, favicon, loading, URL and audio updates flow back through `tab-update`.
- **Groups.** These are implicit:
  - Every tab carries a `groupId`. A tab the user opens is `grp-<tabId>`.
  - Agent tabs and chat links join the chat's group.
  - The backend `ChatStore` records membership (`group_tabs`) and one live conversation per group.
  - The strip draws a chip per group, coloured by what the AI is doing (working, done, failed, stopped).
- **Agents.** The agent shield (a transparent view stacked above a working tab) blocks input and shows status.
  - Worker tabs open visibly inside their group.
  - After a run, the non-result agent tabs close (`handleCloseTabs`).
  - The agent can switch between tabs of its group.
- **Layout.** Bounds come from `.browser-body-layout` plus the 28 px titlebar offset, with a `ResizeObserver`. The main process also clamps the bounds.
- **Security already in place:**
  - Privileged IPC accepts only the main window's top frame (`isAuthorizedSender`).
  - Navigation to internal ports (9222, 8000, 20128) and to non-http(s) schemes is blocked.
  - The internal token never reaches the renderer.

### Defects found (evidence: file and line)
| # | Defect | Where | Effect |
|---|---|---|---|
| D1 | Keyboard shortcuts live in a React `keydown` listener. When a web page has focus, its view gets the keys, so ⌘T, ⌘W, ⌘R, ⌘J don't fire. There is no application `Menu`, so Electron's default menu applies; its Close (⌘W) and Reload (⌘R) roles act on the focused window. | `App.jsx:406`, no `Menu` in `main.js` | Shortcuts work only after clicking the chrome. **To verify live:** ⌘W or ⌘R on a focused page may close or reload the whole Comex window. |
| D2 | ⌘L is listed in the Shortcuts dialog but not implemented | `ShortcutsModal.jsx:13`, `App.jsx:406` | Feature advertised but missing |
| D3 | The shortcut effect depends on `[activeTabId, isChatOpen]`, but `handleCloseTab` reads `tabs` from that render. After agent tabs are added without the active tab changing, ⌘W filters a stale array. | `App.jsx:277, 427` | Closing a tab can drop other tabs from the strip while their native views stay alive (leaked views) |
| D4 | The omnibox suggestions and the agent hover card are React elements that reach below the toolbar. Native views always draw above React (CLAUDE.md §3.1). | `BrowserNavbar.jsx:304, 40` | With a site open, the part of the dropdown or card over the page is hidden behind the page |
| D5 | Omnibox suggestions are four hard-coded sites. There is no history or bookmarks, and no "search for…" row. | `BrowserNavbar.jsx:10` | Looks like autocomplete but isn't |
| D6 | The bookmark star toggles React state only. Bookmarks are a fixed list. | `BrowserNavbar.jsx:295`, `BookmarksBar.jsx` | The star does nothing persistent |
| D7 | `getTitleFromUrl` returns placeholder titles ("Quantum Teleportation - Wikipedia", "comex-browser/core - GitHub") | `App.jsx:185` | Wrong tab titles until the page reports its own |
| D8 | No Stop button, and no stop IPC. Reload is ignored on `about:blank`. | `BrowserNavbar.jsx:266`, `main.js:763` | Can't stop a slow page |
| D9 | `did-fail-load` only clears the spinner. There is no error page and no retry. | `main.js:260` | Failed loads show a blank page |
| D10 | `toNavigableUrl` sends `localhost:3000` and other dotless hosts to Google search. The https-only check is a string prefix test. | `BrowserNavbar.jsx:103` | Local development URLs don't open |
| D11 | The security badge is a lock based on the URL prefix only. Certificate errors aren't handled or shown. | `BrowserNavbar.jsx:143`, no `certificate-error` handler | Misleading security state |
| D12 | `handleLandingPrompt` sets bounds with a hard-coded `y: 138` and `innerHeight - 138`, against the CLAUDE.md rule | `App.jsx:510` | Wrong frame for one render, and the view can cover the chrome |
| D13 | `syncActiveView` detaches every view and re-adds the active one on every bounds message, with about 10 `console.log` lines each time | `main.js:147` | Extra work and log noise on every resize and drawer drag |
| D14 | Closing a tab only reports `/chat/tabs/{id}/closed`. A running agent bound to that tab isn't stopped. There is no "close group" at all. | `App.jsx:277`, `agent_service.py:3060` | Orphaned workers keep running against a dead target until they fail |
| D15 | Nothing restores tabs or groups. React state starts with one Launchpad tab. Chats persist in SQLite, but the tabs do not. | `App.jsx:32` | Every restart loses all tabs |
| D16 | `window.open` is always denied and replaced by a new top-level tab with no opener (`setWindowOpenHandler` returns `deny`) | `main.js:308` | Popup sign-ins ("Sign in with Google/Apple/Microsoft" on other sites, payment 3-D Secure) can't post back to `window.opener` and break |
| D17 | Popups from a page in a group open as a new group of their own (`ownGroup(newTabId)`) | `App.jsx:128` | A site's popup leaves its group and gets a separate chat |
| D18 | Web tabs run with `sandbox: false`. No `setPermissionRequestHandler` is installed, so Electron approves every permission request by default (camera, microphone, geolocation, notifications…). | `main.js:476`, no session config | Any website gets every permission silently |
| D19 | No handler for HTTP basic-auth (`app.on('login')`) and no download UI | `main.js` | Basic-auth sites fail silently; downloads are invisible |
| D20 | `openExternal` is exposed in preload, but there is no `open-external` handler in main | `preload.js:8` | Dead API |
| D21 | Tab ids are `tab-${Date.now()}`, and `__new_tab__` uses the same scheme | `App.jsx:201`, `main.js:319` | Two tabs created in the same millisecond collide |
| D22 | No tab drag-and-drop reorder, no context menu, no pinning, no middle-click close, no tab overflow scrolling. The strip clips. | `BrowserNavbar.jsx:180`, CSS | Many tabs become unreachable |

---

## 2. Google sign-in: what is known and what still has to be reproduced

### Evidence collected (an isolated Electron 43 process with its own profile, not the Comex app)
| Configuration | User-Agent Google receives | What JavaScript reports (`navigator.userAgentData`) | Sign-in page Google serves |
|---|---|---|---|
| Comex today (UA override + remote-debugging port) | `… Chrome/128.0.0.0 Safari/537.36` | brands: Chromium **150**, no "Google Chrome" brand | full `GlifWeb` flow |
| Default UA + debugging port | `… Chrome/150.0.7871.224 Electron/43.4.0 …` | Chromium 150 | `WebLite` flow (Google recognises Electron) |
| Default UA, no debugging port | same as above | Chromium 150 | `WebLite` |

1. **Comex's user agent contradicts itself.** The hard-coded string claims Chrome 128, 22 releases old. The browser's own Client Hints say Chromium 150 and show no Chrome brand. A mismatched identity is a common risk signal, and it misinforms every site's feature detection.
2. **Without the override, Google identifies Electron** and serves its reduced sign-in.
3. **Google's published policy.** Since 4 January 2021 it blocks Google Account sign-in from embedded browser frameworks such as CEF and Electron, because it can't tell them apart from man-in-the-middle phishing. It points developers to browser-based OAuth or a full native browser. Separately, its OAuth endpoint rejects embedded webviews with `disallowed_useragent`.
4. **Not yet reproduced:** the final rejection screen. My scripted email entry did not advance Google's page from a hidden window, and I did not push further with fake input. This needs one real attempt in the running app (procedure in §2.3).

**Why Comet works:** Comet is a full Chromium-based browser. Google treats it like other Chromium browsers. Comex is an app built on an embedded framework, which is exactly the category the policy names.

### 2.1 Two separate requirements
1. **Signing in to Google websites inside Comex** (Gmail, YouTube, Drive in a tab), with the cookies kept in Comex's session.
2. **Comex itself getting access to Google services** (for example, agents reading Gmail or Calendar through APIs).

### 2.2 Legitimate options
| Option | Covers | Effort | Verdict |
|---|---|---|---|
| A. Remove the fake `Chrome/128` override and report the real engine | Correctness on every site | S | **Do it.** Hiding the Electron identity to pass Google's check would be the spoofing you ruled out, so the honest default is the real UA. |
| B. Fix popups (D16): allow `window.open` as a real child window with its opener for auth and payment flows | Sign-in popups on all other sites (Sign in with Google buttons on third-party sites, Microsoft, Apple, Stripe) | M | **Do it.** This is a Comex bug, not a Google policy issue. |
| C. When Google rejects the sign-in, detect its rejection page and show a clear Comex notice: why, and "Open in your default browser" (`shell.openExternal`) | Requirement 1, honestly | S | **Do it** |
| D. OAuth for Comex itself: system browser + loopback redirect `127.0.0.1:<random port>` + PKCE + `state`; refresh token encrypted with `safeStorage` (macOS Keychain); Google "Desktop app" client type | Requirement 2 fully | M | **Do it when a Google API feature is planned** |
| E. Rebuild Comex on full Chromium (a fork, like Comet, Arc, Brave) | Requirement 1 fully | Very large (months), and a different product | Long-term only |
| F. Run a real Chrome or Chromium as the engine, driven over CDP, with a dedicated profile | Requirement 1 fully | Large; tabs could no longer be embedded in the Comex window | Possible, but it changes the whole architecture. Discuss before choosing. |
| G. User-agent or client-hint spoofing, stripping the `Electron` token, proxying Google's traffic | — | — | **Excluded:** it defeats Google's policy, and the policy forbids proxying. |

Recommendation: A + B + C now, D when needed, and an explicit product decision on E or F later. Tell users plainly that signing in to Google websites inside Comex isn't supported by Google for embedded browsers.

### 2.3 Reproduction procedure (needs your account; about 2 minutes)
1. In Comex, open `https://accounts.google.com`, enter your email, press Next.
2. Record:
   - the exact screen text (for example "Couldn't sign you in / This browser or app may not be secure"),
   - the URL in the address bar (a `/signin/rejected` path is expected),
   - whether a password field ever appeared.
3. Repeat with `https://login.microsoftonline.com` and a third-party "Sign in with Google" button (for example on Medium or Canva). This separates Google's policy from the popup bug (D16).
4. After the fixes:
   - sign in to a supported provider;
   - quit and relaunch, and check the session persists;
   - sign out, sign in with a second account, and check cookies are kept per profile.

---

## 3. Architecture decisions

### 3.1 One owner for tabs and groups: the main process
Today React owns the tab list and Electron owns the views. The two drift apart (D3, D14, D21), and a closed group can't release native resources from React alone.

- **`TabManager` in `electron/` (new module).** It is the source of truth for tabs, groups, order, active tab, pinned and collapsed state.
- **Persistence.** It writes a session file `userData/session.json` atomically (write a temporary file, then rename), debounced to 500 ms. Restores work even when the Python backend is down.
- **React renders a snapshot.** It sends intents (`tabs.create`, `groups.move`, …) and receives `session-state` snapshots. Its own `history[]` copy goes away.
- **Identity contract:**
  - `tabId` and `groupId` are random UUIDs created in main.
  - A group has `{id, name, color, collapsed, createdAt}` and nothing about chats.
  - The backend maps `groupId → conversation` (`ChatStore.groups`) as it does today, and a group may have none.
  - `workerId`, `taskId`, `run_id` and `conversation_id` never encode a group.

### 3.2 Lifecycle operations (single code paths)
| Operation | Steps |
|---|---|
| `closeTab(tabId)` | 1. If an agent is bound to the tab, stop only that agent: for a worker, cancel the worker (new backend `POST /agent/tabs/{tabId}/stop`); for the single agent working in this tab, stop its run. 2. Destroy the view. 3. Report `/chat/tabs/{id}/closed`. 4. Choose the next active tab in the same group, else a neighbour. |
| `closeGroup(groupId)` | 1. Ask for confirmation when the group has more than one tab or an agent is working. 2. Stop every run of the group (new `POST /chat/groups/{id}/close` → orchestrator `cancel_run` for that group's runs plus the single-agent stop). 3. Destroy all its views, worker tabs included. 4. Close the conversation, which stays in History and is compacted. 5. Offer "Undo" for 10 seconds, restoring the URLs and membership. |
| `moveTab(tabId, groupId, index)` | Update membership and order in main, then `ChatStore.join_group` and `remove_tab` |
| Agent tab opened | Already explicit (`tabs-open-agent` with `groupId`). Now created through `TabManager`. |

The backend keeps a `group_id → {run ids, single-agent task ids}` index, so stopping a group is one lookup, never URL guessing.

### 3.3 Anything that overlaps the page must not be React (D4)
- **Context menus** (tab, group, page): native `Menu.popup`. They look native and draw above web content.
- **Omnibox suggestions and agent hover card:** one small transparent `WebContentsView` popup layer, stacked like the agent shield, shown only while open. Alternatively, keep them inside the chrome's height.

### 3.4 Keyboard (D1, D2)
An application `Menu` with accelerators (New Tab ⌘T, Close Tab ⌘W, Reopen Closed Tab ⇧⌘T, Focus Address Bar ⌘L, Reload ⌘R, Stop Esc, Back ⌘[, Forward ⌘], next/previous tab ⌃Tab/⌃⇧Tab, ⌘1…9, Assistant ⌘J). It works whichever view has focus, and it replaces Electron's default menu so ⌘W can never close the window.

### 3.5 Security hardening (D18–D20)
- `sandbox: true` for web tab views.
- A session permission handler: deny by default, prompt the user per origin for camera, microphone, location and notifications, and remember the choice.
- A `certificate-error` interstitial, an `app.on('login')` dialog, and a download shelf. Wire or remove `openExternal`.

---

## 4. Feature inventory and priority
Effort: S (≤1 day), M (2–4 days), L (≥1 week).

| Area | Feature | User benefit | Effort | Depends on | Priority |
|---|---|---|---|---|---|
| Keyboard | App menu accelerators, ⌘L, ⇧⌘T, ⌘1–9 | Shortcuts work everywhere | S | — | **P0** |
| Tabs | `TabManager` in main + session restore | Nothing lost on restart; no leaked views | L | — | **P0** |
| Tabs | Close tab stops its agent; close group with confirm + undo | No orphan workers; safe cleanup | M | TabManager, backend stop endpoints | **P0** |
| Groups | Create, rename, recolour, collapse/expand, "New tab in group", move tab between groups, "Open link in new group" | Real tab groups | M | TabManager | **P0** |
| Tabs | Drag to reorder and drag into or out of groups; overflow scrolling with a fade | Manage many tabs | M | TabManager | **P0** |
| Tabs | Native context menus (tab, group, page: Back, Reload, Copy link, Open link in new tab, Inspect) | Expected browser behaviour | S | §3.3 | **P0** |
| Address bar | Stop button, error pages with Retry, localhost and IP handling, Esc to revert | Basic navigation reliability | S | — | **P0** |
| Address bar | Real suggestions: history, open tabs, bookmarks, "Search Google for…" | Faster navigation | M | history store, popup layer | P1 |
| Address bar | Security indicator from certificate state; interstitial on certificate errors | Honest security state | S | — | P1 |
| Auth | Popups with opener (D16), Google rejection notice, real UA (A, B, C) | Sign-in works for other providers; clear Google message | M | — | **P0** |
| Auth | OAuth for Comex (D) | Agents can use Google APIs | M | product need | P2 |
| Security | Sandbox, permission prompts, basic-auth dialog, downloads | Safe by default | M | — | **P0** (sandbox, permissions), P1 (others) |
| Agents | Agent badge, owner and status in the context menu; "Stop agent" per tab; worker tabs marked as owned by a group | Understandable agent tabs | S | TabManager | P1 |
| Polish | Design tokens for chrome, consistent states, reduced motion, focus rings, tab strip at 900–2560 px | Cohesive feel | M | Phases 1–2 | P1 |
| Bookmarks | Real bookmarks (star saves, bar editable) | Removes a fake control | S | session store | P1 |
| Pinning | Pinned tabs (icon-only, restored first) | Common need | S | TabManager | P2 |
| Perf | `syncActiveView` updates only what changed; drop the per-event logs | Smoother resizing and drawer drag | S | — | P1 |

---

## 5. UI direction
- **Chrome-like structure:** the tab strip in the titlebar row (traffic-light spacer kept), then a single toolbar row: back, forward, reload/stop, omnibox, assistant.
- **Groups as Chrome does them:** a coloured label pill before the group's tabs and a 2 px underline in the group colour.
  - Click the label to collapse or expand; right-click for rename, colour, new tab in group, ungroup, close group.
  - The AI state stays as today, as a small status dot plus timer inside the label (working amber, done green, failed red). It doesn't replace the group colour, so colour still says which group and the dot says what the AI is doing.
- Graphite tokens, no gradients, one radius scale (6 px controls, 8 px popovers), 120–160 ms state transitions, `prefers-reduced-motion` honoured, visible focus rings.

---

## 6. Phased roadmap with acceptance criteria
| Phase | Scope | Done when (measured) |
|---|---|---|
| 1. Chrome and address bar | Menu accelerators, Stop, error pages, URL handling, popup layer for suggestions, D7/D12/D13 fixes, real UA | ⌘T/⌘W/⌘L/⌘R work with focus inside a page (live check); suggestions are fully visible over a loaded site; no layout overlap at 900, 1280, 1920 and 2560 px with the drawer at minimum and maximum width; a resize causes ≤1 `setBounds` per frame |
| 2. Tabs and groups | `TabManager`, restore, groups (create, rename, colour, collapse, move, drag), context menus, close-group lifecycle and backend stop endpoints | After a restart, tabs, groups, order and active tab are restored in under 1 s; closing a group leaves 0 views and 0 running workers for it within 2 s (checked through a debug IPC count and backend run state), and other groups are untouched; closing a worker tab cancels only that worker, and the parent conversation remains |
| 3. Sign-in | Reproduce (§2.3), then options A, B and C; D if approved | The reproduction is recorded verbatim; third-party "Sign in with Google" and Microsoft popups complete; the Google rejection shows the Comex notice; the session persists across restart for supported providers |
| 4. Polish | Tokens, states, motion, accessibility, perf | Keyboard-only use of the strip and groups; contrast ≥ 4.5:1 for text; no long tasks over 50 ms during tab switch (Performance panel) |
| 5. Validation | Tests and a live Electron pass | Unit tests for `TabManager` operations and the lifecycle; backend tests for group stop; full suite and build green; a live checklist run, with the log checked for leaked views or orphaned workers |

Behaviour I'll only claim after a live Electron run (not mocks): shortcuts with page focus, the popup layer over pages, restore after relaunch, group close cleanup, and the sign-in flows.

## Sources
- [Google: guidance for the block on less secure browsers and apps (embedded frameworks, 2020)](https://developers.googleblog.com/2020/08/guidance-for-our-effort-to-block-less-secure-browser-and-apps.html)
- [Google: OAuth 2.0 changes for embedded webviews (`disallowed_useragent`, 2021)](https://developers.googleblog.com/2021/06/upcoming-security-changes-to-googles-oauth-2.0-authorization-endpoint.html)
- [IETF OAuth 2.0 for Native Apps (system browser, loopback redirect)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-native-apps-09)
- [Electron security checklist (permission handler, sandbox)](https://electronjs.org/zh/docs/latest/tutorial/security)
- [Doyensec: Electron web API default permissions](https://blog.doyensec.com/2022/09/27/electron-api-default-permissions.html)
