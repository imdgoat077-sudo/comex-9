# Multi-agent orchestration: review and proposal

Status: proposal, nothing implemented. Written 2026-10-13 against branch `feature/browser-tab-manager`.

## 1. What runs today

Comex has two ways to use several agents, chosen by the Single / Multi switch in the chat.

### Multi mode: a fixed pipeline (`services/orchestrator.py`, `/agent/orchestrate/stream`)

Every request goes through the same five stages, whatever it is:

```
user request
   │
   ▼
1. PLAN      one model call (decompose_request_via_llm): split into 1–4 packages, guess 1–3 read_urls each   ~9–10 s
   │
   ▼
2. FAN OUT   one worker per package, each a full agent loop in its own tab
             brief from a fixed template (build_worker_brief), 10 browser actions, 90 s deadline,
             pages pre-read before its first model call (prefetch)
   │
   ▼
3. BARRIER   wait for every worker; the last one gets a grace period, then is told to wrap up      slowest worker
   │
   ▼
4. SYNTHESIS one model call that merges the reports (text only, no browser)                         ~10 s
   │
   ▼
5. FOLLOW-UP optional: ask approval, then start a NEW agent in a NEW tab to act on the winner
```

Yes, it is template-like. The shape is fixed before any page has been seen:

- **The plan is a blind guess.** The planner chooses the facets and the pages to read before anything is known. If worker A
  finds that the answer is all on one site, worker B keeps going anyway. Nobody re-plans.
- **Fixed overhead of about 20 s** (plan plus synthesis), on top of the slowest worker. Measured on "best papers on
  multi-agent orchestration": multi 97 s against 32 s for the single agent, for about 1.8× the papers
  (`benchmarks/research_paths_report.md`).
- **A barrier.** Nothing moves until the slowest worker is done. The straggler policy is a patch for this.
- **The coordinator is blind.** Synthesis is a text merge. It cannot open a page to settle a contradiction, fill a gap or
  retry a failed worker. It can only write "missing".
- **Workers are isolated.** They cannot see what their siblings have already found. Overlap is prevented only by the
  planner's wording.
- **Actions start over.** The follow-up agent gets a text summary and a fresh tab, and re-finds the item.
- **The user picks the mode, not the task.** A simple question in Multi mode still pays for the plan.

### Single mode with helper agents (`HelperAgentManager`, `agent_service.py`)

Single mode already has the design you like: the agent can call `start_agent`, `wait_for_agents`, `message_agent`,
`list_agents` and `stop_agent`. Each helper runs as a one-task orchestration run, so it gets the same tab, lease,
cancellation and tab-group handling. Helpers cannot start helpers, and at most 4 run at once. This is the right
foundation, but it has fallen behind the Multi path:

| Gap | Where |
|---|---|
| `wait_for_agents` blocks the main agent until all (or a timeout); it cannot react to the first helper that finishes while it keeps working | `HelperAgentManager.wait` |
| Helpers start cold: no prefetched pages, so they spend 2–3 model turns (about 6 s each) just reaching the pages | `start()` passes no `read_urls` |
| Thin brief: no conversation context, no list of what sibling helpers own, no structured reply format | `build_helper_brief` |
| Helpers always get the research tool set (no keys, pointer or programs), so they cannot act or draw | `profile="research"` for any worker |
| No approval step, so the single agent cannot ask "add this one to the cart?" mid-task | approval exists only in Multi |
| Never measured. In the 10 single-agent research benchmark runs the agent started 0 helpers | `benchmarks/research_paths/after/*_single.json` |

## 2. My opinion

Drop the pipeline and make the single agent the orchestrator: **one lead agent that does the work itself and calls in
helpers when breadth pays off**. This is how Claude Code's subagents work, and what Comet's client code shows
(`CreateSubagent` is fire-and-forget; the parent keeps working; see `Trials/comet_orchestration_findings`).

Why this is faster and works better:

1. **No planning call and no synthesis call.** The lead's first turn is the plan (it spawns helpers as tool calls). Its
   final answer is the synthesis. That saves about 20 s on every multi-agent request.
2. **The lead plans after looking.** It can open one search page first, see the shape of the results, then split the work
   along real lines (one helper per shop it actually found, not per guessed facet).
3. **No idle time and no barrier.** While helpers browse, the lead works too. It reads each result as it arrives, stops
   helpers once it has enough, and redirects a helper that drifts (`message_agent` already exists).
4. **The coordinator can check.** When two helpers disagree, the lead opens the page itself instead of writing "conflict".
5. **Simple tasks cost nothing extra.** With no spawns, it is exactly today's single agent (25–32 s on the papers task).
6. **Actions continue in place.** The lead already has the winner's page from a helper's tab (browser_switch_tab
   exists), so there is no re-search from a cold tab.

Risk, said plainly: everything rests on the lead deciding well when to spawn. Today's model spawned 0 times in 10
research runs. Clear spawn rules in the prompt, the Multi switch kept as a "use helpers" hint, and a benchmark gate
before anything old is deleted all address this.

## 3. Architecture

