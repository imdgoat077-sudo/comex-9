# Hybrid browser tools and multi-agent speed: measured results

Branch `feature/multi-agent-orchestrator-mvp`, base commit `02edc0b`. All changes are uncommitted in the working tree.
"Old code" means commit `02edc0b` run from a git worktree. "New code" means the working tree. Same model
(`ag/gemini-3.8-flash` through the 9Router proxy), same machine, same prompts. No product code was edited while a series ran.
Raw per-trial records are kept under `benchmarks/hybrid/` and `benchmarks/research_paths/` (nothing was overwritten).

## 1. Browser scenarios (success is read from the page, not from what the agent says)

5 trials per cell, 180 s limit per trial. Fixtures are local and synthetic (`tests/fixtures/browser`), served to a throwaway headless Chrome.

| Scenario | Old: passed | Old: median time (range) | Old: tool calls | New: passed | New: median time (range) | New: tool calls |
|---|---|---|---|---|---|---|
| Chess (mate in one on a board) | 0 of 5 | 180 s (74 to 180) | 39 | **5 of 5** | 29.5 s (25 to 56) | 5 |
| Word guessing game (keyboard only) | 0 of 5 | 180 s (all timeouts) | 44 | **4 of 5** | 56.5 s (30 to 180) | 14 |
| Drawing app (rectangle, ellipse inside) | 0 of 5 | 79 s (65 to 148) | 19 | **5 of 5** | 21.9 s (21 to 29) | 5 |
| Grade table, 57 rows, paginated | 5 of 5 | 75 s (75 to 84) | 24 | 5 of 5 | **30.6 s** (26 to 44) | **6** |
| Shop search and add to cart | 5 of 5 | 40 s (27 to 44) | 9 | 5 of 5 | 30.4 s (30 to 47) | 9 |

Notes
- Files: `benchmarks/hybrid/before*`, `benchmarks/hybrid/after*`, summaries `before.out` and `after.out`.
- The one new-code failure (word game, trial 3) played 4 rows in 180 s and did not find the word. The tools worked; it used three
  tool calls and a model turn per guess, which is slow. It is a game-play and loop-cost failure, not a tool failure.
- Shop is unchanged on tool calls; its 10 s difference is within run-to-run noise and is not claimed as an improvement.
- The word game's answer is scored on a local server, so the agent cannot read it from the page (an earlier fixture leaked it; fixed).

