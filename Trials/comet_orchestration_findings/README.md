# Comet multi-agent orchestration: what the client code shows

Scope: how Comet starts, runs, and finishes sub-agents, read from the installed Comet agent extension.
Method: read-only static analysis. No Comet setting, profile, extension or credential was changed. No Comet code is copied
here; only identifiers and short paraphrases. Nothing outside this folder was modified.

Target: `~/Library/Application Support/Comet/Default/Extensions/npclhjbddhklpbnacpjloidibaggcgon/0.0.231_0`
(`background.js`, 773,368 bytes). Directory SHA-256 `f3ecddf1db0f0574907dc3f90928fd140ab8a0d51cc36a33a2c4bbaf01839fe5`.
Tooling: REA 6.4.0 `analyze-javascript-application` (evidence id `ev_9154a124…`, raw graph in `raw/`), plus targeted reads of `background.js`.

Labels: **[observed]** read directly in the client code. **[inferred]** follows from the client code but depends on the
server. **[unknown]** cannot be settled from anything installed locally.

## Findings

### 1. A sub-agent is spawned by the model through an ordinary tool call, not by a separate planning stage
- [observed] `CreateSubagent` is one of the server-to-client RPC methods. The dispatcher treats it like any other tool call,
  with one difference: it is handled by the orchestration object itself and not by the browser-tool set.
  Arguments: `prompt`, `start_url`, `task_uuid`, `extra_headers`.
- [observed] When a task starts, the client sends `supported_features: ["computer_batch", "computer_ref", "create_subagent"]`.
  The server is told the client can spawn sub-agents; whether it does is the server's choice.
- [inferred] There is no up-front decomposition call. The main agent's own model decides mid-run to spawn helpers.
- [unknown] The rule for when it spawns (the spawn threshold) is not in the client.

### 2. A sub-agent is a complete, independent agent task
- [observed] `CreateSubagent` calls the same function that starts a normal task, with `is_subagent: true`, the parent's
  `entryId`, `senderTabId`, `senderWindowId` and `base_url`.
- [observed] Each task builds its own stack: its own WebSocket to `/agent`, abort controller, tab manager, overlay
  manager, RPC service and browser tools. Nothing is shared between parent and child except the browser profile.
- [observed] The child's `task_uuid` is supplied by the server inside the tool request, and a task id that is already
  running is ignored ("already exists"). Spawning is idempotent.
- [observed] Parent and children share one `entryId`, which is the conversation entry in the UI.

### 3. Spawning does not wait for the child. The client has no join, wait or result tool
- [observed] `CreateSubagent` returns immediately with an empty tab context, or an error string if the start failed.
- [observed] Searches of the client found no wait, join, get-result or aggregate method, and no client-side cap on
  how many sub-agents run. (Searched names listed below, so "none found" is bounded to those names.)
- [inferred] The parent can issue several spawn calls back to back, and results are joined on the server.
  This is the main structural difference from Comex, where the orchestrator waits for all workers and then runs a
  separate synthesis call.
- [unknown] How a child's final answer reaches the parent's model.

### 4. The client is a thin executor; the agent loop runs on the server
- [observed] The server sends `{method, request, task_uuid}`. The client answers with `rpc_response`. Only two methods get
  special handling: `ReportTaskComplete` (ends the task and passes its message to the UI) and `ReportTaskProgress`
  (ignored by the client). Everything else is dispatched as a browser tool call.
- [observed] A second protocol (a "CDP bridge") exists where the server sends raw CDP commands plus control messages
  (pause/resume style status for the overlay). The client forwards them and returns the result.
- [observed] Retry behaviour lives client-side: reattach the debugger on "not attached", reload the tab on a debugger
  timeout, then retry once.

### 5. Visibility, lifecycle and the user interface
- [observed] A sub-agent's tabs are hidden (not focused). When the sub-agent is destroyed, its tabs are closed. The
  initial tab is not closed for sub-agents. Tabs are grouped once a task has two or more.
- [observed] Task events go to the side panel keyed by `taskUuid` and `entryId`: `BROWSER_TASK_COMPLETE` (with a result
  message), `BROWSER_TASK_STOP`, `ACTION_STARTED`. A sub-agent's thread can be moved into the side panel
  (`MOVE_THREAD_TO_SIDECAR` carries an `is_subagent` flag). A `mission_control_status` state exists.
- [inferred] The "mission control" UI that public reports describe is built from these per-task events.

### 6. A correction to the earlier research
- Research file 14 cites `entropy_request_content` and `StreamMiddlewares` as the place the spawn decision is visible
  from the client. Neither string exists in this extension's `background.js`, and a scan of the installed extensions' top-level
  and `js/` scripts found only `background.js` containing any subagent feature string (4 hits, all `create_subagent` / `CreateSubagent`).
  Those names may live in the native `Comet Framework` binary or in deeper bundle directories I did not scan. Treat that evidence-level C claim as unverified until located.

## What this means for Comex (proposals only; no code changed)
| Comet client shows | Comex today | Candidate change (needs benchmarking first) |
|---|---|---|
| Spawn is a non-blocking tool call from the running agent | Fixed pipeline: plan, run workers, wait for all, synthesize (about 17 s of fixed model calls measured) | Let one agent spawn helpers mid-run and keep working. Comex already has helper briefs; a non-blocking spawn tool would be the new part |
| Sub-agent = full independent task, same code path | Workers use the same loop with a reduced tool profile | Already similar |
| Join happens server-side | Orchestrator joins in Python, then one synthesis call | Join in the parent's loop (parent receives helper results as tool results) removes the separate synthesis call |
| Idempotent spawn by task id | Not needed yet | Cheap safety if spawning becomes model-driven |
| Hidden tabs, closed on finish | Visible tabs by design (your requirement) | Keep ours; your visible-tab requirement is a deliberate difference |

Risks of the Comet-style design that this evidence does not settle: runaway spawning (no client cap found), harder
cost control, and no up-front partition to prevent overlapping work. Comex's planner exists partly to prevent overlap.

## Reproduce
```
cd <scratch dir>
npx -y rea-agents@6.4.0 analyze-javascript-application "<extension dir above>" --format json > raw/agent_extension_0.0.231_analysis.json
```
Names searched in `background.js`: CreateSubagent, is_subagent, subagent, task_uuid, entropy_request_content, StreamMiddlewares,
parent_task, spawn, delegat, join/wait/result variants, maxConcurrent, MAX_SUBAGENT, MAX_TASKS, task_limit.
Byte offsets I used are specific to version 0.0.231 and will move on update.