```
                         ┌──────────────────────────── LEAD AGENT (the user's chat, its own tab) ─────────────────────────┐
user ── message ───────▶ │ agent loop (execute_agent_loop), full tool set                                                 │
                         │  • does small parts itself                                                                     │
                         │  • start_agent(task, read_urls, collect, kind, budget) ── returns at once                      │
                         │  • keeps browsing; each finished helper's report arrives in its next turn ◀──────────┐         │
                         │  • wait_for_agents(any|all) only when there is nothing else to do                    │         │
                         │  • ask_user(question) for approval before an action the user did not spell out       │         │
                         │  • final answer = the synthesis                                                      │         │
                         └───────────────┬──────────────────────────────────────────────────────────────────────┼─────────┘
                                         │ spawn (max 4 running, depth 1)                                        │ report (structured,
                         ┌───────────────▼────────────┐ ┌────────────────────────────┐                          │ untrusted data)
                         │ helper-1 (own tab, lease)  │ │ helper-2 (own tab, lease)  │  ...  ───────────────────┘
                         │ pages pre-read before its  │ │ kind=action: action budget │
                         │ first model call           │ │ and stop points            │
                         │ brief: goal, chat context, │ │                            │
                         │ what siblings own, format  │ │                            │
                         └────────────────────────────┘ └────────────────────────────┘
          unchanged underneath: OrchestrationRun per helper, ServerTabLeaseRegistry, tab groups, cancel on tab/group close
```

### Pieces, each reusing what exists

1. **Helper parity with Multi workers.** `start_agent(task, url?, read_urls?, collect?, kind="research"|"action")`.
   - One brief builder: merge `build_helper_brief` into `build_worker_brief`, so helpers get the conversation context,
     the sibling list, `GROUNDING_RULE` and `WORKER_REPLY_FORMAT`.
   - `read_urls` go through `_clean_read_urls` into the task's package, so `_prefetch_pages` reads them before the
     helper's first model call (the biggest measured win from the Multi work).
   - `kind="action"` uses `action_task`'s budget, `ACTION_RULES` and the full tool profile.
2. **Event-driven join.** When a helper finishes, its report (capped, in untrusted-data delimiters) goes into the lead's
   next turn through the same inbox the loop already drains (`inbox.get_nowait()`).
   - `wait_for_agents` gains `mode="any"`.
   - When the lead has nothing else to do it waits on the helpers instead of spending model calls polling.
   - This replaces the straggler policy: the lead decides when it has enough and calls `stop_agent`.
3. **`ask_user` for approval.** It reuses `_await_user_approval`, the `approval_required` event and
   `/agent/orchestrate/approve`, which the chat already renders.
4. **Spawn rules in `DELEGATION_PROMPT`.**
   - Spawn when there are 2 or more independent parts and each needs 2 or more pages. Otherwise work alone.
   - Give each helper `read_urls` (search URLs with the query in them).
   - Never give two helpers the same page.
   - When the switch is on Multi, add "prefer helpers for breadth".
5. **One endpoint.** Both switch positions go to `/agent/run/stream`. Once the benchmark shows the lead is at least as
   good, delete the pipeline's own code: `decompose_request_via_llm`, `synthesize_final_answer`, `_run_follow_up`, the
   straggler policy, and the `/agent/orchestrate*` routes apart from `/approve`. The run, lease, tab and cancellation
   machinery stays, because helpers already use it.

Kept as is: depth 1 (helpers never spawn), at most 4 running, a lease and visible tab per helper, closing a helper's tab
stops only that helper, closing the group stops everything, helper output is treated as data and never as instructions.

## 4. How we'll know it's better (gate before deleting anything)

Same model, same machine, isolated stack, 5 trials per arm, medians and ranges. Three arms: **single (today)**,
**multi pipeline (today)** and **lead + helpers**.

| Scenario | Why it is in the set |
|---|---|
| Best papers on multi-agent orchestration | the existing research benchmark (97 s multi / 32 s single today) |
| Compare one product across 3 shops | real breadth, where helpers should win |
| Compare, then add the best to the cart | research plus approval plus action continuity |
| Book or fill a form on one site (direct action) | must not spawn |
| One quick factual lookup | must not spawn and must cost no more than single |

Measured for each: wall time, model calls (lead plus helpers), helpers spawned, quality (items with working links, from
the existing link checks), failures and recoveries.

Pass condition:
- lead + helpers is no slower than single on the two no-spawn tasks;
- on the breadth tasks it is faster than the multi pipeline with at least the same quality;
- the spawn rate is right in both directions.

My estimate for the papers task, **not measured**: about 40–55 s against 97 s today. The saving comes from no planning
call, no synthesis call, the lead working in parallel, and early stop.

## 5. Order of work

1. Helper parity: brief merge, `read_urls` and prefetch, `kind`, tests.
2. Event-driven join, `wait_for_agents(mode="any")`, stop instead of straggler, tests.
3. `ask_user` approval for the lead.
4. Spawn rules, and the switch as a hint.
5. Benchmark the three arms and write the report.
6. Only if it passes, delete the pipeline code and route both switch positions to the lead.

Each step is its own commit, tested in an isolated live stack before it is called done.

Optional, only if the benchmark points to it:
- run helpers on a faster model than the lead (needs a per-call latency check on the router first);
- a shared findings list so helpers can see items a sibling already found (only if overlap shows up in the measurements).
