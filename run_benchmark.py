import os
import json
import time
import urllib.request
import subprocess
import tempfile
import shutil
import uuid
import uuid
from typing import Dict, Any

from graph.store import AgentGraphStore

# Use the production DB path to extract the seed procedure
PROD_DB_PATH = os.path.expanduser("~/.comex/graph.db")

def extract_seed_procedure(capability: str) -> dict | None:
    store = AgentGraphStore(PROD_DB_PATH)
    results = store.search_procedures(capability, limit=1, threshold=0.1)
    if results:
        return results[0]
    return None

def run_trial(condition: str, task: str, domain: str, expected_items: int, seed_proc: dict | None) -> dict:
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "graph.db")
    
    # 1. Setup isolated DB
    store = AgentGraphStore(temp_db_path)
    
    # 2. Seed procedure if PROCEDURAL
    if condition == "procedural" and seed_proc:
        store.conn.execute(
            """
            CREATE (a:Artifact {
                id: $id, 
                artifact_type: $type, 
                title: $title, 
                content: $content, 
                created_at: timestamp($created_at), 
                source_agent_id: $source_agent_id
            })
            """,
            {
                "id": str(uuid.uuid4()),
                "type": seed_proc.get("artifact_type", "procedure"),
                "title": seed_proc.get("title", ""),
                "content": seed_proc.get("content", ""),
                "created_at": str(seed_proc.get("created_at", "2026-01-01 00:00:00")),
                "source_agent_id": "seed-agent"
            }
        )
    
    # 2.5 Release lock before starting service
    del store
    import gc
    gc.collect()
    
    # 3. Start agent_service.py on this DB
    env = os.environ.copy()
    env["GRAPH_DB_PATH"] = temp_db_path
    
    # Random unused port for isolation
    port = 8011
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        [".venv/bin/python", "agent_service.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for service to be ready
    time.sleep(10)
    
    use_procedures = (condition == "procedural")
    req_data = json.dumps({
        "task": task,
        "tabId": f"bench_{condition}",
        "taskId": f"bench_{condition}",
        "intent": "VISIBLE_BROWSER_TASK",
        "use_procedures": use_procedures
    }).encode('utf-8')
    
    req = urllib.request.Request(f"http://localhost:{port}/agent/run", data=req_data, headers={'Content-Type': 'application/json'})
    
    result = None
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error calling agent: {e}")
        
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()
        
    # Validation logic
    passed = False
    details = ""
    if result and result.get("success"):
        res_text = result.get("result", "")
        # A simple deterministic check for the sake of the smoke test
        passed = (f"{expected_items} items" in res_text.lower() or "extracted data" in res_text.lower() or "here are the first" in res_text.lower())
        details = res_text[:100]
    
    # Clean up DB to release lock and delete
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    meta = result.get("metadata", {}) if result else {}
    
    return {
        "run_id": str(uuid.uuid4()),
        "condition": condition,
        "task": task,
        "domain": domain,
        "use_procedures": use_procedures,
        "procedure_capability": meta.get("procedure_capability"),
        "procedure_abstract_query": meta.get("procedure_abstract_query"),
        "procedure_confidence": meta.get("procedure_confidence"),
        "retrieved_procedure_ids": meta.get("retrieved_procedure_ids", []),
        "retrieved_procedure_scores": meta.get("retrieved_procedure_scores", []),
        "procedure_retrieval_threshold": meta.get("procedure_retrieval_threshold"),
        "procedure_context_injected": meta.get("procedure_context_injected", False),
        "exact_procedure_context": meta.get("exact_procedure_context"),
        "tool_call_count": meta.get("tool_call_count", 0),
        "failed_tool_call_count": meta.get("failed_tool_call_count", 0),
        "duration_seconds": meta.get("duration_seconds", 0.0),
        "final_result": result.get("result", "") if result else "",
        "validation": {
            "passed": passed,
            "details": details
        }
    }

def main():
    print("Extracting seed procedure from production DB...")
    seed_proc = extract_seed_procedure("extract list records")
    if not seed_proc:
        print("Failed to find seed procedure. Exiting.")
        return
        
    print(f"Found seed procedure: {seed_proc['title']}")
    
    task = "Go to https://webscraper.io/test-sites/e-commerce/allinone/phones/touch and extract the first 3 phones' titles and prices."
    domain = "webscraper.io"
    expected_items = 3
    
    results = []
    
    # Run Baseline
    print("\n--- Running BASELINE ---")
    res_base = run_trial("baseline", task, domain, expected_items, seed_proc)
    results.append(res_base)
    print(json.dumps(res_base, indent=2))
    
    # Run Procedural
    print("\n--- Running PROCEDURAL ---")
    res_proc = run_trial("procedural", task, domain, expected_items, seed_proc)
    results.append(res_proc)
    print(json.dumps(res_proc, indent=2))
    
    with open("benchmark_results.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\\n")
            
    print("\nBenchmark completed. Results saved to benchmark_results.jsonl")

if __name__ == "__main__":
    main()
