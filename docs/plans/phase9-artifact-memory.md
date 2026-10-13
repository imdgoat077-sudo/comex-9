# Phase 9: Artifact Memory

This document describes the design and implementation of Phase 9 (Artifact Memory).

## 1. Architectural Intent
Phase 9 introduces a proper durable Artifact memory layer. 

Artifacts are explicitly designed for durable unstructured content that should be retrievable later as a coherent document or result (e.g., compiled sets of questions, research summaries, generated reports, or durable task outputs).

**What Artifact memory is for:**
- Durable unstructured memory and reusable knowledge.
- Explicitly saved outputs from an agent execution that should outlive the individual run.

**What Artifact memory is NOT for:**
- Trace history (e.g., `ToolCall.result_summary` is trace memory). Old ToolCalls are not Artifacts.
- Automatic recording of every conversational turn or output.
- Automatic semantic or episodic mapping (No Insight nodes, no planner memory, no auto-context).

## 2. Artifact Schema
The Artifact schema was implemented as a minimal `NODE_TABLE` in Kuzu:
- `id`: Deterministic UUID-based ID (`art_<uuid>`).
- `artifact_type`: E.g., "report", "document", "questions".
- `title`: Short descriptive title.
- `content`: The FULL un-truncated content of the artifact.
- `created_at`: Timestamp of creation.
- `source_agent_id`: The ID of the Agent that created this artifact.

## 3. Provenance Model
Artifacts strictly retain provenance back to their originating Agent execution.
- We introduced a new relation: `CREATED_ARTIFACT(FROM Agent TO Artifact)`.
- When an artifact is saved, a link is explicitly created from the creating `Agent` to the `Artifact`.
- This ensures any returned artifact can answer the question: “Which execution produced this artifact?”

## 4. `save_artifact` Semantics
The backend API exposes a canonical `save_artifact` method in `AgentGraphStore`.
- Persists full content, creates a new `Artifact` node, and the `CREATED_ARTIFACT` edge from the source `Agent`.
- Catches and logs exceptions (failure isolation) to prevent Graph DB errors from crashing normal Agent execution.
- Used safely even when Graph DB is misconfigured or disabled.

## 5. `search_memory` Integration
Artifacts are integrated seamlessly into the existing `search_memory` system:
- A new `ARTIFACTS` domain is available for targeted retrieval.
- The `ALL` domain now searches `Entities` + `History (Agent & ToolCall)` + `Artifacts`.
- Uses deterministic BM25 `FTS` queries on `['title', 'content', 'artifact_type']`.
- **Full-content vs Excerpt Semantics:** While the database stores the **FULL** artifact content unconditionally, `search_memory` returns a *controlled excerpt* (truncated at 500 characters) to avoid flooding the LLM context. 
- The full content is always recoverable via the internal programmatic API `get_artifact(artifact_id)`.

## 6. Test Results
The integration was fully validated against strict requirements:
- **Phase 0-8 Regression:** ALL existing 64 tests pass. The schema upgrades strictly preserved `ToolCall` and `Entity` behavior.
- **Phase 9 Tests:** 3 new tests successfully run.
- **Distinction Test:** Verified that Artifact memory retrieval correctly functions on the full-text `Artifact` independently of any `ToolCall.result_summary`.
- **E2E Independent Agent Recall:** Simulated a normal execution that explicitly uses `save_artifact` (Task A). In a completely new execution, Task B successfully used `search_memory(..., "ARTIFACTS")` to read the exact questions produced by Task A without calling the browser.
- **Negative Control:** Validated that a search for a non-existent artifact ("Chemistry Test") returned empty results, and the LLM explicitly declared it unavailable (obeying the Negative Memory Grounding Rule).
- **Failure Isolation:** Proven that a mocked Database connection failure correctly returns an empty string without raising an exception to the Agent loop.

Phase 9 successfully implemented.
