import json
import sys
from full_benchmark_v3 import run_trial, tasks

t10 = next(t for t in tasks if t["id"] == "T10")

print("--- Preflight: GATED_PROCEDURAL ---", flush=True)
res_gate = run_trial("gated_procedural", t10)
print(f"Gate Decision: {res_gate.get('gate_decision')}", flush=True)
print(f"Gate Reason: {res_gate.get('gate_reason')}", flush=True)
print(f"Gate Confidence: {res_gate.get('gate_confidence')}", flush=True)
print(f"Gate Exception: {res_gate.get('gate_exception')}", flush=True)
