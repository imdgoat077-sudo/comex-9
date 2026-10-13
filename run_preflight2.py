import json
import subprocess
from full_benchmark_v3 import run_trial, tasks
import time

t10 = next(t for t in tasks if t["id"] == "T10")
# run_trial doesn't dump stderr easily. Let's patch agent_service to log to a file.
