import os
import json
import time
import urllib.request
import subprocess
import tempfile
import shutil
import uuid
import random

seed_procedures = [
    {
        "capability": "extract_list_items",
        "title": "Procedural Candidate: List Record Extraction",
        "content": "Goal: Extract selected fields from repeated records on a webpage.\nProcedure:\n1. Use document.querySelectorAll to identify the repeating record container.\n2. Iterate through nodes and extract the requested fields.\n3. Return structured JSON results.",
        "artifact_type": "procedure"
    },
    {
        "capability": "search_and_extract",
        "title": "Procedural Candidate: Search and Extract",
        "content": "Goal: Enter a query into a search bar, submit, and extract top result.\nProcedure:\n1. Locate search input field using CSS selectors (e.g., input[type='search'], input[name='search'], input[name='q']).\n2. Set value and dispatch 'input' and 'change' events.\n3. Click the submit button or form.\n4. Wait for results to load.\n5. Extract the first result.",
        "artifact_type": "procedure"
    },
    {
        "capability": "form_submission",
        "title": "Procedural Candidate: Form Submission",
        "content": "Goal: Fill out a form and submit it.\nProcedure:\n1. Locate input fields by name, id, or placeholder.\n2. Fill fields using js() and dispatchEvent(new Event('input', {bubbles: true})).\n3. Locate the submit button and click it.\n4. Extract the resulting success or error message on the next page or DOM update.",
        "artifact_type": "procedure"
    },
    {
        "capability": "click_detail_and_extract",
        "title": "Procedural Candidate: Click Detail and Extract",
        "content": "Goal: Click on a specific item in a list to view its detail page and extract info.\nProcedure:\n1. Find the link or button for the target item using its text content.\n2. Click it using js().\n3. Wait for the detail page to render.\n4. Extract the required data.",
        "artifact_type": "procedure"
    }
]

tasks = [
    {
        "id": "T13", "family": "form_submission", "domain": "the-internet.herokuapp.com",
        "task": "Go to https://the-internet.herokuapp.com/login, DO NOT submit the form, just extract the text of the subheader h2 element.",
        "expected": ["Login Page"]
    },

    {
        "id": "T1", "family": "extract_list_items", "domain": "the-internet.herokuapp.com",
        "task": "Go to https://the-internet.herokuapp.com/challenging_dom and extract the first 3 values in the 'Definiebas' column of the table. Format as a comma-separated list.",
        "expected": ["Definiebas0", "Definiebas1", "Definiebas2"]
    },
    {
        "id": "T2_v2", "family": "extract_list_items", "domain": "the-internet.herokuapp.com",
        "task": "Go to https://the-internet.herokuapp.com/tables, look at 'Table 1', and extract the first 3 Last Names in order. Format as a comma-separated list.",
        "expected": ["Smith", "Bach", "Doe"]
    },
    {
        "id": "T3", "family": "extract_list_items", "domain": "lambdatest.io",
        "task": "Go to https://ecommerce-playground.lambdatest.io/index.php?route=product/category&path=57 and extract the name of the first product in the list.",
        "expected": ["Samsung Galaxy Tab 10.1"]
    },
    {
        "id": "T4", "family": "search_and_extract", "domain": "octoperf.com",
        "task": "Go to https://petstore.octoperf.com/actions/Catalog.action, search for 'Golden Retriever' using the search bar, and extract its Product ID.",
        "expected": ["K9-RT-01"]
    },
    {
        "id": "T5", "family": "search_and_extract", "domain": "lambdatest.io",
        "task": "Go to https://ecommerce-playground.lambdatest.io/, use the search bar to search for 'iMac', and extract the price of the product from the search results.",
        "expected": ["$122.00"]
    },
    {
        "id": "T6", "family": "search_and_extract", "domain": "automationexercise.com",
        "task": "Go to https://automationexercise.com/products, search for 'Blue Top', click search, and extract the price of the first product found.",
        "expected": ["Rs. 500"]
    },
    {
        "id": "T7", "family": "form_submission", "domain": "the-internet.herokuapp.com",
        "task": "Go to https://the-internet.herokuapp.com/login, login with username 'tomsmith' and password 'SuperSecretPassword!', and extract the flash banner success message.",
        "expected": ["You logged into a secure area"]
    },
    {
        "id": "T8", "family": "form_submission", "domain": "saucedemo.com",
        "task": "Go to https://www.saucedemo.com/, login with username 'standard_user' and password 'secret_sauce'. Extract the title of the first product on the dashboard.",
        "expected": ["Sauce Labs Backpack"]
    },
    {
        "id": "T9", "family": "form_submission", "domain": "uitestingplayground.com",
        "task": "Go to http://uitestingplayground.com/sampleapp, enter username 'testuser' and password 'pwd', click 'Log In', and extract the success message text.",
        "expected": ["Welcome, testuser!"]
    },
    {
        "id": "T10", "family": "click_detail_and_extract", "domain": "demoblaze.com",
        "task": "Go to https://www.demoblaze.com/, click on the 'Samsung galaxy s6' link to view its detail page, and extract its exact price.",
        "expected": ["$360"]
    },
    {
        "id": "T11", "family": "click_detail_and_extract", "domain": "saucedemo.com",
        "task": "Go to https://www.saucedemo.com/, login with 'standard_user' / 'secret_sauce', click on the 'Sauce Labs Fleece Jacket' link, and extract its price on the detail page.",
        "expected": ["$49.99"]
    },
    {
        "id": "T12", "family": "click_detail_and_extract", "domain": "octoperf.com",
        "task": "Go to https://petstore.octoperf.com/actions/Catalog.action?viewCategory=&categoryId=CATS, click on the Product ID for 'Persian', and extract the Item ID of the adult female persian on the detail page.",
        "expected": ["EST-16"]
    }
]

