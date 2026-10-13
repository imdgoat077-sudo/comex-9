import asyncio
import json
import tempfile
import os
import urllib.parse
import time
import random
import uuid

from graph.store import AgentGraphStore
from agent_service import execute_agent_loop, MODEL_NAME, OPENAI_BASE_URL, ROUTER_API_KEY

async def run_trial(store: AgentGraphStore, task: str, target_url: str, use_procedures: bool) -> dict:
    t0 = time.time()
    res, meta = await execute_agent_loop(
        task=f"Go to {target_url} and {task}",
        default_cdp_url="ws://127.0.0.1:9222/devtools/browser/xyz",
        intent="VISIBLE_BROWSER_TASK",
        use_procedures=use_procedures,
        procedure_mode="gated",
        use_graph=True
    )
    duration = time.time() - t0
    
    success = "SUCCESS_" in res
    if not success and any(t["success"] for t in meta.get("tool_traces", [])):
        for t in meta.get("tool_traces", []):
            if t["success"] and "SUCCESS_" in str(t.get("result_summary", "")):
                success = True
                break

    trace_text = ""
    failed_tool_call_count = 0
    for tc in meta.get("tool_traces", []):
        trace_text += f"[{tc['tool']}] Args: {tc['args']} -> Success: {tc['success']}\n"
        if not tc["success"]:
            failed_tool_call_count += 1
            
    return {
        "success": success,
        "trace": trace_text,
        "raw_res": res,
        "meta": meta,
        "duration": duration,
        "tool_call_count": meta.get("tool_call_count", 0),
        "failed_tool_call_count": failed_tool_call_count
    }

async def main():
    print("="*50)
    print("PHASE 14 V3 REPLICATION EXPERIMENT")
    print("="*50)

    # 3 Procedures
    procs = {
        "P1_Overlay": {
            "title": "Bypass Blocking Overlays",
            "capability": "ui_overlay_bypass",
            "goal": "Interact with underlying elements when a modal/overlay blocks clicks",
            "preconditions": [],
            "ordered_steps": [
                "Check if an overlay (cookie banner, promo) is intercepting clicks.",
                "Locate the dismiss/close button inside the overlay and click it.",
                "Proceed with interacting with target elements."
            ],
            "applicability_notes": "Use when standard clicks fail due to obscuring elements.",
            "limitations_caveats": "",
            "provenance": {"source_episode_id": "ep_v3_a"}
        },
        "P2_Scroll": {
            "title": "Inner Container Infinite Scroll",
            "capability": "ui_inner_scroll",
            "goal": "Trigger infinite scroll when window scrolling fails",
            "preconditions": [],
            "ordered_steps": [
                "Locate the specific inner container wrapping the list.",
                "Execute scroll events directly on this inner container.",
                "Wait for DOM changes and extract."
            ],
            "applicability_notes": "Use for isolated scroll panes.",
            "limitations_caveats": "",
            "provenance": {"source_episode_id": "ep_v3_b"}
        },
        "P3_Hover": {
            "title": "Hover Reveal Navigation",
            "capability": "ui_hover_reveal",
            "goal": "Access hidden submenu items",
            "preconditions": [],
            "ordered_steps": [
                "Identify the parent navigation menu item.",
                "Dispatch a hover/mouseenter event to reveal the flyout menu.",
                "Click the target submenu link."
            ],
            "applicability_notes": "Use when links are display:none until hovered.",
            "limitations_caveats": "",
            "provenance": {"source_episode_id": "ep_v3_c"}
        }
    }

    # 3 Tasks
    tasks = {
        "T1_Overlay": {
            "html": """<html><body>
                <div id="promo" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:999;">
                    <button class="close-promo" onclick="document.getElementById('promo').style.display='none'">X</button>
                </div>
                <button id="final-btn" onclick="document.body.innerHTML+='SUCCESS_T1'">Click Me</button>
                </body></html>""",
            "task": "Click the final button."
        },
        "T2_Scroll": {
            "html": """<html><body>
                <div class="infinite-list" style="height:50px;overflow-y:auto;" onscroll="if(this.scrollTop>0) { document.body.innerHTML+='SUCCESS_T2'; }">
                    <div class="item">Item 1</div>
                    <div class="item" style="height:100px;">Item 2</div>
                </div>
                </body></html>""",
            "task": "Scroll down the list."
        },
        "T3_Hover": {
            "html": """<html><body>
                <div class="dropdown" onmouseover="document.getElementById('sub').style.display='block'">Hover Menu</div>
                <div id="sub" style="display:none;">
                    <button id="final-btn" onclick="document.body.innerHTML+='SUCCESS_T3'">Target</button>
                </div>
                </body></html>""",
            "task": "Click the target button in the menu."
        }
    }

    runs = []
    for p_name in procs.keys():
        for t_name in tasks.keys():
            for cond in ["BASELINE", "PROCEDURAL"]:
                for rep in range(1, 4):
                    runs.append({
                        "run_id": str(uuid.uuid4()),
                        "procedure_id": p_name,
                        "task_id": t_name,
                        "condition": cond,
                        "rep": rep
                    })
                    
    random.shuffle(runs)
    print(f"Total runs scheduled: {len(runs)}")

    with open("phase14_v3_results.jsonl", "w") as out:
        for i, run_info in enumerate(runs):
            print(f"\n[{i+1}/{len(runs)}] Run: {run_info['run_id']} | Proc: {run_info['procedure_id']} | Task: {run_info['task_id']} | Cond: {run_info['condition']} | Rep: {run_info['rep']}")
            
            # Setup fresh DB for this run to isolate the procedure seeded
            temp_dir = tempfile.mkdtemp()
            db_path = os.path.join(temp_dir, f"graph_{i}.db")
            os.environ["GRAPH_DB_PATH"] = db_path
            
            import agent_service
            store = AgentGraphStore(db_path)
            agent_service.graph_store = store
            
            # Seed procedure
            store.save_artifact("ag_sys", procs[run_info['procedure_id']]["title"], "procedure", json.dumps(procs[run_info['procedure_id']]))
            
            t_data = tasks[run_info['task_id']]
            url = f"data:text/html,{urllib.parse.quote(t_data['html'])}"
            
            use_proc = (run_info['condition'] == "PROCEDURAL")
            
            # Execute
            res = await run_trial(store, t_data['task'], url, use_proc)
            
            # Save results
            record = {
                "run_id": run_info["run_id"],
                "procedure_id": run_info["procedure_id"],
                "task_id": run_info["task_id"],
                "condition": run_info["condition"],
                "rep": run_info["rep"],
                "success": res["success"],
                "tool_call_count": res["tool_call_count"],
                "failed_tool_call_count": res["failed_tool_call_count"],
                "duration": res["duration"],
                "procedure_retrieved": len(res["meta"].get("retrieved_procedure_ids", [])) > 0,
                "procedure_injected": res["meta"].get("procedure_context_injected", False),
                "behavioral_following": res["success"], # Approx, refined in analysis
                "gate_decision": res["meta"].get("procedure_context_injected", False),
                "trace": res["trace"]
            }
            out.write(json.dumps(record) + "\n")
            out.flush()
            
            print(f"  -> Success: {record['success']} | Tools: {record['tool_call_count']} | Duration: {record['duration']:.1f}s")
            
if __name__ == "__main__":
    asyncio.run(main())
