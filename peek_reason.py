import json

with open("raw_benchmark_results_v3.jsonl", "r") as f:
    for line in f:
        r = json.loads(line)
        if r["condition"] == "gated_procedural":
            print(f"Task: {r['task_id']}")
            print(f"gate_decision: {r.get('gate_decision')}")
            print(f"gate_reason: {r.get('gate_reason')}")
            print(f"gate_confidence: {r.get('gate_confidence')}")
            print("---")
            break
