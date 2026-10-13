# Rocket runs: notes on how to read them

All runs: same prompt and same nine-part scorer (`benchmarks/rocket_rubric.py`), one hidden Chrome per run, one trial each. Single trials, so evidence, not a statistical result.

| Run | Approach | Time | Model calls | Score v2 | Note |
|---|---|---|---|---|---|
| explore_typed_300 | typed tools, 5 min lease | 306 s | 60 | 1/9 | lease expired. About 5 s per model call (normal) |
| explore_typed_900 | typed tools, 15 min lease | 569 s | 101 | 1/9 | stopped by the 100-step cap. About 5.6 s per model call (normal) |
| original_python | Original, Python scripts | 474 s | 29 | 9/9 | **time is unreliable**: the user's internet went off during this run (about 16 s per call against about 8 s in run 2, and one 61 s gap). The drawing itself is valid |
| original_python_run2 | Original, Python scripts | 109 s | 14 | 9/9 (7/9 under scorer v1) | scorer v1 had two false negatives; see `rocket_rubric.py` and `rescore_rockets.py` |

Not run: the hybrid mode. Its runtime exists on the branch but is not connected to the agent.
