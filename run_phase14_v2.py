import asyncio
import json
import tempfile
import os
import urllib.parse
import time

from langchain_openai import ChatOpenAI
from graph.store import AgentGraphStore
from agent_service import execute_agent_loop, MODEL_NAME, OPENAI_BASE_URL, ROUTER_API_KEY
from validation_and_refinement import evaluate_transfer

async def run_trial(graph_store: AgentGraphStore, task: str, target_url: str, use_procedures: bool) -> dict:
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
    
    # Simple success detection based on our mock HTML triggers
    success = "SUCCESS_" in res or "Extracted" in res or "Checkout complete" in res
    if not success and any(t["success"] for t in meta.get("tool_traces", [])):
        # Inspect trace for explicit SUCCESS text appended to DOM
        for t in meta.get("tool_traces", []):
            if t["success"] and "SUCCESS_" in str(t.get("result_summary", "")):
                success = True
                break

    trace_text = ""
    for tc in meta.get("tool_traces", []):
        trace_text += f"[{tc['tool']}] Args: {tc['args']} -> Success: {tc['success']}\n"
        trace_text += f"Snippet: {str(tc.get('result_summary', ''))[:150]}...\n"
        
    return {
        "success": success,
        "trace": trace_text,
        "raw_res": res,
        "meta": meta,
        "duration": duration
    }

