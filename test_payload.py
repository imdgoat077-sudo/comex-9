import json
from full_benchmark_v3 import run_trial, tasks
import urllib.request
from unittest.mock import patch

t10 = next(t for t in tasks if t["id"] == "T10")

def mock_urlopen(req, *args, **kwargs):
    print("Payload sent:")
    print(req.data.decode('utf-8'))
    import sys
    sys.exit(0)

with patch('urllib.request.urlopen', side_effect=mock_urlopen):
    run_trial("gated_procedural", t10)
