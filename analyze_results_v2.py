import json
import statistics

TASK_FAMILIES = {
    "T1": "extract_list_items",
    "T2_v2": "extract_list_items",
    "T3": "extract_list_items",
    "T4": "search_and_extract",
    "T5": "search_and_extract",
    "T6": "search_and_extract",
    "T7": "form_submission",
    "T8": "form_submission",
    "T9": "form_submission",
    "T10": "click_detail_and_extract",
    "T11": "click_detail_and_extract",
    "T12": "click_detail_and_extract"
}

def load_results():
    results = []
    with open("raw_benchmark_results_v2.jsonl", "r") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

def strict_validate(r):
    res_text = r.get("final_result", "").lower()
    passed = r["deterministic_validation"].get("passed", False)
    
    hallucination_kws = ["under normal conditions", "under normal operating conditions", "backend api server", "outage", "unresponsive", "timing out", "0 product cards were populated"]
    if any(k in res_text for k in hallucination_kws):
        passed = False
        
    t_id = r.get("task_id")
    if t_id == "T1":
        if "definiebas0" not in res_text or "definiebas1" not in res_text:
            passed = False
    elif t_id == "T2_v2":
        if "smith" not in res_text or "bach" not in res_text or "doe" not in res_text:
            passed = False
            
    # Browser grounding: must have at least one successful run_browser_harness
    traces = r.get("tool_traces", [])
    has_browser = any(t.get("tool") == "run_browser_harness" and t.get("success", False) for t in traces)
    
    if not has_browser:
        passed = False
        
    return passed

def check_procedure_followed(r):
    traces = r.get("tool_traces", [])
    fam = r["benchmark_family"]
    
    js_code = " ".join([t.get("args", {}).get("code", "") for t in traces if t.get("tool") == "run_browser_harness"]).lower()
    
    if fam == "extract_list_items":
        return "queryselectorall" in js_code or "getelementsby" in js_code
    elif fam == "search_and_extract":
        return "submit" in js_code or "click" in js_code or "value =" in js_code
    elif fam == "form_submission":
        return "click" in js_code or "value =" in js_code
    elif fam == "click_detail_and_extract":
        return "click" in js_code
    return False

