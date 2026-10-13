import urllib.request
import json
import time
import os
import kuzu

task_text = "Go to http://books.toscrape.com/catalogue/category/books/science_22/index.html and extract the title and price of the first 3 books."

req_data = json.dumps({
    "task": task_text,
    "tabId": "val_exp",
    "taskId": "val_exp",
    "intent": "VISIBLE_BROWSER_TASK"
}).encode('utf-8')

print(f"Running task: {task_text}")
req = urllib.request.Request("http://localhost:8000/agent/run", data=req_data, headers={'Content-Type': 'application/json'})

start_time = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode())
        elapsed = time.time() - start_time
        print(f"Outcome: {result}")
        print(f"Duration: {elapsed:.2f}s")
except Exception as e:
    print(f"Error: {e}")

print("Killing agent_service to check DB...")
import subprocess
try:
    with open("agent_service.pid") as f:
        pid = f.read().strip()
    subprocess.run(["kill", "-9", pid])
except Exception:
    pass

db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

res = conn.execute("MATCH (a:Agent) RETURN a.id ORDER BY a.created_at DESC LIMIT 1")
a_id = res.get_next()[0]

print(f"Agent ID: {a_id}")

t_res = conn.execute("MATCH (a:Agent {id: $aid})-[r:EXECUTED]->(t:ToolCall) RETURN t.step_index, t.tool_name, t.success, t.args_json ORDER BY t.step_index ASC", {"aid": a_id})
tool_calls = []
while t_res.has_next():
    t = t_res.get_next()
    tool_calls.append(t)

print(f"Tool Call count: {len(tool_calls)}")
for t in tool_calls:
    print(f"Step {t[0]} - {t[1]} (Success={t[2]})")

