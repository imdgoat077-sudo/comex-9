import subprocess
import os

env = os.environ.copy()
env["PORT"] = "8555"
p = subprocess.Popen([".venv/bin/python", "agent_service.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

import time
time.sleep(5)

subprocess.run([".venv/bin/python", "preflight_v3.py"])

p.terminate()
out, err = p.communicate()
for line in err.decode().split('\n'):
    if "Gating failed" in line:
        print(line)
