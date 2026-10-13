import asyncio
from graph.store import AgentGraphStore

def test_issues():
    store = AgentGraphStore("test_issue_db")
    
    # ISSUE 1: Current agent isolation in explicit search
    store.create_agent("agent_123", "Find monitors", "UNKNOWN")
    store.record_tool_call("agent_123", "dummy_tool", '{"foo": "bar"}', "Found a great monitor", 1, True)
    
    # search_memory inside tools.py just calls store.search_memory directly without filtering
    results = store.search_memory("monitor", "ALL")
    found_current_agent = any(r.get("provenance") == "agent_123" for r in results)
    print(f"Issue 1: Can retrieve own provenance? {found_current_agent}")
    
    # ISSUE 2: Full Artifact Retrieval
    long_content = "A" * 1000
    art_id = store.save_artifact("agent_123", "Long Report", "report", long_content)
    
    results = store.search_memory("Report", "ARTIFACTS")
    for r in results:
        if r.get("source_id") == art_id:
            excerpt = r.get("content_excerpt")
            print(f"Issue 2: Excerpt length: {len(excerpt)} vs Full length: {len(long_content)}")
            
            # Can the LLM get the rest? No tool exists for get_artifact in tools.py
            print(f"Issue 2: LLM can reliably retrieve full? FALSE (no tool)")

test_issues()