async def main():
    print("="*50)
    print("PHASE 14 V2 VALIDATION EXPERIMENT")
    print("="*50)
    
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "graph.db")
    os.environ["GRAPH_DB_PATH"] = db_path
    
    import agent_service
    store = AgentGraphStore(db_path)
    agent_service.graph_store = store
    
    # =========================================================================
    # Procedure A: Modal Overlay Bypass
    # =========================================================================
    proc_a = {
        "title": "Bypass Blocking Overlays",
        "capability": "ui_overlay_bypass",
        "goal": "Interact with underlying elements when a modal/overlay blocks clicks",
        "preconditions": [],
        "ordered_steps": [
            "Check if an overlay (e.g., cookie banner, promotional modal) is intercepting clicks.",
            "Locate the dismiss/close button inside the overlay.",
            "Click the dismiss button to remove the overlay.",
            "Proceed with interacting with the target elements."
        ],
        "applicability_notes": "Use when standard clicks fail due to obscuring elements or z-index issues.",
        "limitations_caveats": "",
        "provenance": {"source_episode_id": "ep_src_a"}
    }
    id_a = store.save_artifact("ag_sys", "Overlay Bypass", "procedure", json.dumps(proc_a))
    
    html_a = """<html><body>
    <div id="overlay" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:999;">
        <button id="close-btn" onclick="document.getElementById('overlay').style.display='none'">Close</button>
    </div>
    <button id="target-btn" onclick="document.body.innerHTML+='SUCCESS_A'">Click Target</button>
    </body></html>"""
    url_a = f"data:text/html,{urllib.parse.quote(html_a)}"
    task_a = "Click the target button. Ensure the click registers and produces SUCCESS_A."

    # =========================================================================
    # Procedure B: Inner Container Scroll
    # =========================================================================
    proc_b = {
        "title": "Inner Container Infinite Scroll",
        "capability": "ui_inner_scroll",
        "goal": "Trigger infinite scroll when window scrolling fails",
        "preconditions": [],
        "ordered_steps": [
            "Identify if window scrolling fails to load new records.",
            "Locate the specific inner container wrapping the list (often has overflow-y: scroll or auto).",
            "Execute scroll events directly on this inner container.",
            "Wait for DOM changes and extract the newly loaded items."
        ],
        "applicability_notes": "Use for isolated scroll panes like sidebars or specific result wrappers.",
        "limitations_caveats": "",
        "provenance": {"source_episode_id": "ep_src_b"}
    }
    id_b = store.save_artifact("ag_sys", "Inner Scroll", "procedure", json.dumps(proc_b))
    
    html_b = """<html><body>
    <div id="inner-scroll" style="height:50px;overflow-y:auto;" onscroll="if(this.scrollTop>0) { document.body.innerHTML+='SUCCESS_B'; }">
        <div class="item">Item 1</div>
        <div class="item" style="height:100px;">Item 2</div>
    </div>
    </body></html>"""
    url_b = f"data:text/html,{urllib.parse.quote(html_b)}"
    task_b = "Scroll down to load the next items and produce SUCCESS_B."

    # =========================================================================
    # Procedure C: Hover-to-Reveal
    # =========================================================================
    proc_c = {
        "title": "Hover Reveal Navigation",
        "capability": "ui_hover_reveal",
        "goal": "Access hidden submenu items in a navigation bar",
        "preconditions": [],
        "ordered_steps": [
            "Identify the parent navigation menu item.",
            "Dispatch a hover/mouseenter event to reveal the flyout menu.",
            "Wait for the submenu to become visible in the DOM.",
            "Click the target submenu link."
        ],
        "applicability_notes": "Use when links exist in the DOM but are display:none until hovered.",
        "limitations_caveats": "",
        "provenance": {"source_episode_id": "ep_src_c"}
    }
    id_c = store.save_artifact("ag_sys", "Hover Reveal", "procedure", json.dumps(proc_c))
    
    html_c = """<html><body>
    <div id="nav" onmouseover="document.getElementById('menu').style.display='block'">Hover Me</div>
    <div id="menu" style="display:none;">
        <button id="target-btn" onclick="document.body.innerHTML+='SUCCESS_C'">Click Submenu</button>
    </div>
    </body></html>"""
    url_c = f"data:text/html,{urllib.parse.quote(html_c)}"
    task_c = "Click the target submenu button located inside the navigation menu to produce SUCCESS_C."

    experiments = [
        ("Task A (Overlay)", task_a, url_a, proc_a),
        ("Task B (Inner Scroll)", task_b, url_b, proc_b),
        ("Task C (Hover Reveal)", task_c, url_c, proc_c)
    ]
    
    llm = ChatOpenAI(model=MODEL_NAME, base_url=OPENAI_BASE_URL, api_key=ROUTER_API_KEY)
    results = []

    for name, task, url, proc in experiments:
        print(f"\n{'='*60}\nRunning {name}\n{'='*60}")
        
        # Baseline
        print("[*] Running BASELINE...")
        base = await run_trial(store, task, url, use_procedures=False)
        print(f"  -> Success: {base['success']}, Duration: {base['duration']:.1f}s, Tools: {base['meta'].get('tool_call_count')}")
        
        # Procedural
        print("[*] Running PROCEDURAL...")
        proc_run = await run_trial(store, task, url, use_procedures=True)
        gate_decision = proc_run['meta'].get('procedure_context_injected', False)
        print(f"  -> Retrieved: {len(proc_run['meta'].get('retrieved_procedure_ids', []))} candidates")
        print(f"  -> Gated IN: {gate_decision}")
        print(f"  -> Success: {proc_run['success']}, Duration: {proc_run['duration']:.1f}s, Tools: {proc_run['meta'].get('tool_call_count')}")
        
        # Evaluation
        eval_result = await evaluate_transfer(
            task=task,
            baseline_trace=base['trace'],
            baseline_success=base['success'],
            procedural_trace=proc_run['trace'],
            procedural_success=proc_run['success'],
            retrieved_procedure=proc,
            llm=llm
        )
        print(f"\n[EVALUATION OUTCOME]: {eval_result['classification']}")
        print(f"[REASONING]: {eval_result['reasoning']}")
        
        results.append({
            "name": name,
            "baseline": base,
            "procedural": proc_run,
            "evaluation": eval_result
        })

    with open("phase14_v2_results.json", "w") as f:
        # We strip large meta objects for the JSON dump
        stripped_results = []
        for r in results:
            stripped_results.append({
                "name": r["name"],
                "baseline_success": r["baseline"]["success"],
                "baseline_tools": r["baseline"]["meta"].get("tool_call_count"),
                "baseline_duration": r["baseline"]["duration"],
                "procedural_success": r["procedural"]["success"],
                "procedural_tools": r["procedural"]["meta"].get("tool_call_count"),
                "procedural_duration": r["procedural"]["duration"],
                "procedural_retrieved": len(r["procedural"]["meta"].get("retrieved_procedure_ids", [])),
                "procedural_injected": r["procedural"]["meta"].get("procedure_context_injected"),
                "classification": r["evaluation"].get("classification"),
                "reasoning": r["evaluation"].get("reasoning")
            })
        json.dump(stripped_results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
