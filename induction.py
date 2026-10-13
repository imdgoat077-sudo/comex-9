import json
import uuid
import logging
from typing import Dict, Any, List
from graph.store import AgentGraphStore
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import os

logger = logging.getLogger(__name__)

# Basic heuristics for eligibility
INELIGIBLE_KEYWORDS = ["one-off", "single factual lookup", "current value", "current price", "just checking", "extract the experiment token"]

def is_eligible(task: str, tool_calls: List[Dict[str, Any]], self_reported: str) -> bool:
    # 1. Reject trivial queries based on keywords (naive heuristic for demo)
    task_lower = task.lower()
    for kw in INELIGIBLE_KEYWORDS:
        if kw in task_lower:
            return False
            
    # 2. Check for sufficient browser trace
    browser_calls = [tc for tc in tool_calls if tc['tool_name'] == 'run_browser_harness' and tc['success']]
    if len(browser_calls) == 0:
        return False # No browser actions, not a browser procedure
        
    # We could require len >= 2 to ensure it's multi-step, but sometimes a complex JS script is a single tool call.
    # We'll allow len >= 1 but the LLM will ultimately decide if it's reusable.
    return True

async def induce_procedure(episode_id: str, agent_id: str, task: str, tool_calls: List[Dict], self_reported: str, llm: ChatOpenAI) -> Dict[str, Any]:
    """Uses LLM to induce a reusable procedure from a concrete trace."""
    
    trace_text = ""
    for tc in tool_calls:
        trace_text += f"\n--- Step {tc['step_index']} ({tc['tool_name']}) ---\n"
        trace_text += f"Args: {tc['args_json']}\n"
        trace_text += f"Result Snippet: {str(tc['result_summary'])[:300]}...\n"

    prompt = f"""You are an expert browser automation procedure extractor.
We have a concrete execution trace of an agent completing a browser task.
Your job is to determine if this represents a reusable procedural workflow (e.g., navigating a specific site's menu, extracting a table, filling a specific form).

If it is merely a one-off factual lookup (e.g. "what is the price of X today" where the method is trivial) or if the trace is insufficient, REJECT it.
If it is a reusable workflow, extract it into an abstract procedure.

Abstract away: concrete URLs if generic, specific item names, exact CSS selectors if they change often, user-specific data.
Preserve: reusable action ordering, structural reasoning, validation steps, important decisions.

Original Task: {task}
Self-Reported Outcome: {self_reported}
Execution Trace:
{trace_text}

Output a RAW JSON object strictly following this schema:
{{
  "accepted": true/false,
  "rejection_reason": "if accepted=false, why?",
  "procedure": {{
    "title": "Short descriptive title",
    "capability": "Short capability key (e.g. extract_list_items, form_submission)",
    "goal": "Abstract goal",
    "preconditions": ["List of preconditions"],
    "ordered_steps": ["Step 1...", "Step 2..."],
    "applicability_notes": "When does this apply?",
    "limitations_caveats": "Any limitations?"
  }}
}}
Do NOT wrap in markdown blocks. Output ONLY valid JSON.
"""
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        content = res.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        logger.error(f"LLM Induction failed or returned invalid JSON: {e}")
        return {"accepted": False, "rejection_reason": f"Malformed JSON: {e}"}

def check_duplicate(graph_store: AgentGraphStore, candidate: Dict[str, Any]) -> bool:
    """Uses existing lexical search to see if we already have this procedure."""
    proc = candidate.get("procedure", {})
    query = f"{proc.get('title', '')} {proc.get('capability', '')} {proc.get('goal', '')}"
    
    # search_procedures uses FTS internally on Artifact content
    results = graph_store.search_procedures(query, limit=3, threshold=0.3)
    
    for r in results:
        try:
            stored_proc = json.loads(r.get("content", "{}"))
            if stored_proc.get("capability") == proc.get("capability"):
                return True
        except:
            pass
    return False

async def run_offline_induction(graph_store: AgentGraphStore, llm: ChatOpenAI, target_episode_id: str = None) -> Dict:
    """Run induction over eligible episodes."""
    results = []
    
    # 1. Fetch episodes
    query = """
    MATCH (e:Episode)-[:FOR]->(a:Agent)
    WHERE e.outcome_status = 'completed'
    """
    if target_episode_id:
        query += f" AND e.id = '{target_episode_id}'"
    query += " RETURN e.id, a.id, a.task, e.self_reported"
    
    res = graph_store.conn.execute(query)
    episodes = []
    while res.has_next():
        row = res.get_next()
        episodes.append({
            "episode_id": row[0],
            "agent_id": row[1],
            "task": row[2],
            "self_reported": row[3]
        })
        
    for ep in episodes:
        # Fetch trace
        tc_query = """
        MATCH (a:Agent {id: $ag_id})-[:EXECUTED]->(t:ToolCall)
        RETURN t.tool_name, t.args_json, t.result_summary, t.success, t.step_index
        ORDER BY t.step_index
        """
        tc_res = graph_store.conn.execute(tc_query, {"ag_id": ep["agent_id"]})
        tool_calls = []
        while tc_res.has_next():
            row = tc_res.get_next()
            tool_calls.append({
                "tool_name": row[0],
                "args_json": row[1],
                "result_summary": row[2],
                "success": row[3],
                "step_index": row[4]
            })
            
        # 2. Eligibility
        if not is_eligible(ep["task"], tool_calls, ep["self_reported"]):
            results.append({"episode_id": ep["episode_id"], "status": "REJECTED_ELIGIBILITY"})
            continue
            
        # 3. Induction
        induction_result = await induce_procedure(ep["episode_id"], ep["agent_id"], ep["task"], tool_calls, ep["self_reported"], llm)
        
        if not induction_result.get("accepted"):
            results.append({"episode_id": ep["episode_id"], "status": "REJECTED_INDUCTION", "reason": induction_result.get("rejection_reason")})
            continue
            
        # 4. Deduplication
        if check_duplicate(graph_store, induction_result):
            results.append({"episode_id": ep["episode_id"], "status": "REJECTED_DUPLICATE"})
            continue
            
        # 5. Persistence
        # Store as Artifact. We embed the procedure and provenance in the JSON string.
        proc = induction_result["procedure"]
        
        required_fields = ["title", "capability", "goal", "preconditions", "ordered_steps", "applicability_notes", "limitations_caveats"]
        missing = [f for f in required_fields if f not in proc]
        if missing:
            results.append({"episode_id": ep["episode_id"], "status": "REJECTED_INDUCTION", "reason": f"Missing required fields: {missing}"})
            continue
            
        prov_content = {
            "title": proc["title"],
            "capability": proc["capability"],
            "goal": proc["goal"],
            "preconditions": proc.get("preconditions", []),
            "ordered_steps": proc.get("ordered_steps", []),
            "applicability_notes": proc.get("applicability_notes", ""),
            "limitations_caveats": proc.get("limitations_caveats", ""),
            "provenance": {
                "source_episode_id": ep["episode_id"],
                "source_agent_id": ep["agent_id"],
                "original_task": ep["task"],
                "induction_model": llm.model_name
            }
        }
        
        artifact_id = graph_store.save_artifact(
            agent_id=ep["agent_id"],
            title=proc["title"],
            artifact_type="procedure",
            content=json.dumps(prov_content)
        )
        
        results.append({
            "episode_id": ep["episode_id"], 
            "status": "PERSISTED", 
            "artifact_id": artifact_id,
            "procedure": prov_content
        })
        
    return results
