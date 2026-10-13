import json
from collections import defaultdict

def analyze():
    records = []
    with open("phase14_v3_results.jsonl", "r") as f:
        for line in f:
            records.append(json.loads(line))
            
    # Group by (Task, Condition, Procedure - if applicable)
    # Actually, Baseline condition shouldn't be split by procedure, because it's identical per task. 
    # But because of the randomization matrix, we have 9 baseline runs per task (3 per procedure). 
    # We can aggregate all Baseline runs for a Task to get a robust baseline average (n=9).
    
    tasks = set(r["task_id"] for r in records)
    procs = set(r["procedure_id"] for r in records)
    
    print("# Phase 14 V3 — Replication Analysis\n")
    
    final_verdict = "C. No reproducible benefit"
    helpful_count = 0
    
    for task in tasks:
        print(f"## Task: {task}")
        # Agg Baseline for this task
        base_runs = [r for r in records if r["task_id"] == task and r["condition"] == "BASELINE"]
        avg_base_succ = sum(r["success"] for r in base_runs) / len(base_runs)
        avg_base_tools = sum(r["tool_call_count"] for r in base_runs) / len(base_runs)
        avg_base_dur = sum(r["duration"] for r in base_runs) / len(base_runs)
        
        print(f"Baseline (n={len(base_runs)}):")
        print(f"  Success: {avg_base_succ*100:.1f}%")
        print(f"  Avg Tools: {avg_base_tools:.2f}")
        print(f"  Avg Duration: {avg_base_dur:.1f}s\n")
        
        # Eval each procedure on this task
        for proc in procs:
            proc_runs = [r for r in records if r["task_id"] == task and r["condition"] == "PROCEDURAL" and r["procedure_id"] == proc]
            if not proc_runs: continue
            
            avg_proc_succ = sum(r["success"] for r in proc_runs) / len(proc_runs)
            avg_proc_tools = sum(r["tool_call_count"] for r in proc_runs) / len(proc_runs)
            avg_proc_dur = sum(r["duration"] for r in proc_runs) / len(proc_runs)
            
            # Gating stats
            retrieved_count = sum(r["procedure_retrieved"] for r in proc_runs)
            injected_count = sum(r["procedure_injected"] for r in proc_runs)
            
            # Classify
            classification = "Inconclusive"
            if avg_proc_succ < avg_base_succ:
                classification = "Harmful"
            elif avg_proc_succ == avg_base_succ:
                # Check tool calls
                if avg_proc_tools < avg_base_tools and avg_proc_dur <= avg_base_dur * 1.2:
                    classification = "Helpful"
                    helpful_count += 1
                elif avg_proc_tools > avg_base_tools or avg_proc_dur > avg_base_dur * 1.5:
                    classification = "Harmful"
                else:
                    classification = "Neutral"
            elif avg_proc_succ > avg_base_succ:
                classification = "Helpful"
                helpful_count += 1
                
            # If the procedure wasn't injected, it can't be Helpful/Harmful due to the procedure text itself,
            # but the gating decision is part of the system behavior. If it was gated out, it's Neutral.
            if injected_count == 0 and classification != "Inconclusive":
                classification = "Neutral (Gated Out)"
                
            print(f"Procedure: {proc} (n={len(proc_runs)})")
            print(f"  Retrieved: {retrieved_count}/{len(proc_runs)} | Injected: {injected_count}/{len(proc_runs)}")
            print(f"  Success: {avg_proc_succ*100:.1f}%")
            print(f"  Avg Tools: {avg_proc_tools:.2f}")
            print(f"  Avg Duration: {avg_proc_dur:.1f}s")
            print(f"  Classification: {classification}\n")
            
    print("## Aggregate Summary")
    print(f"Total Runs: {len(records)}")
    print(f"Helpful Configurations: {helpful_count}")
    
    if helpful_count > 0:
        final_verdict = "A. Reproducible procedural benefit"
        
    print(f"\nFinal Verdict: {final_verdict}")

if __name__ == "__main__":
    analyze()
