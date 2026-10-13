import asyncio
import json
import os
import shutil
from unittest import mock

import agent_service
from graph.store import AgentGraphStore


async def verify():
    print("=== Episode Instrumentation Verification ===")
    
    # 1. Fresh DB
    db_path = os.path.expanduser("~/.comex/graph_ep.db")
    shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    agent_service.graph_store = AgentGraphStore(db_path)
    store = agent_service.graph_store
    
    # Mock browser output
    mock_browser_output = """
Found the test page. Extracting questions...
Question 1: What is 2+2?
===COMEX_EXTRACT===
{
  "url": "http://test.local/questions",
  "title": "Test Questions",
  "entities": []
}
===END_EXTRACT===
    """
    
    mock_run = mock.MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = mock_browser_output
    mock_run.stderr = ""
    
    print("\n--- Running Controlled Task ---")
    with mock.patch("subprocess.run", return_value=mock_run):
        res = await agent_service.execute_agent_loop(
            "Navigate to the test page, read it, and tell me Question 1.", 
            "http://localhost:9222"
        )
    print("Task completed.")
    print(f"Final LLM Result: {res}")
    
    # Query database to verify Episode exists and is linked properly
    with store._lock:
        print("\n--- Verifying Episode Record ---")
        
        # Check number of Episodes
        res_count = store.conn.execute("MATCH (e:Episode) RETURN count(e)")
        count = res_count.get_next()[0]
        print(f"Total Episodes created: {count}")
        assert count == 1, "Exactly one episode should be created."
        
        # Fetch the Episode and linked Agent
        query = "MATCH (e:Episode)-[:FOR]->(a:Agent) RETURN e.id, e.agent_id, a.id, e.outcome_status, e.self_reported, a.task"
        res_ep = store.conn.execute(query)
        
        assert res_ep.has_next(), "No Episode-[FOR]->Agent relationship found!"
        
        row = res_ep.get_next()
        ep_id = row[0]
        ep_agent_id = row[1]
        a_id = row[2]
        outcome = row[3]
        self_rep = row[4]
        task = row[5]
        
        print(f"Episode ID: {ep_id}")
        print(f"Episode's agent_id: {ep_agent_id}")
        print(f"Agent's id: {a_id}")
        print(f"Agent Task: {task}")
        print(f"Outcome Status: {outcome}")
        print(f"Self Reported:\n{self_rep}")
        
        assert ep_agent_id == a_id, "Episode agent_id does not match Agent id!"
        assert outcome == "completed", "Expected outcome_status to be 'completed'"
        assert self_rep == res, "self_reported does not match final LLM response!"
        
        print("\nSUCCESS: Episode successfully recorded and wired correctly!")

if __name__ == "__main__":
    asyncio.run(verify())
