import os
import kuzu
from graph.store import AgentGraphStore

db_path = os.path.expanduser("~/.comex/graph.db")

store = AgentGraphStore(db_path)

# 1. Ensure artifact is persisted
artifact_title = "Procedural Candidate: List Record Extraction"
artifact_type = "procedure"
artifact_content = """
Goal: Extract selected fields from repeated records on a webpage.
Preconditions: The target page contains repeated record-like elements.
Procedure:
1. Navigate to the target page.
2. Identify the repeating record container.
3. Identify the requested fields.
4. Extract the requested fields from each record.
5. Select the requested records.
6. Return structured results.
Provenance: Derived from successful live episodes (e.g. ep_add371609f244082, ep_6d7be30ce734454e). Status=provisional.
"""
# Save it just in case. agent_id can be dummy
store.save_artifact("agent_experiment", artifact_title, artifact_type, artifact_content)

queries = {
    "A": "Find the first 5 products on this webpage and return their names and prices.",
    "B": "Open a product listing and extract the top 3 items with title and price.",
    "C": "From a webpage containing repeated entries, return selected fields for the first N records.",
    "D": "Go to a webpage and list the first three product names and prices.",
    "E": "Open this webpage and tell me its title.",
    "F": "Search Google for the capital of France.",
    "G": "Open this page and summarize the article.",
    "H": "Navigate to a broken URL and diagnose the error."
}

with open("retrieval_matrix.txt", "w") as f:
    for name, q in queries.items():
        f.write(f"\n--- QUERY {name} ---\n{q}\n")
        results = store.search_memory(q, domain="ALL", limit=5)
        for i, res in enumerate(results):
            title = res.get("title", "")
            if res.get("memory_type") == "Artifact":
                display = f"Artifact: {title}"
            else:
                display = f"ToolCall: {res.get('source_id')}"
                
            is_target = ("Procedural Candidate" in title)
            f.write(f"[{i+1}] TARGET? {is_target} | {display} | {res.get('content_excerpt')[:60].replace(chr(10), ' ')}\n")