def run_trial(condition: str, task_def: dict) -> dict:
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "graph.db")
    
    from graph.store import AgentGraphStore
    store = AgentGraphStore(temp_db_path)
    
    if condition != "baseline":
        for proc in seed_procedures:
            store.conn.execute(
                """
                CREATE (a:Artifact {
                    id: $id, 
                    artifact_type: $type, 
                    title: $title, 
                    content: $content, 
                    created_at: timestamp('2026-01-01 00:00:00'), 
                    source_agent_id: $source_agent_id
                })
                """,
                {
                    "id": str(uuid.uuid4()),
                    "type": proc["artifact_type"],
                    "title": proc["title"],
                    "content": proc["content"],
                    "source_agent_id": "seed-agent"
                }
            )
            
    del store
    import gc
    gc.collect()
    
    env = os.environ.copy()
    env["GRAPH_DB_PATH"] = temp_db_path
    
    port = random.randint(8100, 8900)
    env["PORT"] = str(port)
    
    proc = subprocess.Popen(
        [".venv/bin/python", "agent_service.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(8)
    
    use_procedures = (condition != "baseline")
    procedure_mode = "none" if condition == "baseline" else ("gated" if condition == "gated_procedural" else "blind")
    req_data = json.dumps({
        "task": task_def["task"],
        "tabId": f"bench_{condition}_{task_def['id']}",
        "taskId": f"bench_{condition}_{task_def['id']}",
        "intent": "VISIBLE_BROWSER_TASK",
        "use_procedures": use_procedures,
        "procedure_mode": procedure_mode
    }).encode('utf-8')
    
    req = urllib.request.Request(f"http://127.0.0.1:{port}/agent/run", data=req_data, headers={'Content-Type': 'application/json'})
    
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
        
    passed = False
    details = ""
    res_text = ""
    if result and result.get("success"):
        res_text = result.get("result", "")
        # Deterministic check
        res_lower = res_text.lower()
        passed = all(str(e).lower() in res_lower for e in task_def["expected"])
        details = res_text[:300]
        
        # Strict fallback checking: fail if hallucination/fallback keywords exist
        hallucination_kws = ["under normal conditions", "under normal operating conditions", "backend api server", "outage", "unresponsive", "timing out", "0 product cards were populated"]
        if any(k in res_lower for k in hallucination_kws):
            passed = False
    else:
        # If the task hits max iterations, it might say "stopped after reaching maximum"
        # We also treat it as a failure
        res_text = result.get("result", "") if result else result.get("error", "Error") if result else "Connection Error"
        
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    meta = result.get("metadata", {}) if result else {}
    
    return {
        "run_id": str(uuid.uuid4()),
        "task_id": task_def["id"],
        "benchmark_family": task_def["family"],
        "task": task_def["task"],
        "domain": task_def["domain"],
        "condition": condition,
        "isolated_db_path": temp_db_path,
        "use_procedures": use_procedures,
        "procedure_capability": meta.get("procedure_capability"),
        "procedure_abstract_query": meta.get("procedure_abstract_query"),
        "procedure_confidence": meta.get("procedure_confidence"),
        "retrieved_procedure_ids": meta.get("retrieved_procedure_ids", []),
        "retrieved_procedure_scores": meta.get("retrieved_procedure_scores", []),
        "retrieval_threshold": meta.get("procedure_retrieval_threshold"),
        "procedure_context_injected": meta.get("procedure_context_injected", False),
        "exact_procedure_context": meta.get("exact_procedure_context"),
        "tool_call_count": meta.get("tool_call_count", 0),
        "failed_tool_call_count": meta.get("failed_tool_call_count", 0),
        "tool_traces": meta.get("tool_traces", []),
        "gate_decision": meta.get("gate_decision"),
        "gate_reason": meta.get("gate_reason"),
        "gate_confidence": meta.get("gate_confidence"),
        "gate_exception": meta.get("gate_exception"),
        "duration_seconds": meta.get("duration_seconds", 0.0),
        "final_result": res_text,
        "deterministic_validation": {
            "passed": passed,
            "details": details
        },
        "episode_outcome": "completed" if passed else "failed"
    }

def main():
    runs = []
    for t in tasks:
        runs.append(("baseline", t))
        runs.append(("current_procedural", t))
        runs.append(("gated_procedural", t))
        
    random.shuffle(runs)
    
    results = []
    print(f"Starting {len(runs)} benchmark runs (V3)...")
    
    with open("raw_benchmark_results_v3.jsonl", "w") as f:
        pass
    
    for i, (condition, task) in enumerate(runs):
        print(f"[{i+1}/{len(runs)}] Running {task['id']} - {condition.upper()}")
        res = run_trial(condition, task)
        results.append(res)
        
        with open("raw_benchmark_results_v3.jsonl", "a") as f:
            f.write(json.dumps(res) + "\n")
            
    print("Benchmark complete.")

if __name__ == "__main__":
    main()
