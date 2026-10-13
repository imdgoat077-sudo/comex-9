COMEX — FINAL PHASE 10 RETRIEVAL-BOUNDARY REVIEW REPORT
================================================

1. CURRENT-AGENT ISOLATION
   - verified behavior: Automatic memory context explicitly filters out results where `provenance == agent_id` to prevent the agent's new `Agent` node (with `status: running`) from polluting the initial prompt. The explicit `search_memory` tool does NOT apply this filter.
   - test evidence: `test_phase10_automatic_context.py::test_current_agent_isolation` explicitly tests auto-context isolation. There is no test enforcing isolation on explicit searches. Code inspection of `graph/tools.py` confirms `search_memory` has access to `agent_id` but does not filter by it.
   - decision: INTENTIONAL DESIGN. Auto-context runs before the agent takes any actions, so filtering `agent_id` correctly suppresses the noise of its own creation record. Conversely, if an agent runs a long 100-step task, it is entirely valid for it to explicitly search for and retrieve ToolCalls, Entities, or Artifacts it generated earlier in its own execution. Breaking this would introduce false negatives.

2. FULL ARTIFACT RETRIEVAL
   - verified behavior: A. "The backend can retrieve the full artifact." is TRUE (`graph_store.get_artifact(artifact_id)` returns full content). B. "The LLM can reliably retrieve the full artifact." is FALSE. `search_memory` truncates all results to a ~500 character query-focused excerpt. There is no `read_artifact` tool exposed to the LLM. 
   - test evidence: `test_phase8_memory_retrieval.py::test_truncation_limits` proves excerpts are bounded. Inspection of `agent_service.py` and `graph/tools.py` proves `make_save_artifact_tool` is bound to the LLM, but no corresponding full-read tool exists. Phase 9 docs explicitly state recovery is via "internal programmatic API".
   - decision: KNOWN LIMITATION. This is a clear limitation of the current tool schema, but it is not a Phase 10 correctness bug. It is a Future-Phase Concern (e.g., introducing a `read_artifact` tool).

3. CHANGES MADE
   - none

4. REGRESSION
   - exact final test count: 85/85 tests passed.

5. PHASE 10 STATUS
   - APPROVED
