import urllib.request
import json
import time
import kuzu
import os

task_text = "Go to https://books.toscrape.com/ and list the titles and prices of the top 3 books."
req_data = json.dumps({
    "task": task_text,
    "tabId": "tab1",
    "taskId": "experiment_1",
    "intent": "VISIBLE_BROWSER_TASK"
}).encode('utf-8')

req = urllib.request.Request("http://localhost:8000/agent/run", data=req_data, headers={'Content-Type': 'application/json'})

print("Dispatching task...")
start_time = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode())
        elapsed = time.time() - start_time
        print(f"Success: {result.get('success')}")
        print(f"Duration: {elapsed:.2f}s")
        print(f"Outcome: {result.get('result')[:300]}")
except Exception as e:
    print(f"Failed: {e}")

import subprocess
subprocess.run(["kill", "-9", open("agent_service.pid").read().strip()])
print("\n--- GRABBING DB TRACE ---")
db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

# The newest agent
res = conn.execute("MATCH (a:Agent) RETURN a.id, a.task ORDER BY a.created_at DESC LIMIT 1").get_next()
agent_id = res[0]
print(f"Agent ID: {agent_id}")
print(f"Task: {res[1]}")

res = conn.execute("MATCH (e:Episode)-[:FOR]->(a:Agent {id: $aid}) RETURN e.id, e.outcome_status", {"aid": agent_id}).get_next()
print(f"Episode ID: {res[0]} (Status: {res[1]})")

res = conn.execute("MATCH (a:Agent {id: $aid})-[r:EXECUTED]->(t:ToolCall) RETURN t.id, t.tool_name, t.success, t.step_index, t.args_json, t.result_summary ORDER BY t.step_index ASC", {"aid": agent_id})
tool_calls = []
while res.has_next():
    t = res.get_next()
    tool_calls.append({
        "id": t[0],
        "name": t[1],
        "success": t[2],
        "step": t[3],
        "args": t[4],
        "res": t[5]
    })

print(f"Total ToolCalls: {len(tool_calls)}")
for t in tool_calls:
    print(f"\nStep {t['step']}: {t['name']} (Success={t['success']})")
    print(f"Args Snippet: {t['args'][:200].replace(chr(10), ' ')}")
    print(f"Res Snippet: {t['res'][:200].replace(chr(10), ' ')}")
