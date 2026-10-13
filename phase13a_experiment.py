import asyncio
import uuid
import json
import random
import string
import os

from agent_service import execute_agent_loop
import tempfile
import urllib.request

async def run_trial(use_graph: bool):
    print(f"\n{'='*50}\nRUNNING TRIAL: Graph Memory Enabled = {use_graph}\n{'='*50}")
    
    # 1. Generate randomized token
    token = "TKN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    print(f"[*] Generated unique experiment token: {token}")
    
    # 2. Start a fresh database for this trial (so conditions don't leak)
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "graph.db")
    os.environ["GRAPH_DB_PATH"] = db_path
    print(f"[*] Graph Database path: {db_path}")
    
    # We must patch the global graph_store in agent_service so execute_agent_loop picks it up
    import agent_service
    from graph.store import AgentGraphStore
    if use_graph:
        agent_service.graph_store = AgentGraphStore(db_path)
    else:
        agent_service.graph_store = None
    
    # Generate the deterministic web page URL
    html_content = f"<html><body>The secret experiment token is {token}.</body></html>"
    data_url = f"data:text/html,{urllib.parse.quote(html_content)}"
    
    # --- PHASE A: WRITE ---
    print(f"\n--- PHASE A: WRITE ---")
    write_task = f"Go to {data_url} and read the secret experiment token. You MUST explicitly save the token to memory using the save_artifact tool with title 'experiment_token'. When finished, output the token."
    
    res1, meta1 = await execute_agent_loop(
        task=write_task,
        default_cdp_url="ws://127.0.0.1:9222/devtools/browser/xyz",
        intent="VISIBLE_BROWSER_TASK",
        use_procedures=False,
        procedure_mode="none",
        use_graph=use_graph
    )
    print(f"[Phase A Result]: {res1}")
    print(f"[Phase A Tool Calls]: {meta1.get('tool_call_count')}")
    
    token_saved = False
    for trace in meta1.get("tool_traces", []):
        if trace["tool"] == "save_artifact":
            token_saved = True
            print(f"[Phase A Saved Artifact]: {trace['args']}")
    if not token_saved and use_graph:
        print("[WARNING] The agent did not use save_artifact! The token might not be stored!")
        
    # --- PHASE B: DESTROY CONTEXT ---
    # Because we are starting a completely new execute_agent_loop, conversation history is completely destroyed.
    # The only thing preserved is the db_path in AgentGraphStore.
    # To be extremely pedantic, we recreate AgentGraphStore to drop any in-memory caches.
    if use_graph:
        del agent_service.graph_store
        agent_service.graph_store = AgentGraphStore(db_path)
        
    # --- PHASE C: RECALL ---
    print(f"\n--- PHASE C: RECALL ---")
    recall_task = "What was the experiment token from my previous task? You MUST use search_memory to retrieve it. Do not use the browser to visit any data URL. Output the token precisely."
    
    res2, meta2 = await execute_agent_loop(
        task=recall_task,
        default_cdp_url="ws://127.0.0.1:9222/devtools/browser/xyz",
        intent="VISIBLE_BROWSER_TASK",
        use_procedures=False,
        procedure_mode="none",
        use_graph=use_graph
    )
    
    print(f"[Phase C Result]: {res2}")
    
    used_search = False
    used_browser = False
    search_records = []
    for trace in meta2.get("tool_traces", []):
        if trace["tool"] == "search_memory":
            used_search = True
            search_records.append(trace["args"])
        if trace["tool"] == "run_browser_harness":
            used_browser = True
            
    print(f"[Phase C Search Used?]: {used_search}")
    print(f"[Phase C Browser Used?]: {used_browser}")
    if used_search:
        print(f"[Phase C Search Queries]: {search_records}")
        
    match = token in res2
    print(f"[*] FINAL RECALL MATCH: {match}")
    
    return {
        "condition": "ENABLED" if use_graph else "DISABLED",
        "token": token,
        "write_result": res1,
        "recall_result": res2,
        "used_search": used_search,
        "used_browser": used_browser,
        "match": match
    }

async def main():
    results = []
    results.append(await run_trial(use_graph=False))
    results.append(await run_trial(use_graph=True))
    
    print("\n\n" + "="*50)
    print("PHASE 13A FINAL RESULTS")
    print("="*50)
    for r in results:
        print(f"Condition: {r['condition']}")
        print(f"Token: {r['token']}")
        print(f"Used Search: {r['used_search']}")
        print(f"Match: {r['match']}")
        print(f"Write Trace Snippet: {r['write_result'][:50]}...")
        print(f"Recall Trace Snippet: {r['recall_result'][:50]}...")
        print("-" * 50)
    
    with open("phase13a_report.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
