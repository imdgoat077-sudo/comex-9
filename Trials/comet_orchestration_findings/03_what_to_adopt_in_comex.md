# What Comex can learn from this, ranked

Not implemented. No main code was changed. Each item says what Comex does today (checked against the current tree), the
expected effect, and how to prove it. Candidates that change the agent loop must be benchmarked on the same scenarios as
the hybrid series, with no code edits during a series.

Measured background (this repo, same model and machine): one model call costs 4 to 6 s; tool execution is milliseconds to
a few seconds; planning plus synthesis cost about 17 s in multi-agent runs; baseline code fails chess and Wordle (0 of 5 chess).

## A. Highest expected value

1. **Return the resulting state with every action (act + observe in one turn).**
   Comet: every browser tool returns a screenshot and the task's tab list. Comex: tool results are text; a screenshot needs a
   separate `browser_screenshot` call, which costs another 4 to 6 s model turn.
   Change: an `observe_after` option on `browser_sequence`, `browser_pointer`, `browser_keys` that attaches the screenshot (using the existing
   image sink) and a compact tab list. Prove: fewer LLM calls per game move on chess/draw scenarios.

2. **Non-blocking helper spawn instead of a fixed plan → wait → synthesize pipeline.**
   Comet: a spawn call returns at once; the parent keeps working; joining is on the server. Comex: the orchestrator always
   plans, waits for every worker, then runs a separate synthesis call. Change (larger): let the single-agent loop call a
   `spawn_helper` tool that starts a worker through the existing orchestrator machinery, and receive the finished helper
   findings as a later tool result, so the parent's final answer is the synthesis. Needs a hard cap on helpers, deadlines and
   an overlap guard, because Comet's design has no up-front partition. Prove: multi vs single ratio (currently about 1.6 to 2).

3. **Tab list in every result.** Cheap; prevents a class of "which tab am I on" errors once several tabs exist. Prove: no
   change in speed, fewer wrong-tab calls in multi-tab tasks.

## B. Medium value

4. **Click proof marker on pointer actions.** Draw a marker at the clicked point on the screenshot the model gets next. Comex's pointer
   result reports the hit element (text), but not an image. Do it in-page on the capture, like Comet, because PIL is not available in the test environment.
5. **Better page-settle signal.** Comex `wait_for idle` uses a quiet window; Comet counts only meaningful requests and uses
   accessibility-tree update events with per-site tweaks. Adopt only if a benchmark shows idle waits are too slow or too early; today
   they are not the bottleneck.
6. **Accessibility-tree read in screenshot coordinates with filter modes (interactive / all / viewport, subtree by ref, depth).** Comex's `observe`
   and `inspect` cover much of this; the specific gain is coordinates already in screenshot space. Check what `inspect` returns before building.

## C. Already matched in Comex (no work)
Viewport-drift refusal of stale coordinates; partial results on batch failure; native-select hint and a dedicated select tool;
auto-answer of JavaScript dialogs; per-request timeouts; reattach-and-retry; hidden/background work tabs (Comex deliberately shows agent tabs, a product choice you made).

## D. Skip
Clipboard-paste typing fallback (direct insertion works in every fixture so far); random inter-action jitter (Comex waits on
page state, not time); Comet's special-casing of Gmail/Amazon (site-specific, brittle).

## Open questions that only Comet's servers can answer
When it chooses to spawn; how a helper's answer reaches the parent; whether it caps helpers. Observing Comet from outside
(same prompt, count tabs and time) is the only safe way to learn more.
