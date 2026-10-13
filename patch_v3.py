import re

with open("full_benchmark_v3.py", "r") as f:
    content = f.read()

# Add T13 to tasks
tasks_str = content.split("tasks = [")[1].split("]")[0]
new_task = """    {
        "id": "T13", "family": "form_submission", "domain": "the-internet.herokuapp.com",
        "task": "Go to https://the-internet.herokuapp.com/login, DO NOT submit the form, just extract the text of the subheader h2 element.",
        "expected": ["Login Page"]
    }
"""
content = content.replace("tasks = [", f"tasks = [\n{new_task}")

# Update run_trial signature and payload
content = content.replace("def run_trial(condition: str, task_def: dict) -> dict:", "def run_trial(condition: str, task_def: dict) -> dict:")

# Inside run_trial, modify use_procedures and procedure_mode
run_trial_body = """    use_procedures = (condition != "baseline")
    procedure_mode = "none" if condition == "baseline" else ("gated" if condition == "gated_procedural" else "blind")
    req_data = json.dumps({
        "task": task_def["task"],
        "tabId": f"bench_{condition}_{task_def['id']}",
        "taskId": f"bench_{condition}_{task_def['id']}",
        "intent": "VISIBLE_BROWSER_TASK",
        "use_procedures": use_procedures,
        "procedure_mode": procedure_mode
    }).encode('utf-8')"""

content = re.sub(
    r'    use_procedures = \(condition == "procedural"\)\n.*?\}\)\.encode\(\'utf-8\'\)',
    run_trial_body,
    content,
    flags=re.DOTALL
)

# Update return dict
return_update = """        "tool_traces": meta.get("tool_traces", []),
        "gate_decision": meta.get("gate_decision"),
        "gate_reason": meta.get("gate_reason"),
        "gate_confidence": meta.get("gate_confidence"),
        "duration_seconds": meta.get("duration_seconds", 0.0),"""
content = content.replace('        "tool_traces": meta.get("tool_traces", []),\n        "duration_seconds": meta.get("duration_seconds", 0.0),', return_update)

# Update the main trials generation
main_loop = """    trials = []
    for t in tasks:
        trials.append(("baseline", t))
        trials.append(("current_procedural", t))
        trials.append(("gated_procedural", t))
    
    random.shuffle(trials)
    
    print(f"Starting {len(trials)} benchmark runs (V3)...")
    with open("raw_benchmark_results_v3.jsonl", "w") as f:
        pass  # clear previous
    
    for i, (condition, task) in enumerate(trials):
        print(f"[{i+1}/{len(trials)}] Running {task['id']} - {condition.upper()}")
        res = run_trial(condition, task)
        results.append(res)
        
        with open("raw_benchmark_results_v3.jsonl", "a") as f:
            f.write(json.dumps(res) + "\\n")"""

content = re.sub(
    r'    trials = \[\]\n.*?f\.write\(json\.dumps\(res\) \+ "\\n"\)',
    main_loop,
    content,
    flags=re.DOTALL
)

with open("full_benchmark_v3.py", "w") as f:
    f.write(content)
