# Execution routing (Phase 1)

Branch `feature/python-program-mode`. Nothing here is committed or pushed.

> **Status update (after live use): PARKED. `--jevmode` was removed from the application.**
> The router was run in advisory mode on 12 real chat turns. All 12 were decided by the deterministic rules (Jev was never called) and all 12 were `typed` with 0.90 confidence, including follow-up messages such as "yes please. solve all questions", "continue... finish all questions" and "do it". The router sees only the latest message, with no conversation, and "all questions" carries no count, so it classed them as ordinary. That is the failure mode the evidence section below warns about: the 100% held-out figure came from tasks the same author wrote, and real follow-up turns were not represented in them.
> Nothing in the run changed, because the mode was advisory and the program tool is not connected. The router library, tests and evaluation are kept as written; the application no longer uses them. Sections below describe the design as built, not as adopted.

## 1. Architecture and policy

Perception and execution are separate decisions, made once per task, before the agent loop starts.

- **Perception**: what the task has to be looked at with. `semantic` (DOM, text, elements), `structured` (a complete table or record extraction), `visual` (screenshots). A task can need several. Semantic is always included (cheap).
- **Execution**: `typed` (the existing typed browser tools, the default) or `program` (a bounded Python-driven browser program that does many predictable operations in one call).

A large output is not a large execution: extracting 57 or 200 table rows is one `browser_read_table` call and stays `typed`. Needing to see a page (canvas, chess, chart) does not imply a program either.

Policy (`services/execution_router.py`), cheapest first. The common path makes no network call and takes about 0.02 ms.

1. Vague request, nothing concrete to classify: `typed`, flagged uncertain, the main model decides. Jev is not asked; it cannot know either.
2. Complete table extraction (a table word, an extraction verb, no entering/clicking verb): `typed`, override.
3. Strong many-operations signals (large counts, "each/every" with an operation, loop wording, detailed or multi-part drawings): `program`.
4. Clearly small or ordinary: `typed`.
5. Borderline: ask Jev's yes/no `many_ops` once, only if enabled. p ≥ 0.70 → `program`; p ≤ 0.35 → `typed`; in between → uncertain.
6. Jev disabled, unreachable, slow (1.5 s), invalid or unsure → `typed`, flagged uncertain, the reason recorded (`jev_not_enabled`, `jev_no_key`, `jev_timeout`, `jev_unreachable`, `jev_http_<code>`, `jev_invalid_response`, `jev_low_confidence`, `jev_circuit_open`), escalation hint `program_if_typed_stalls`.

Jev is never called after browser actions. A repeated task is cached; three consecutive failures pause calls for 60 s. The key is read from `TYPESAFE_API_KEY`, never logged, returned or stored (a test asserts this).

Privacy: when Jev is consulted, the task text and the page kind are sent to TypeSafe. That happens only with `--jevmode` and only for borderline tasks (2 of 68 in the held-out set).

Schemas: `RouteRequest(task, page_path)` and `RouteDecision(execution, perception, confidence, source, signals, uncertain, fallback, escalate, jev_called, jev_p, latency_ms)`.

## 2. What works in the application now

Start the backend with `.venv/bin/python agent_service.py --jevmode` (needs `TYPESAFE_API_KEY` in `.env` for the Jev step; without it the router still works and records `jev_no_key`).

- The router decides and reports a `route` event on the single-agent stream, and logs a one-line summary. It runs beside the agent (`asyncio.create_task`), never in front of it.
- It is **advisory only**. It does not change which tools the agent has, how it works, or any result. Helper workers are not routed. Without `--jevmode` nothing changes at all.
- A `program` decision is a recommendation. **The agent cannot execute a program.**

Not connected: the agent-facing program tool. What exists on this branch and works in isolation: `services/program_runtime.py` and `services/program_child.py` (a Python program in its own process that reaches the browser only through `ComexToolService`), the `page_script` and `cdp` service operations, and 15 tests in a real Chrome (permission per operation, call cap, timeout, cancellation, scrubbed environment, CDP allow-list).

### The blocker, precisely

Registering a tool in `_build_browser_tools` (`agent_service.py`) that lets the model write and run a program was refused by the permission checker in the session that built the runtime. No reason was given. It was not retried or worked around. Supported next steps: apply that registration yourself against the contract below, or add a permission rule that allows a future session to make that edit. Everything else in this phase proceeded.

### Contract for the eventual tool

- It must call `ProgramRunner(service, context).run(code, timeout_s)` with the agent's own `ToolExecutionContext`, so tab authority, lease, per-operation permission (`program`, `page_script`, `pointer`, ...), deadline and cancellation stay enforced per call.
- Bounded: code size, wall-clock timeout (default 120 s, max 600 s, never beyond the task deadline), at most 3000 browser operations, capped output.
- Partial results: a refused operation raises `ComexError` inside the program (it may catch it); a timeout or cancel returns what already printed, the operation counts and the list of refused operations, and says that work already done on the page stays done.
- Postconditions: the tool result should come with a fresh screenshot and the model must check it; routing only recommends.
- Permission consequences, stated plainly: the browser side is brokered; the Python itself runs as the same user with normal file and network access. A kill switch is `COMEX_PROGRAMS=0`.

