# Single-agent vs multi-agent research: before and after the decomposition fix

Request (identical in all 20 trials): *"Find me the best research papers on multi agent orchestration."*
Run 2026-10-11, 23:31–23:55 IST, same machine, same Comex window, same model proxy (`ag/gemini-3.8-flash`).
5 trials per mode per phase, alternating single/multi order. **Before** = backend at commit `005efd0`
(run from a separate worktree); **after** = fixed backend. Single-agent code is identical in both phases.
Raw data: `benchmarks/research_paths/{before,after}/` (per-trial JSON with full event timeline, raw answer
`*_answer.md`, link checks) and `summary.json`. Harness: `benchmarks/benchmark_research_paths.py`.

## Root cause (from the user's original runs and the baseline trials)

1. **Website-based, overlapping decomposition with seeded item lists.** Baseline packages read "Search arXiv
   and Google Scholar for …" for both agents, and some named papers ("frameworks such as AutoGen, MetaGPT").
   One agent then looked papers up one by one: in the user's run, 20 tool calls / 115 s vs 4 calls / 34 s for
   its sibling, which then idled 82 s.
2. **No enforced limits.** The slow agent kept browsing for 4 steps after its 90 s deadline expired.
3. **No timing instrumentation** for planning, synthesis or per-agent LLM calls.

Workers did run concurrently (interleaved logs, simultaneous starts); scheduling was not the problem.

## Results

| Metric (median, range) | Single before | Single after | Multi before | Multi after |
|---|---|---|---|---|
| End-to-end time | 34.7 s (28.4–40.2) | 25.2 s (23.9–44.1) | **110.3 s (72.0–150.4)** | **97.2 s (71.3–100.6)** |
| Agents | 1 | 1 | 2 | 3 |
| Planning | – | – | 8.8 s | 10.4 s |
| Slowest agent | – | – | 94.1 s (53.8–128.9) | 74.7 s (51.9–78.3) |
| Comparison step (after last agent) | – | – | 11.0 s | 10.2 s |
| Tool calls (all agents) | 4 | 4 | 19 | 23 |
| LLM calls | 5 (5–6) | 5 (4–7) | ≈23, derived* | 27 measured (23–33) + planning + synthesis |
| Papers with links in final answer | 6 (5–9) | 6 (5–7) | 8 (7–10) | **11 (9–12)** |
| Paper links that resolve (HTTP 200) | 34/34 | 30/31 | 41/42 | 53/54 |
| Papers reported by 2+ agents | – | – | 0 | 0 |

\* Baseline multi-agent runs did not record LLM calls (root cause 3); derived as tool calls + one final turn per
agent + planning + synthesis.

**Single agent:** same code in both phases, so its 34.7 s → 25.2 s difference is run-to-run variance in the
model proxy, not an improvement. Pooled over all 10 runs: median 31.8 s, 6 papers.

## What changed in the multi-agent runs

- **Worst case is bounded.** Max time fell from 150.4 s to 100.6 s, and the slowest agent from 128.9 s to at
  most 78.3 s. 8 of 15 agent runs reached the 10-action limit and still returned 2–5 papers each.
- **Distinct responsibilities.** Every run after the fix split into surveys / foundational frameworks /
  benchmarks and evaluation, with no named papers to look up. Agents still sometimes use the same site
  (arXiv) for different facets; no paper was reported by two agents in either phase.
- **Deeper, better-sourced answers.** Median papers rose from 8 to 11 (≈1.8× the single agent's 6). The
  after-fix answers give authors, year, venue and source-attributed citation counts for each paper (the
  fields each package asked for); baseline answers often gave rounded figures without a source.
- **Cost.** Median time improved 12% (110 → 97 s), not dramatically: the fix spends the saved time on a third
  agent. Planning got about 1.6 s slower because packages are more detailed.

## Verdict

Multi-agent is still about 3× slower than the single agent on this request (97 s vs ~32 s). It now delivers
clearly more research for that cost: about 1.8× the papers, organised by facet, with verifiable metadata and
working links, and without the runaway agent. Before the fix it was 3.5× slower for 1.3× the papers. For a
quick "best papers" lookup the single agent remains the faster choice; multi-agent is worth it when breadth
and per-paper detail matter.

Limits of this evaluation: one request, 5 trials per cell, one model proxy whose latency varies run to run.
Relevance and correctness were checked by reading answers and resolving links; individual facts (e.g.
citation counts) were not each verified against their sources.
