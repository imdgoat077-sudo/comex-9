# Hybrid browser intelligence: engineering note

Written 2026-10-12 before any code change in this effort. Branch `feature/multi-agent-orchestrator-mvp`, base commit `02edc0b`,
working tree clean apart from one intentionally untracked research file (`Trials/comet_deep_research/16_extracted_source_and_disassembly.md`).
Every statement below is tagged **[verified]** (I checked it in code, history, a running process, or the installed app in this session),
**[research]** (taken from the Comet research notes, with their evidence level A to D), or **[inference]**.

## 1. The architecture that exists today

- Electron shell (CDP on 9222), React UI, FastAPI backend on 8000, Kuzu graph memory, model `ag/gemini-3.8-flash` through the 9Router proxy on 20128. [verified: listening ports and `.env`]
- The agent has **seven typed browser tools** built in `agent_service._build_browser_tools`: `browser_click` (ref / text / selector), `browser_type`, `browser_navigate`, `browser_extract`, `browser_inspect`, `browser_find`, `browser_sequence`. They call `ComexToolService` in process. [verified]
- Every tool call is authorized in `_authorize_and_resolve_session`: context claims, lease revalidation, canonical Chromium target-id match, deadline and cancellation, then a per-tab `action_lock`. Clicks and typing are bound to a DOM node (`TargetBinding`), pass Method E actionability, the ReflexEngine rules (dialog, navigation, overlay, geometry) and the ActuatorGate before any CDP input is sent. [verified: `services/tool_service.py`, `nervous/*`]
- `perform_sequence` already runs up to a bounded number of steps with typed **pre- and postconditions** (`url_contains`, `element_visible`, `text_contains`, and others). [verified]
- The multi-agent orchestrator plans with one LLM call, runs workers concurrently in visible tabs under leases, enforces a per-worker deadline and action budget, then synthesizes. [verified]

## 2. What the current layer cannot do (verified by reading the code)

| Missing primitive | Consequence |
|---|---|
| Key presses and chords | Wordle (keyboard driven), shortcuts, game controls |
| Scrolling and wheel input | Long pages, virtualised lists, canvases |
| Coordinate click, move, drag | Chess boards drawn with divs or canvas, Excalidraw |
| Arbitrary page reads (`evaluate`) | Board state, attributes, geometry, canvas size |
| Screenshot returned to the model | Any canvas or visually encoded state |
| Complete table read with completeness flags | VTOP grade history, any dense table (`extract` is capped at 8000 chars) |
| State-based wait | Fixed assumptions about when a page has settled |

## 3. The old Browser Harness, exactly [verified]

- Browser Harness 0.1.10 is **not Python running in the page**. The agent wrote a Python snippet; `run_browser_harness` piped it to the `browser-harness` CLI as a subprocess (90 s timeout); a daemon held the CDP socket. The snippet had helpers: `cdp(method, **params)` (raw CDP), `js(expr)` (Runtime.evaluate), `click_at_xy`, `press_key`, `type_text`, `scroll`, `capture_screenshot`, `wait_for_element`, `wait_for_network_idle`, `page_info`, tab helpers, plus loops and conditionals in Python.
- The old agent's system prompt embedded the entire harness SKILL.md. The agent therefore had **raw CDP plus arbitrary JavaScript plus coordinate input in a single tool call, with no policy layer**.
- The harness returns stdout only. `capture_screenshot` wrote a file the model never saw. So the old "visual" success came from reading DOM state with `js()` and acting with coordinates, not from model vision.

## 4. Why the capabilities were lost [verified in code and history]

1. `nervous/action_policy.py::validate_harness_script_safety` (Phase 1.5 hardening, tested in `tests/test_phase1_5_action_hardening.py` and `test_phase1_tab_safety.py`) **explicitly forbids** `click_at_xy`, key dispatch (`press`, `dispatchkeyevent`), `drag_to`, `hover`, and `evaluate`/`js` calls built from f-strings or concatenation.
2. Commit `191f84d` (11 Oct 15:28, "checkpoint after Phase 2.2 baseline") replaced the harness subprocess tool with the in-process typed tools. In `agent_service.py` the harness mentions fell from 23 to 4 (stale comments). The agent's tool list no longer contains a script tool.
3. The typed tools that replaced it cover selector-bound click and type only (section 2).
4. **Strawberry-inspired work was not the cause.** My changes (element refs, `find_by_text`, `browser_sequence` exposure, step labels, dialog auto-answer, delegation) were added on top of that layer after commit `191f84d`; none of them removed a primitive. The earliest session transcript available to me starts at 16:49 IST, after that 15:28 commit, so I can show *when* the capability was removed but not who wrote it. The loss is a deliberate security decision (the policy and its tests are explicit) whose cost was never offset by safe replacements.

## 5. What the Comet research says, and how far I trust it

Level A items are tagged in `evidence_index.json`. I additionally spot-checked the installed Comet extension **read-only** (counting strings in `background.js`, no content copied, nothing modified):
the file is exactly the 773,368 bytes the inventory lists, and it contains `ComputerBatch`, `getFullAXTree`, `captureSnapshot`, `setInterceptDrags`, `pasteFromString`, `mouseWheel`, `getBoxModel`, `Accessibility.loadComplete`, `Page.navigatedWithinDocument`, the viewport-drift error string, and the 1568 and 1.15e6 image limits. [verified]

