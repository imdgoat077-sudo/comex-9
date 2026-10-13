import json
import subprocess
import os

p = subprocess.Popen([".venv/bin/python", "agent_service.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

import time
time.sleep(3)

# make a request
import urllib.request
req_data = json.dumps({
    "task": "Test task",
    "tabId": "bench_gated",
    "taskId": "bench_gated",
    "intent": "VISIBLE_BROWSER_TASK",
    "use_procedures": True,
    "procedure_mode": "gated"
}).encode('utf-8')
try:
    req = urllib.request.Request("http://127.0.0.1:8000/agent/run", data=req_data, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
except Exception as e:
    pass

p.terminate()
out, err = p.communicate()
for line in err.decode().split('\n'):
    if "Received AgentRequest" in line or "Gating failed" in line:
        print(line)
