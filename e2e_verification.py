import os
import shutil
import asyncio
from unittest import mock
import json

import agent_service
from graph.store import AgentGraphStore

async def verify_e2e():
    print("=== Phase 8 E2E Verification ===")
    
    # 1. Fresh DB
    db_path = os.path.expanduser("~/.comex/graph.db")
    shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    agent_service.graph_store = AgentGraphStore(db_path)
    store = agent_service.graph_store
    
    # 3. Mock the browser to return the 6 questions
    mock_browser_output = """
Found the test page. Extracting questions...
Question 1: What is 2+2?
Question 2: Who am I?
Question 3: Where is the moon?
Question 4: Is water wet?
Question 5: Why is sky blue?
Question 6: What is AI?
===COMEX_EXTRACT===
{
  "url": "http://test.local/questions",
  "title": "Test Questions",
  "entities": []
}
===END_EXTRACT===
    """
    
    # We will patch the LLM to output a ToolCall instead of running the real LLM, 
    # OR we can just use the real LLM. 
    # The requirement is: "Task A must use the NORMAL Comex execution path".
    # We'll use the real LLM but mock the actual browser tool invocation via subprocess.run
    mock_run = mock.MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = mock_browser_output
    mock_run.stderr = ""
    
    print("\n--- Running Task A (Normal Execution) ---")
    with mock.patch("subprocess.run", return_value=mock_run):
        res_a = await agent_service.execute_agent_loop(
            "Navigate to the test page, find the 6 questions, and summarize them.", 
            "http://localhost:9222"
        )
    print("Task A completed.")
    print(f"Task A result excerpt: {res_a[:100]}...")
    
    # 5. Confirm texts exist in historical record
    print("\n--- Verifying persistence ---")
    res = store.conn.execute("MATCH (tc:ToolCall) RETURN tc.result_summary")
    found_questions = False
    while res.has_next():
        summary = res.get_next()[0]
        if "What is 2+2?" in summary:
            found_questions = True
            break
    
    if found_questions:
        print("Success: The six questions are present in the ToolCall history.")
    else:
        print("Defect: Questions not found in ToolCall history!")
        
    
    # 7. Start Task B as a completely independent new agent execution
    print("\n--- Running Task B (Recall) ---")
    # Wrap search_memory to spy on it and run_browser to ensure it's not called
    search_mem_spy = []
    
    original_search_memory = store.search_memory
    def spy_search_memory(query, domain="ALL", limit=10):
        search_mem_spy.append({"query": query, "domain": domain})
        return original_search_memory(query, domain, limit)
        
    store.search_memory = spy_search_memory
    
    mock_run_b = mock.MagicMock()
    mock_run_b.returncode = 1
    mock_run_b.stdout = "Browser tool should not be called in Task B"
    mock_run_b.stderr = ""
    
    with mock.patch("subprocess.run", return_value=mock_run_b):
        res_b = await agent_service.execute_agent_loop(
            "What were the exact six questions from the previous test? Do not browse the web. Use only persistent memory.", 
            "http://localhost:9222"
        )
        
    print("\nTask B Result:")
    print(res_b)
    
    # 8. Verify in trace
    print("\n--- Task B Trace Verification ---")
    print(f"search_memory calls: {search_mem_spy}")
    if len(search_mem_spy) > 0:
        print("Success: search_memory was called.")
    else:
        print("Defect: search_memory was not called.")
        
    # Check questions in output
    all_qs = ["2+2", "Who am I", "moon", "water wet", "sky blue", "AI"]
    if all(q in res_b for q in all_qs):
        print("Success: All six questions were recalled successfully.")
    else:
        print("Defect: Not all questions were recalled.")
        
    # 9. Ask natural-language recall variation
    print("\n--- Running Task B.2 (Natural Language Variation) ---")
    search_mem_spy.clear()
    with mock.patch("subprocess.run", return_value=mock_run_b):
        res_b2 = await agent_service.execute_agent_loop(
            "Can you list the six questions from the programming test I worked on earlier, in order?", 
            "http://localhost:9222"
        )
    print("Task B.2 search_memory calls:", search_mem_spy)
    if all(q in res_b2 for q in all_qs):
        print("Success: All six questions recalled via natural language query.")
    else:
        print("Defect: Natural language recall failed.")
        
    # 10. Verify provenance
    print("\n--- Verifying Provenance ---")
    if search_mem_spy:
        # Search for the same query to check provenance
        q = search_mem_spy[-1]["query"]
        d = search_mem_spy[-1]["domain"]
        prov_results = original_search_memory(q, d)
        if prov_results and prov_results[0]["provenance"]:
            prov_id = prov_results[0]["provenance"]
            print(f"Success: Provenance ID found: {prov_id}")
            
            # Check if prov_id is a ToolCall or Agent
            res = store.conn.execute("MATCH (n {id: $id}) RETURN label(n)", {"id": prov_id})
            if res.has_next():
                print(f"Provenance node type: {res.get_next()[0]}")
        else:
            print("Defect: Provenance not established.")
            
    # 11. Verify Negative Control
    print("\n--- Running Task C (Negative Control) ---")
    with mock.patch("subprocess.run", return_value=mock_run_b):
        res_c = await agent_service.execute_agent_loop(
            "What were the questions from the fake nonexistent math test from 2010?", 
            "http://localhost:9222"
        )
    print("Task C Result:", res_c)
    if "2+2" not in res_c and "AI" not in res_c:
        print("Success: Negative control passed.")
    else:
        print("Defect: LLM hallucinated the nonexistent test.")
        


if __name__ == "__main__":
    asyncio.run(verify_e2e())