Ideas I take (architecture and contracts only, no code copied):

| Idea | Research | Status |
|---|---|---|
| Hybrid perception: accessibility tree plus DOM geometry plus optional screenshot, refs for elements | 04, EV-004 (A) | Comex already has refs and inspect; adding geometry, screenshots, and completeness |
| Coordinate geometry: screenshot space, viewport space, DPR; scale to an image budget; abort a coordinate batch if the viewport changed since the screenshot | 06, EV-003 (A) | Implement as `ViewportInfo` with a drift gate |
| Batch actions with settle-wait and jitter | 07 (A) | Extend `perform_sequence`; use state-based settle, no random jitter |
| Event-driven wait instead of sleeps | 07 (A) | Implement from existing world state (navigation, network, DOM revision) |
| Drag via drag-interception, chorded keys, wheel scroll | 05 (A) | Implement drag and key chords with CDP input |
| Clipboard-swap typing | 05 (A) | Not needed first; `Input.insertText` works. Revisit only if a fixture fails |
| Self-healing RPC (reattach, reload on timeout) | 08 (A) | Already partly present; retry once on closed socket |
| Native select popups invisible to screenshots; give the model a hint | 04, 05 (A) | Adopt as a deterministic hint |
| Subagents in isolated tabs | 09, EV-007 (A) | Already implemented differently |

Not verifiable locally (cloud side, level C or D): the backend system prompt and action grammar, how many sub-agents are spawned and why, WebMCP signing. I do not rely on them. The research's own file 15 proposes porting minified functions directly; I am deliberately not doing that.

## 6. Two facts measured this session that shape the design

- **Engine-enforced read-only JavaScript is practical.** Chrome's `Runtime.evaluate` with `throwOnSideEffect: true` blocked every mutation I tried (click, set value, innerHTML, fetch, localStorage.setItem, cookie, location, dispatchEvent, setTimeout), left page state unchanged, and a `timeout` terminated `while(true){}`. It still allows the reads that matter (attributes, class lists, values, rects, computed style, shadow roots, `querySelectorAll`). It blocks `getElementById`, `matches`, `closest`, canvas pixel reads and `elementFromPoint`; those I provide as typed helpers. This gives "bounded, read-only programmatic inspection" without a new unrestricted execution path.
- **The configured model can see screenshots.** A synthetic image was described correctly (left red, right blue, small yellow circle), a no-image control answered "NO IMAGE", and it works through the app's own LangChain client. Cost: about 1.1k extra prompt tokens and no extra latency for a small image. The proxy already adds about 2.4k prompt tokens to every call.

## 7. Decision on "Python-driven" operations

The harness's power was Python plus raw CDP with no policy. Recreating a Python sandbox inside the backend process (which holds the router key) would be the "uncontrolled execution pathway" the brief rules out, and AST allow-lists are not a proof of safety. The capability that mattered is: read arbitrary page state, compute, then act in bounded batches with verification. I recover it with:
(a) a read-only `evaluate` tool (engine-enforced, size and time capped),
(b) typed input primitives (keys, scroll, coordinate click, drag) through the same authorization path,
(c) an extended `browser_sequence` with new step types and postconditions, so a verified multi-step operation costs one model turn,
(d) a complete `read_table`.
The model does the computation (a chess move) between turns; the service does the deterministic execution.

## 8. Proposed changes, in order of expected impact

1. Typed input primitives plus read-only evaluate plus coordinate/viewport layer (restores chess, Wordle, Excalidraw).
2. `read_table` with completeness (restores VTOP-style extraction).
3. Screenshot tool wired so the image reaches the model, with old screenshots dropped from context.
4. Sequence extensions: new step types, state-based `wait_for`, postconditions on every step, partial-result reporting.
5. Deterministic strategy hints (semantic, table, visual) with light instrumentation.
6. Multi-agent: measure the critical path first, then adaptive routing and fewer model turns per worker; benchmark against the preserved baseline.

## 9. Regression matrix (completed with measurements later in this effort)

| Capability | Historical (harness) | Current | Reproduced failure | Root cause / evidence | Correction |
|---|---|---|---|---|---|
| Chess on a real board | `js()` reads board, `click_at_xy` | no coordinate click, no state read | yes, 0 of 5 old code (measured) | policy bans `click_at_xy`; no evaluate | evaluate + pointer click + postcondition |
| Wordle | `press_key`, `js()` tile state | no key tool | yes, 0 of 5 old code (measured) | `press`/`dispatchkeyevent` banned; no key tool | keys + evaluate |
| Excalidraw | `click_at_xy`/CDP mouse drag | no drag | yes on local drawing page, 0 of 5; real site not measured on old code | `drag_to`, mouse methods banned; no drag tool | pointer drag + verification |
| VTOP table | `js()` full table | `extract` capped at 8000 chars | no: old code passed 5 of 5 by paginating (24 calls); cost was speed | `MAX_EXTRACT_CHARS`, text not structure | `read_table` with completeness |
| Text-semantic browsing | works | works | n/a (must not regress) | | regression test |

Updated with actual results in `docs/engineering/hybrid_browser_results.md`.