def main():
    results = load_results()
    if not results: return
    
    for r in results:
        r["strict_passed"] = strict_validate(r)
        r["benchmark_family"] = TASK_FAMILIES.get(r["task_id"], "unknown")
        
    baseline_runs = [r for r in results if r["condition"] == "baseline"]
    procedural_runs = [r for r in results if r["condition"] == "procedural"]

    def success_rate(runs):
        if not runs: return 0.0
        successes = sum(1 for r in runs if r.get("strict_passed", False))
        return (successes / len(runs)) * 100

    def median_metric(runs, key):
        if not runs: return 0.0
        vals = [r.get(key, 0) for r in runs]
        return statistics.median(vals)
        
    base_sr = success_rate(baseline_runs)
    proc_sr = success_rate(procedural_runs)
    diff = proc_sr - base_sr

    base_tools = median_metric(baseline_runs, "tool_call_count")
    proc_tools = median_metric(procedural_runs, "tool_call_count")
    
    base_fails = median_metric(baseline_runs, "failed_tool_call_count")
    proc_fails = median_metric(procedural_runs, "failed_tool_call_count")
    
    base_dur = median_metric(baseline_runs, "duration_seconds")
    proc_dur = median_metric(procedural_runs, "duration_seconds")
    
    # Procedure states
    proc_retrieved = 0
    proc_correct_retrieved = 0
    proc_injected = 0
    proc_followed = 0
    
    for r in procedural_runs:
        ids = r.get("retrieved_procedure_ids", [])
        if ids:
            proc_retrieved += 1
            ctx = r.get("exact_procedure_context", "")
            if "Procedural Candidate" in ctx:
                proc_correct_retrieved += 1
        
        if r.get("procedure_context_injected"):
            proc_injected += 1
            
        if check_procedure_followed(r):
            proc_followed += 1

    report = [
        "# Phase 12C/D Benchmark Report V2 (Corrected Instrumentation)",
        "",
        "## Overall Metrics",
        f"- **Baseline Browser-Grounded Task Success Rate**: {base_sr:.1f}%",
        f"- **Procedural Browser-Grounded Task Success Rate**: {proc_sr:.1f}%",
        f"- **Absolute Success-Rate Difference**: {diff:+.1f}%",
        "",
        "### Procedural States (Out of 12 runs)",
        f"- **A. Procedure Retrieved**: {proc_retrieved}/12",
        f"- **B. Correct Procedure Retrieved**: {proc_correct_retrieved}/12",
        f"- **C. Procedure Injected**: {proc_injected}/12",
        f"- **D. Behaviorally-Followed Procedure**: {proc_followed}/12",
        "",
        "### Operational Metrics (Medians)",
        "| Condition | Tool Calls | Failed Tools | Duration (s) |",
        "|-----------|------------|--------------|--------------|",
        f"| Baseline  | {base_tools:.1f} | {base_fails:.1f} | {base_dur:.1f} |",
        f"| Procedural| {proc_tools:.1f} | {proc_fails:.1f} | {proc_dur:.1f} |",
        ""
    ]
    
    # Efficiency analysis
    fewer_tools = 0
    fewer_tools_more_dur = 0
    tasks_info = {}
    for r in results:
        t_id = r["task_id"]
        if t_id not in tasks_info:
            tasks_info[t_id] = {"baseline": None, "procedural": None}
        tasks_info[t_id][r["condition"]] = r
        
    for t_id, conditions in tasks_info.items():
        if conditions["baseline"] and conditions["procedural"]:
            b_tc = conditions["baseline"]["tool_call_count"]
            p_tc = conditions["procedural"]["tool_call_count"]
            b_dur = conditions["baseline"]["duration_seconds"]
            p_dur = conditions["procedural"]["duration_seconds"]
            
            if p_tc < b_tc:
                fewer_tools += 1
                if p_dur > b_dur:
                    fewer_tools_more_dur += 1
                    
    report.append("### Efficiency Analysis")
    report.append(f"- **Cases where Procedural used fewer tool calls**: {fewer_tools}/12")
    report.append(f"- **Cases where Procedural used fewer tool calls BUT took longer**: {fewer_tools_more_dur}/{fewer_tools}")
    report.append("")
    
    report.append("## Per-Family Results")
    family_results = {}
    for r in results:
        fam = r["benchmark_family"]
        if fam not in family_results:
            family_results[fam] = {"base_pass": 0, "proc_pass": 0, "total": 0}
        
        if r["condition"] == "baseline":
            if r["strict_passed"]: family_results[fam]["base_pass"] += 1
            family_results[fam]["total"] += 1
        else:
            if r["strict_passed"]: family_results[fam]["proc_pass"] += 1
            
    for fam, stats in family_results.items():
        total = stats["total"]
        if total == 0: continue
        b_rate = (stats["base_pass"] / total) * 100
        p_rate = (stats["proc_pass"] / total) * 100
        report.append(f"### {fam}")
        report.append(f"- Baseline: {b_rate:.1f}% ({stats['base_pass']}/{total})")
        report.append(f"- Procedural: {p_rate:.1f}% ({stats['proc_pass']}/{total})")
        
    report.append("")
    report.append("## Per-Task Results")
    report.append("| Task ID | Family | Baseline | Procedural | Delta |")
    report.append("|---------|--------|----------|------------|-------|")
    
    for t_id in sorted(tasks_info.keys(), key=lambda x: int(x[1:]) if "_" not in x else int(x.split("_")[0][1:])):
        info = tasks_info[t_id]
        b = "✅" if info["baseline"]["strict_passed"] else "❌"
        p = "✅" if info["procedural"]["strict_passed"] else "❌"
        d = ""
        if not info["baseline"]["strict_passed"] and info["procedural"]["strict_passed"]: d = "📈 Improved"
        elif info["baseline"]["strict_passed"] and not info["procedural"]["strict_passed"]: d = "📉 Regressed"
        elif info["baseline"]["strict_passed"] and info["procedural"]["strict_passed"]: d = "➖ Equal (Pass)"
        else: d = "➖ Equal (Fail)"
        fam = info["baseline"]["benchmark_family"]
        report.append(f"| {t_id} | {fam} | {b} | {p} | {d} |")
        
    report.append("")
    report.append("## Behavioral Evidence Trace (Procedural Runs)")
    for r in procedural_runs:
        followed = check_procedure_followed(r)
        status = "✅ Followed" if followed else "❌ Diverged"
        report.append(f"- **{r['task_id']}**: {status} (Tool Calls: {r['tool_call_count']})")
        
    report.append("")
    report.append("## Final Verdict")
    if diff > 10.0 and proc_followed > 6:
        report.append("**A. PROCEDURAL MEMORY SHOWS MEASURABLE BENEFIT**")
    elif diff >= 0.0 and proc_retrieved >= 6:
        report.append("**B. PROCEDURAL MEMORY RETRIEVES CORRECTLY BUT BENEFIT IS NOT YET SHOWN**")
    else:
        report.append("**C. RETRIEVAL/EXPERIMENT IS INVALID**")

    with open("benchmark_report_v2.md", "w") as f:
        f.write("\n".join(report))
        
    print("Report generated: benchmark_report_v2.md")

if __name__ == "__main__":
    main()
