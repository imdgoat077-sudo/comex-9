import json

def main():
    results = []
    with open("raw_benchmark_results_v3.jsonl", "r") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
                
    gated = [r for r in results if r["condition"] == "gated_procedural"]
    
    print("\n--- REAL V3 GATED RUNS SNEAK PEEK ---")
    for r in gated:
        t_id = r["task_id"]
        dec = "INJECT" if r.get("gate_decision") else "REJECT"
        rsn = r.get("gate_reason", "None")
        if len(rsn) > 50: rsn = rsn[:47] + "..."
        passed = "✅" if r["deterministic_validation"].get("passed") else "❌"
        print(f"[{t_id}] Result: {passed} | Gate: {dec} | Reason: {rsn}")

if __name__ == "__main__":
    main()