### Real site: Excalidraw (new code only)
Success rule fixed before running: the scene Excalidraw saves in the page contains a rectangle larger than 40 px and an ellipse
larger than 20 px with the ellipse's box fully inside the rectangle's. The canvas is cleared before every trial.
Result: **5 of 5**, median 23.2 s (21.8 to 32.0), 4 tool calls median. Files: `benchmarks/hybrid/excalidraw_after_v2*`.
- The old code was not measured on the real site (stopped by the user's decision). Its only evidence is the local drawing page above (0 of 5).
- A first run, `excalidraw_after_visible_INVALID_leftover_scene`, is **invalid**: the saved scene accumulated across trials and the check
  could pass on leftovers. It is kept for the record and not counted.
- Runs were in a visible Chrome window with its own profile. A real, repeatable one-shot test of the real NYT Wordle was not run (it can only be played once a day).

## 2. Multi-agent research speed

Task: "best research papers on multi-agent orchestration", 5 trials per cell, isolated backend with an empty throwaway graph database.
Like-for-like set: `baseline_clean` (old code) against `hybrid_v1` (new code), `benchmarks/research_paths/`.

| Median (range) | Old code | New code |
|---|---|---|
| Single agent, wall time | 55 s (44 to 118) | 56 s (49 to 58) |
| Multi agent, wall time | 88 s (85 to 114) | **59 s** (55 to 61) |
| Multi agent, tool calls | 30 | **12** |
| Planning | 9.6 s | 8.7 s |
| Slowest worker | 63 s | **39 s** |
| After workers (synthesis) | 15 s | 10 s |
| Multi over single | 1.60x | **1.05x** |
| Papers in the answer | 12 | 7 |
| Links reachable | 46 of 60 (77%) | 33 of 37 (89%) |

- All 20 runs succeeded. Per-call model time is unchanged (about 4.3 s).
- The speedup came with less coverage: 7 papers against 12. I have not judged paper quality; the saved answers are in `*_answer.md` for review.
- The 1.25x target is met only in this empty-memory condition. In the user's real app a single agent often gets a graph-memory hit and answers in about 25 s
  (older sets `before` and `after`), which would put multi at about 2.3x that. That ratio was not re-measured in this series.
- Fixed model calls (planning plus synthesis) are about 17 to 19 s and were not removed.
- What changed: pages the plan names are read before the first model call with a per-page cap of 8 s, the first page is not
  re-opened, workers get at most 3 extra browser actions after the pre-read, the planner prefers fast pages, and slower workers can be asked to wrap up.

## 3. Regression matrix (completed)

| Capability | Historical | Before this work | Reproduced failure | Root cause | Correction |
|---|---|---|---|---|---|
| Chess | read board, click by pixel | no coordinate click | **yes, 0 of 5** (timeouts, board never changed) | policy bans coordinate input; no page-state tool | `browser_evaluate`, `browser_pointer`, `browser_screenshot` |
| Word game | key presses, read tiles | no key tool | **yes, 0 of 5** (no guess ever entered) | key and mouse methods banned | `browser_keys`, `browser_evaluate` |
| Drawing (local page) | CDP mouse drag | no drag | **yes, 0 of 5** (no shapes) | drag tools banned | `browser_pointer` drag with hit-testing |
| Excalidraw (real site) | CDP mouse drag | no drag | **not measured on the real site** | same cause as the local drawing page | new code passes 5 of 5 |
| Grade table | full table via JS | text extract capped at 8000 characters | **no, the old code passed 5 of 5** by paginating, in about 24 calls | cap is real, but the agent worked around it | `browser_read_table` with a completeness flag: 6 calls, 2.5x faster |
| Text browsing (shop) | works | works | not a regression | | no loss: 5 of 5 both; tool calls equal |

The earlier prediction that the table would fail was wrong for this fixture; the cost was speed, not success.

## 4. Tests and build

- Full suite on the working tree: **754 passed** (about 3.5 minutes), including new files for page I/O, the new tools through the real authorization path (real Chrome),
  the sequence engine's new steps, the multi-agent speed work and the hybrid tool profile. `npx vite build` succeeds.
- One test expectation was updated because planning packages now carry a `read_urls` field (my change, not a pre-existing failure).
- A bad text replacement briefly broke the worker prompt (every worker failed); fixed and covered by real-loop tests.
- The tiny test-harness change after that (`COMEX_LAB_VISIBLE`, benchmark harness only) was not covered by a full re-run at the time of writing; see section 6.

## 5. Security and reliability

- The new tools run through the existing authorization path: context claims, lease, canonical target, per-tab lock, deadline and cancellation.
  Tested: a context that omits an operation is refused for every new tool; a cancelled context sends nothing; Comex's own UI and browser-internal pages refuse input;
  mid-navigation input is refused as retryable.
- Page evaluation is read-only and enforced by the browser engine (`throwOnSideEffect`), with a time and output cap. Tested against clicks, value changes, `innerHTML`, `fetch`, cookies,
  navigation and timers; none changed the page. Elements fetched by literal id are rewritten to a form the engine accepts, and mutation is still refused.
- A coordinate click from a screenshot is refused if the viewport, navigation generation or scroll changed since the screenshot, or the point is outside the viewport.
- Pre-read pages and all page text are wrapped as untrusted data. No arbitrary code execution path was added.
- Isolation: benchmarks ran in their own Chrome and backend with a throwaway database. A second Electron window (separate profile) was used for earlier isolated stack runs.
  The user's app and backend were not driven. One earlier slip is recorded: a system screenshot tool once captured the user's screen; those files were deleted and the tool is no longer used.
- Nothing was pushed in this phase. The remote `public-comex-6` is public.

## 6. Open items and honest limits

- Wordle: 4 of 5, one failure from loop cost; returning the resulting screenshot and tab list from key and click actions is the most likely fix and is not built.
- Multi-agent still pays about 17 to 19 s of planning and synthesis. The remaining larger change is a non-blocking helper spawn (see `Trials/comet_orchestration_findings/03_what_to_adopt_in_comex.md`).
- Quality of the faster multi-agent answers (7 against 12 papers) was not judged.
- Not done: real-site Excalidraw on the old code, a one-time real Wordle attempt, a public benchmark subset, any CAPTCHA or search-fallback handling.
- The user's own running backend started before the last edits; it may not have every new tool until restarted.

## 7. Reproduce

```
.venv/bin/python benchmarks/hybrid_scenarios.py --label after --trials 5 --backend-dir . --timeout 180
git worktree add --detach <dir> 02edc0b && cp .env <dir>/.env
.venv/bin/python benchmarks/hybrid_scenarios.py --label before --trials 5 --backend-dir <dir> --timeout 180
COMEX_LAB_VISIBLE=1 .venv/bin/python benchmarks/hybrid_scenarios.py --label excalidraw_after_v2 --scenarios excalidraw --trials 5 --backend-dir .
.venv/bin/python benchmarks/isolated_stack.py start [--backend-dir <dir>] --log-dir <logs>
.venv/bin/python benchmarks/benchmark_research_paths.py --phase <label> --trials 5 --modes single,multi --backend http://127.0.0.1:8091 --cdp http://127.0.0.1:9333
.venv/bin/python -m pytest tests -q
```