## 3. Evaluation

Two sets, kept apart.

- **Dev set**: the original 30-task probe (`benchmarks/router_probe.py`, `benchmarks/router/typesafe_probe.json`, preserved). The deterministic rules were developed against it: 29 of 30 correct with no network call; the last one is borderline and goes to Jev.
- **Held-out set**: `benchmarks/router_eval_set.py`, 68 tasks in 9 categories, written before any router code existed, SHA-256 `9afae832...`. Run once. Router file SHA-256 `44d0dd14...` for the first run. Results: `benchmarks/router/eval_v1_results.json`.

| Arm (68 held-out tasks) | Accuracy | Program recall | Program false positives | Ambiguous flagged | Jev calls | Decision latency |
|---|---|---|---|---|---|---|
| Always typed (today) | 76.5% | 0% | 0 | 0/8 | 0 | 0 |
| Deterministic only | 98.5% | 94% | 0 | 8/8 | 0 | median 0.02 ms |
| **Production** (deterministic, Jev on borderline) | **100%** | **100%** | **0** | **8/8** | **2** | median 0.04 ms; the 2 Jev calls took 1,138 ms and 484 ms |
| Jev on every task + table override | 95.6% | 100% | 3 | 0/8 | 68 | median 511 ms, total 35 s |

- **Perception**: visual and structured requests had precision 1.0 and recall 1.0 in both deterministic arms.
- **Fallback frequency**: 0 failures in the production arm. With Jev off, the 2 borderline tasks fall back to `typed` flagged uncertain.
- **What Jev contributed**: 2 decisions, both correct, both for tasks the rules alone could not settle (floor plan drawing p = 0.74 → program; "click each of the six tabs" p = 0.14 → typed). Jev on every task did worse than the combination: it called three research tasks "program" (p = 0.50, 0.65, 0.81). On the held-out set program tasks scored as low as 0.58 and 14 of 52 non-program tasks scored above 0.35, a weaker separation than on the dev probe. This is why Jev is only a tie-breaker.

### Expected effect of the mistakes (only what was measured)

| Mistake | Cost |
|---|---|
| Long drawing routed `typed` | measured: typed tools scored 1/9 on the rocket in both runs; the Original's script agent scored 9/9 |
| Simple game or drawing task routed `program` | measured: the script agent was about +12 to +16 s slower on chess and drawing |
| Bulk DOM task routed `typed` | not measured |
| Ordinary task routed `program` | not measured |

Always-typed makes 8 mistakes of the first kind (8 long drawings) and 8 of the unmeasured second kind. Production makes none on this set.

### Limits of this evidence (read these)

- **The same person wrote the rules and the held-out set.** The held-out accuracy is almost certainly optimistic; it exercises the author's own phrasing. The honest next test is real tasks. In advisory mode every real task now gets a logged decision: label a sample of those by hand and compare.
- **Only 2 tasks reached Jev.** Nothing here says how reliable Jev is on borderline cases beyond those 2 and the dev probe; its 0.74 on the floor plan is barely above the 0.70 line.
- **No end-to-end benefit has been measured.** The program tool is not connected, so "the routing would help" rests on the earlier rocket and chess runs, not on a routed run.
- **Ambiguity handling is rule-based** (short vague phrasing). Real vague requests will vary.
- Small sample, labelled preliminary.

## 4. Files

- `services/execution_router.py`: router, schemas, optional Jev client.
- `tests/test_execution_router.py` (23 tests), `tests/test_router_integration.py` (4): policy, perception independence, table override, uncertainty, every Jev failure mode, no key leak, circuit breaker, cache, hook gating.
- `benchmarks/router_eval_set.py`, `benchmarks/router_eval.py`, `benchmarks/router/eval_v1_results.json`: held-out evaluation.
- `agent_service.py`: `--jevmode`, `_advisory_route`, one gated line in the stream handler.
- Earlier on this branch: `services/program_runtime.py`, `services/program_child.py`, `nervous/page_io.py` (`evaluate_script`, `cdp_call`), `services/tool_service.py` (`page_script`, `cdp`), `nervous/action_policy.py` (`COMEX_LEASE_TTL_S`), `benchmarks/rocket*`.

## 5. Next steps

1. Run in advisory mode on real use; label a sample; re-measure. Any rule change after that is a new version, scored on new tasks.
2. Resolve the blocker above and connect the program tool through the contract in section 2.
3. Then, and only then, measure the routed system end to end: the rocket (target 4 of 5 trials at 8 of 9 or better, median under 180 s), the five browser scenarios (stay at 24 of 25 or better), routing overhead (under 2 s per task, currently well under 0.1 s without Jev).
