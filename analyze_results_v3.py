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
    "T12": "click_detail_and_extract",
    "T13": "form_submission" # Trap task
}

def load_results():
    results = []
    with open("raw_benchmark_results_v3.jsonl", "r") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

def strict_validate(r):
    res_text = str(r.get("final_result", "") or "").lower()
    passed = r["deterministic_validation"].get("passed", False)
    
    hallucination_kws = ["under normal conditions", "under normal operating conditions", "backend api server", "outage", "unresponsive", "timing out", "0 product cards were populated"]
    if any(k in res_text for k in hallucination_kws):
        passed = False
        
    t_id = r.get("task_id")
    if t_id == "T1":
        if "definiebas0" not in res_text or "definiebas1" not in res_text: passed = False
    elif t_id == "T2_v2":
        if "smith" not in res_text or "bach" not in res_text or "doe" not in res_text: passed = False
    elif t_id == "T13":
        # must NOT have submitted the form, should just grab the h2 "Login Page"
        if "login page" not in res_text: passed = False
            
    # Browser grounding
    traces = r.get("tool_traces", [])
    has_browser = any(t.get("tool") == "run_browser_harness" and t.get("success", False) for t in traces)
    if not has_browser:
        passed = False
        
    return passed

def check_procedure_followed(r):
    traces = r.get("tool_traces", [])
    fam = r["benchmark_family"]
    
    js_code = " ".join([t.get("args", {}).get("code", "") for t in traces if t.get("tool") == "run_browser_harness"]).lower()
    
    if fam == "extract_list_items": return "queryselectorall" in js_code or "getelementsby" in js_code
    elif fam == "search_and_extract": return "submit" in js_code or "click" in js_code or "value =" in js_code
    elif fam == "form_submission": return "click" in js_code or "value =" in js_code
    elif fam == "click_detail_and_extract": return "click" in js_code
    return False

def main():
    results = load_results()
    if not results: return
    
    tasks_info = {}
    for r in results:
        r["strict_passed"] = strict_validate(r)
        r["benchmark_family"] = TASK_FAMILIES.get(r["task_id"], "unknown")
        
        t_id = r["task_id"]
        if t_id not in tasks_info:
            tasks_info[t_id] = {"baseline": None, "current_procedural": None, "gated_procedural": None}
        tasks_info[t_id][r["condition"]] = r
        
    baseline = [r for r in results if r["condition"] == "baseline"]
    current_proc = [r for r in results if r["condition"] == "current_procedural"]
    gated_proc = [r for r in results if r["condition"] == "gated_procedural"]

    def sr(runs):
        return (sum(1 for r in runs if r.get("strict_passed")) / len(runs)) * 100 if runs else 0

    base_sr = sr(baseline)
    curr_sr = sr(current_proc)
    gate_sr = sr(gated_proc)

    def median_tc(runs):
        return statistics.median([r.get("tool_call_count", 0) for r in runs]) if runs else 0

    base_tc = median_tc(baseline)
    curr_tc = median_tc(current_proc)
    gate_tc = median_tc(gated_proc)
    
    report = [
        "# Phase 12F Benchmark Report (Gating Experiment)",
        "",
        "## Overall Success Rates",
        f"- **Baseline**: {base_sr:.1f}%",
        f"- **Current Procedural (Blind)**: {curr_sr:.1f}%",
        f"- **Gated Procedural**: {gate_sr:.1f}%",
        "",
        "## Overall Median Tool Calls",
        f"- **Baseline**: {base_tc:.1f}",
        f"- **Current Procedural**: {curr_tc:.1f}",
        f"- **Gated Procedural**: {gate_tc:.1f}",
        "",
        "## Detailed Task Comparisons",
        "| Task ID | Baseline | Blind Proc | Gated Proc | Gate Decision | Gate Reason |",
        "|---------|----------|------------|------------|---------------|-------------|"
    ]
    
    correct_rejections = 0
    incorrect_rejections = 0
    
    for t_id in sorted(tasks_info.keys(), key=lambda x: int(x[1:]) if "_" not in x else int(x.split("_")[0][1:])):
        info = tasks_info[t_id]
        b = info.get("baseline")
        c = info.get("current_procedural")
        g = info.get("gated_procedural")
        if not b or not c or not g: continue
        
        b_p = "✅" if b["strict_passed"] else "❌"
        c_p = "✅" if c["strict_passed"] else "❌"
        g_p = "✅" if g["strict_passed"] else "❌"
        
        dec = "INJECT" if g.get("gate_decision") else "REJECT"
        rsn = str(g.get("gate_reason", "")).replace('\n', ' ')
        if len(rsn) > 50: rsn = rsn[:47] + "..."
        
        report.append(f"| {t_id} | {b_p} | {c_p} | {g_p} | {dec} | {rsn} |")
        
        if t_id == "T12":
            # Procedural hurt T12. So if it rejected, it was correct.
            if not g.get("gate_decision"): correct_rejections += 1
        if t_id == "T13":
            # Procedure irrelevant. Should reject.
            if not g.get("gate_decision"): correct_rejections += 1
        if t_id == "T10":
            # Procedural helped T10. So if it rejected, it was incorrect.
            if not g.get("gate_decision"): incorrect_rejections += 1
            
    report.append("")
    report.append("## Gating Impact Analysis")
    report.append(f"- **T10-like Rescue Cases Preserved (Gate=INJECT)**: {1 - incorrect_rejections} (Expected: 1)")
    report.append(f"- **T12/T13-like Regression/Trap Cases Avoided (Gate=REJECT)**: {correct_rejections} (Expected: 2)")
    
    report.append("")
    report.append("## Final Verdict")
    if gate_sr > max(base_sr, curr_sr):
        report.append("**A. Gating materially improves procedural memory**")
    elif gate_sr >= base_sr and correct_rejections > 0:
        report.append("**B. Gating reduces regressions but benefit remains unproven**")
    else:
        report.append("**C. Gating does not help**")

    with open("benchmark_report_v3.md", "w") as f:
        f.write("\n".join(report))
        
    print("Report generated: benchmark_report_v3.md")

if __name__ == "__main__":
    main()
