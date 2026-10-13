import urllib.request
import json
import time
import kuzu
import os
import uuid

TASKS = [
    {
        "id": "quotes",
        "baseline_text": "Go to http://quotes.toscrape.com/ and extract the text and author of the top 3 quotes.",
    },
    {
        "id": "gdp",
        "baseline_text": "Go to https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal) and extract the country name and IMF forecast for the top 3 countries.",
    },
    {
        "id": "films",
        "baseline_text": "Go to https://en.wikipedia.org/wiki/List_of_highest-grossing_films and extract the title and worldwide gross of the top 3 films.",
    }
]

PROCEDURAL_KNOWLEDGE = """

AVAILABLE METHOD PATTERN (List Record Extraction):
Goal: Extract a subset of repeated structured items from a feed/list/table.
Preconditions: Data exists on a single URL, visibly rendered in a repeating structural DOM pattern.
Abstract Operations:
1. Navigate to URL and wait for load.
2. Identify Container: Isolate the CSS selector uniquely identifying the repeating wrapper element for each record.
3. Map Fields: Iterate over selected containers, extracting specific text/attributes per requested field.
4. Filter/Slice: Apply limits to the extracted collection.
5. Format & Return: Serialize into JSON payload.
Note: You must independently determine the site-specific CSS selectors. Do NOT assume any specific selectors or concrete implementation (like Array.map).
"""

def run_task(task_text, task_id):
    req_data = json.dumps({
        "task": task_text,
        "tabId": f"tab_{task_id}",
        "taskId": task_id,
        "intent": "VISIBLE_BROWSER_TASK"
    }).encode('utf-8')
    
    req = urllib.request.Request("http://localhost:8000/agent/run", data=req_data, headers={'Content-Type': 'application/json'})
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode())
            elapsed = time.time() - start_time
            return result.get('success'), elapsed, result.get('result')
    except Exception as e:
        return False, time.time() - start_time, str(e)

print("Starting Efficacy Experiment...")

# We will run them sequentially and store agent IDs
# Since agent IDs are not returned directly by the API in this mock setup, we will just query the last 6 agents ordered by created_at.
results = []

for t in TASKS:
    # BASELINE
    t_id_base = f"base_{t['id']}_{uuid.uuid4().hex[:6]}"
    print(f"Running BASELINE for {t['id']}...")
    succ, dur, res_text = run_task(t["baseline_text"], t_id_base)
    results.append({"type": "baseline", "task_id": t["id"], "success": succ, "duration": dur})
    
    # LEARNED
    t_id_learn = f"learn_{t['id']}_{uuid.uuid4().hex[:6]}"
    print(f"Running LEARNED for {t['id']}...")
    succ, dur, res_text = run_task(t["baseline_text"] + PROCEDURAL_KNOWLEDGE, t_id_learn)
    results.append({"type": "learned", "task_id": t["id"], "success": succ, "duration": dur})

# Kill agent service safely before querying graph
print("Killing agent_service to release DB lock...")
import subprocess
try:
    with open("agent_service.pid") as f:
        pid = f.read().strip()
    subprocess.run(["kill", "-9", pid])
except Exception:
    pass

print("Extracting Traces...")
db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

res = conn.execute("MATCH (a:Agent) RETURN a.id, a.task, a.created_at ORDER BY a.created_at DESC LIMIT 6")
agents = []
while res.has_next():
    agents.append(res.get_next())

# Reverse to chronological
agents = list(reversed(agents))

trace_out = []
for i, a in enumerate(agents):
    a_id = a[0]
    task_text = a[1]
    
    # Get outcome
    out_res = conn.execute("MATCH (e:Episode)-[:FOR]->(a:Agent {id: $aid}) RETURN e.outcome_status", {"aid": a_id})
    outcome = out_res.get_next()[0] if out_res.has_next() else "unknown"
    
    # Get tool calls
    t_res = conn.execute("MATCH (a:Agent {id: $aid})-[r:EXECUTED]->(t:ToolCall) RETURN t.id, t.tool_name, t.success, t.step_index ORDER BY t.step_index ASC", {"aid": a_id})
    tool_calls = []
    failures = 0
    while t_res.has_next():
        t = t_res.get_next()
        if not t[2]:
            failures += 1
        tool_calls.append({"name": t[1], "success": t[2]})
        
    trace_out.append({
        "type": "learned" if "AVAILABLE METHOD PATTERN" in task_text else "baseline",
        "task_text": task_text,
        "duration": results[i]["duration"],
        "outcome": outcome,
        "tool_count": len(tool_calls),
        "failures": failures,
        "tool_names": [t["name"] for t in tool_calls]
    })

with open("efficacy_experiment_results.json", "w") as f:
    json.dump(trace_out, f, indent=2)

print("Experiment Complete. Results written to efficacy_experiment_results.json")
