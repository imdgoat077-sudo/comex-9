# Phase 8 Execution Plan: Unified Historical Memory Retrieval

## 1. Goal & Architectural Scope
The goal of Phase 8 is to enable Comex to retrieve historical execution data (Agent tasks, ToolCall summaries, and Entity data) using a unified deterministic text search interface backed by Kuzu Full-Text Search (FTS). 

**Architectural Constraint 1: Trace vs. Artifact**
`ToolCall.result_summary` is TRACE HISTORY, representing the raw chronological execution of a task. It is *not* a canonical long-term document or question memory. Phase 8 makes existing history searchable; it is not creating a new canonical document-memory architecture. Phase 9 will later introduce Artifacts for deliberate preservation of important unstructured content.

**Architectural Constraint 2: Immutability of Trace**
The database must ALWAYS retain the original stored value of trace data. `ToolCall.result_summary` MUST NEVER be truncated or overwritten in persistent storage. Any truncation limit (e.g., 500 characters) applies ONLY to the retrieval/output representation returned to the LLM to protect the context window. Limits must be applied *after* retrieval and ranking.

**In Scope for Phase 8:**
- Deterministic text retrieval only.
- Justified Kuzu FTS indices on trace and entity data.
- Implementing `search_memory(query: str, domain: str)` in Python.
- Refactoring `query_graph_memory` into a compatibility wrapper.
- Updating the agent's system prompt.
- Unit, integration, regression, and live testing.

**Out of Scope (Do NOT implement in Phase 8):**
- Vector embeddings or semantic search.
- `Artifact` nodes or `Insight` nodes.
- `save_artifact` or `save_insight` tools.
- `UserPreference` nodes.
- Post-task reflection or automatic learning.
- Planner redesigns.

---

## 2. Schema Extension (Kuzu FTS)
We will extend the graph initialization to create FTS indices. 

**Target Indices & Justification:**
- `Agent_FTS`: Index on `Agent(task)`. Core for history retrieval ("What was my previous task?").
- `ToolCall_FTS`: Index on `ToolCall(name, arguments, result_summary)`. Core for history retrieval ("What actions did I take?" and "What text did I read during the task?").
- `Entity_FTS`: Index on `Entity(type, data)`. Useful for fuzzy-searching extracted products or facts.
- **DEFERRED:** `Page_FTS`. Do NOT make mandatory without first verifying that the `Page` table contains useful searchable text beyond URL/title metadata.

*Note: Phase 0–7 schema semantics, provenance, deduplication, and staleness must be strictly preserved. Existing node and relationship structures will not change.*

---

## 3. Retrieval API (`graph/store.py`)
Add a new method `search_memory` to `AgentGraphStore`.

```python
def search_memory(self, query: str, domain: str = "ALL", limit: int = 10) -> list[dict]:
```

**Semantics:**
- **Valid Domains:** 
  - `"ENTITIES"` (searches `Entity_FTS` only).
  - `"HISTORY"` (searches `Agent_FTS` + `ToolCall_FTS`).
  - `"ALL"` (searches `ENTITIES` + `HISTORY`). 
  *Note: `Page_FTS` is deferred and therefore not included in `ALL` during Phase 8.*
- **Hard Limits (Applied POST-Retrieval):**
  - Retrieval ranking (BM25 scoring) MUST happen *before* output truncation or limit application.
  - Maximum number of results: `limit` (default 10).
  - Maximum excerpt size: e.g., 500 chars per result text.
  - Persisted `ToolCall.result_summary` is NEVER modified in the database. Limits apply only to the output string.
  - Maximum total returned payload: Bound by the above two constraints to prevent context bloat.
- **Retrieval Result Contract:** Each dictionary returned MUST include:
  - `memory_type`: (e.g., 'Entity', 'Task', 'ToolAction')
  - `source_id`: UUID or canonical key of the source node.
  - `timestamp`: The creation/completion time.
  - `relevance_score`: BM25 score from Kuzu.
  - `content_excerpt`: The retrieved text (safely truncated).
  - `provenance`: Task/Agent association where available.

---

## 4. Tool Migration Contract (`graph/tools.py`)
Replace `make_query_graph_memory_tool` with `make_search_memory_tool`.

**Input Schema:**
```json
{
  "query": "string (the natural language query)",
  "domain": "enum: ['ALL', 'ENTITIES', 'HISTORY']"
}
```

**Migration Strategy:**
- Do NOT immediately delete `query_graph_memory`. 
- `query_graph_memory` should become a compatibility wrapper around `search_memory` (using `domain="ENTITIES"` and passing the entity type as the query). This prevents breaking existing downstream dependencies until a full regression pass completes.
- The system prompt will be updated to instruct the agent to use `search_memory` for both entity retrieval and historical recall.

---

## 5. Prompt Changes (`agent_service.py`)
**Add:** 
```text
=== GRAPH MEMORY RETRIEVAL ===
You have a `search_memory` tool to check your persistent, long-term memory. 
You can search across two domains:
- "ENTITIES": For structured data you extracted previously (e.g., products, prices).
- "HISTORY": For your past tasks, actions, and the raw text results of your previous tool calls.
- "ALL": To search everything.

Always use `search_memory` before browsing if you suspect you or the user have already encountered the requested information.
```

---

## 6. Acceptance Criteria & Tests

### Unit & Regression Tests (`tests/test_phase8_memory_retrieval.py`)
1. **FTS Index Creation:** Verify indices are successfully created.
2. **Domain Routing:** Verify `"ENTITIES"` domain returns only Entities, `"HISTORY"` returns Trace elements.
3. **Retrieval Truncation Limits:** Verify long strings are truncated *only* in the returned LLM payload, and the database retains the full string.
4. **Phase 3 Regression:** Strict regression tests proving that the original Phase 3 entity-memory usecase ("Which monitors did you find under 15,000?") still works perfectly, verifying both `search_memory` and the `query_graph_memory` compatibility wrapper.
5. **Preservation of Phase 0-7:** Verify entity retrieval, staleness, deduplication, provenance, concurrency, debug endpoints, and health checks are unbroken.

### Live Cross-Task Verification (The Six-Question Acid Test)
This test MUST prove ALL of the following:
a. Task A contains six distinct questions.
b. Those question texts are actually persisted somewhere searchable in the historical graph (e.g., in a `ToolCall`).
c. Task B explicitly forbids live browsing.
d. Task B calls `search_memory`.
e. `search_memory` retrieves the relevant historical ToolCall/Agent record.
e2. The returned `search_memory` results themselves contain enough historical question text to reconstruct all six questions.
f. The final answer contains all six questions.
g. The questions are in the correct order.
h. No new browser navigation/tool execution occurs during Task B.
h2. No hidden conversation context may be used to satisfy the test; it must rely entirely on retrieved memory.
i. Provenance identifies the historical task/tool-call source.
j. **Negative Control:** A nonexistent-history query results in "not found / insufficient memory" rather than hallucination.

---

## 7. Definition of Done (HARD STOP POINT)
Implement Phase 8 only, then:
1. Run all Phase 0–7 regression tests.
2. Run all Phase 8 unit tests.
3. Run the live cross-task acid test.
4. Inspect actual `search_memory` tool traces.
5. Inspect Kuzu records.
6. **STOP IMMEDIATELY.** Do NOT proceed to Phase 9.
