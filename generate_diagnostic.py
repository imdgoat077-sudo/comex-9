import json

def load_results():
    results = []
    with open("raw_benchmark_results_v2.jsonl", "r") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

def get_trace_summary(traces):
    if not traces: return "No tools"
    seq = []
    for t in traces:
        name = t["tool"]
        success = "✅" if t.get("success", True) else "❌"
        args = t.get("args", {})
        code_snippet = ""
        if name == "run_browser_harness":
            code = args.get("code", "")
            if "querySelectorAll" in code: code_snippet = "[querySelectorAll]"
            elif "getElementById" in code: code_snippet = "[getElementById]"
            elif "click" in code: code_snippet = "[click]"
            elif "submit" in code: code_snippet = "[submit]"
            elif "Array.from" in code: code_snippet = "[Array.from]"
            else: code_snippet = "[JS]"
        seq.append(f"{name}{code_snippet}({success})")
    return " -> ".join(seq)

def get_js_details(traces):
    js = []
    for t in traces:
        if t["tool"] == "run_browser_harness":
            code = t.get("args", {}).get("code", "")
            # keep it somewhat short
            if len(code) > 100:
                js.append(code[:50] + "..." + code[-50:])
            else:
                js.append(code)
    return js

def main():
    results = load_results()
    tasks_info = {}
    for r in results:
        t_id = r["task_id"]
        if t_id not in tasks_info:
            tasks_info[t_id] = {"baseline": None, "procedural": None}
        tasks_info[t_id][r["condition"]] = r

    with open("diagnostic_dump.md", "w") as out:
        out.write("# Diagnostic Dump\n\n")
        
        for t_id in sorted(tasks_info.keys(), key=lambda x: int(x[1:]) if "_" not in x else int(x.split("_")[0][1:])):
            out.write(f"## {t_id}\n")
            
            b = tasks_info[t_id]["baseline"]
            p = tasks_info[t_id]["procedural"]
            
            b_pass = "✅" if b["deterministic_validation"]["passed"] else "❌"
            p_pass = "✅" if p["deterministic_validation"]["passed"] else "❌"
            
            out.write(f"- Baseline ({b_pass}): {b['tool_call_count']} tools, {b['failed_tool_call_count']} failed\n")
            out.write(f"  Trace: {get_trace_summary(b.get('tool_traces', []))}\n")
            out.write(f"  JS Highlights: {json.dumps(get_js_details(b.get('tool_traces', [])))}\n")
            
            out.write(f"- Procedural ({p_pass}): {p['tool_call_count']} tools, {p['failed_tool_call_count']} failed\n")
            out.write(f"  Trace: {get_trace_summary(p.get('tool_traces', []))}\n")
            out.write(f"  JS Highlights: {json.dumps(get_js_details(p.get('tool_traces', [])))}\n")
            out.write("\n")

if __name__ == "__main__":
    main()
