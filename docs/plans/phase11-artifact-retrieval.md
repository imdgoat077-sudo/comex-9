# Phase 11: Full Artifact Retrieval

Phase 11 introduces explicit, sequential retrieval of Artifact memory.

## Architectural Boundary

- `search_memory`: Discovery tool. Uses FTS to find records and returns **bounded excerpts** (~500 chars).
- `read_artifact`: Document reading tool. Retrieves the full content of an Artifact sequentially via **chunked reading**.

Artifacts are meant to store unstructured durable knowledge (reports, lists, code). To be useful, the LLM must be able to read the entire document, not just a keyword-focused snippet.

## 1. Tool Signature

The new tool is exposed to the LLM as:

```python
def read_artifact(artifact_id: str, chunk_index: int = 0) -> str:
    """Read the full content of an Artifact sequentially by chunk.
    Use this tool after finding an artifact_id (source_id) via search_memory
    to read its complete text without being bounded to a short excerpt.
    """
```

It takes an `artifact_id` (obtained as the `source_id` from a `search_memory(domain="ARTIFACTS")` call) and a zero-indexed `chunk_index`.

## 2. Bind Tools Registration

The tool is dynamically instantiated via `make_read_artifact_tool(graph_store, agent_id, step_ref, chunk_size)` and explicitly appended to the `tools` list passed to `llm.bind_tools(tools)`. The LLM's schema natively exposes both `artifact_id` and `chunk_index`.

## 3. Chunking Configuration

Reading large documents directly into the LLM context can overflow token limits. Therefore, `read_artifact` slices the document at runtime.

- **Size**: Configured via `graph_memory.artifact_chunk_size` in `config.json` (defaults to 4000 characters).
- **Implementation**: Pure Python string slicing (`content[start:end]`). No chunk nodes or physical splitting occurs in the Kuzu database.
- **Result**: Responses include `total_chunks`, `char_range`, and `has_more` metadata to help the LLM navigate.

## 4. Provenance

Every call to `read_artifact` is recorded as a `ToolCall` node in the graph, linked to the executing `Agent` via an `EXECUTED` edge. The chunk index and character count are stored in the `result_summary`.

## 5. Security Boundary (Untrusted Data)

Because artifacts can contain arbitrary web scrapes or user input, raw content must not execute as LLM instructions. All returned text is wrapped in structurally enforced delimiter tags:
```
[UNTRUSTED DATA START]
<chunk_content>
[UNTRUSTED DATA END]
```

## 6. Current-Agent Policy

`read_artifact` is an **explicit tool**. Unlike Phase 10's automatic context (which filters out the current agent's own data to reduce noise), explicit tool calls *are* allowed to retrieve artifacts created by the current agent. This is intentional: a long-running agent may need to re-read a document it generated 50 steps ago.

## 7. Graph-Disabled Behavior

If `graph_store` fails to initialize or is disabled (`graph_memory.enabled == false`), `read_artifact` follows the repository's standard pattern: the tool is entirely omitted from the `bind_tools()` list, making it invisible to the LLM.

## 8. Known Cumulative-Context Limitation

While `read_artifact` allows reading a 20,000-character document over 5 turns (at 4,000 chars per chunk), the current `agent_service.py` execution loop simply appends all LLM messages to the `messages` array. Therefore, reading a large artifact chunk-by-chunk still consumes cumulative tokens linearly. There is no automated prompt-truncation or token-budget eviction implemented yet.
