import json
with open("raw_benchmark_results_v3.jsonl", "r") as f:
    for line in f:
        r = json.loads(line)
        if r["condition"] == "baseline":
            print(r)
            break
