import json
import logging
from typing import Dict, Any, List
from graph.store import AgentGraphStore
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

async def evaluate_transfer(
    task: str,
    baseline_trace: str,
    baseline_success: bool,
    procedural_trace: str,
    procedural_success: bool,
    retrieved_procedure: Dict[str, Any],
    llm: ChatOpenAI
) -> Dict[str, Any]:
    """
    Evaluates whether the retrieved procedure was helpful, harmful, neutral, ignored, or irrelevant.
    Outputs a strict JSON classification.
    """
    prompt = f"""You are an expert evaluator analyzing the transfer of an induced browser automation procedure to a new unseen task.

Procedure Retrieved:
{json.dumps(retrieved_procedure, indent=2)}

Validation Task: {task}

BASELINE CONDITION (No Procedure):
Success: {baseline_success}
Trace:
{baseline_trace}

PROCEDURAL CONDITION (Procedure Available):
Success: {procedural_success}
Trace:
{procedural_trace}

Classify the transfer outcome into EXACTLY ONE of the following categories:
- Helpful: Procedure was relevant, followed, and clearly contributed to success or improved efficiency.
- Neutral: Procedure was followed or available, but outcome/efficiency was unchanged vs baseline.
- Harmful: Procedure was followed but caused a regression, loop, or failure.
- Ignored: Procedure was available but the agent's behavior shows it did not materially follow it.
- Irrelevant: The procedure retrieved does not actually match the validation task.

If it was Harmful or Ignored due to the procedure being incomplete, brittle, or containing source-specific assumptions (like a hardcoded selector that doesn't exist on the new site), explain why and propose a refinement.

Output a RAW JSON object strictly following this schema:
{{
  "classification": "Helpful" | "Neutral" | "Harmful" | "Ignored" | "Irrelevant",
  "reasoning": "Detailed justification citing trace evidence",
  "needs_refinement": true/false,
  "refinement_rationale": "If true, why?",
  "refined_procedure_candidate": {{
     "title": "...",
     "capability": "...",
     "goal": "...",
     "preconditions": [...],
     "ordered_steps": [...],
     "applicability_notes": "...",
     "limitations_caveats": "..."
  }} // Only include this object if needs_refinement is true
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
        logger.error(f"Transfer evaluation failed or returned invalid JSON: {e}")
        return {"classification": "Invalid", "reasoning": f"Malformed JSON: {e}", "needs_refinement": False}

def refine_procedure(
    graph_store: AgentGraphStore,
    evaluation: Dict[str, Any],
    original_procedure_id: str,
    original_procedure: Dict[str, Any],
    validation_episode_id: str,
    model_name: str
) -> str:
    """
    Safely persists a refined procedure as a NEW Artifact (v2).
    Leaves the original intact.
    """
    if not evaluation.get("needs_refinement") or "refined_procedure_candidate" not in evaluation:
        return ""
        
    candidate = evaluation["refined_procedure_candidate"]
    
    # Strict validation of required fields
    required_fields = ["title", "capability", "goal", "preconditions", "ordered_steps", "applicability_notes", "limitations_caveats"]
    missing = [f for f in required_fields if f not in candidate]
    if missing:
        logger.warning(f"Refinement candidate missing fields: {missing}. Aborting refinement.")
        return ""
        
    prov_content = {
        "title": candidate["title"],
        "capability": candidate["capability"],
        "goal": candidate["goal"],
        "preconditions": candidate.get("preconditions", []),
        "ordered_steps": candidate.get("ordered_steps", []),
        "applicability_notes": candidate.get("applicability_notes", ""),
        "limitations_caveats": candidate.get("limitations_caveats", ""),
        "provenance": {
            "refined_from_procedure_id": original_procedure_id,
            "validation_episode_id": validation_episode_id,
            "refinement_rationale": evaluation.get("refinement_rationale", ""),
            "induction_model": model_name,
            # Inherit original provenance if available
            "original_source_episode_id": original_procedure.get("provenance", {}).get("source_episode_id", "")
        }
    }
    
    # Save as a new artifact. We link it to a dummy agent or leave agent_id empty if allowed, 
    # but the API requires agent_id. We'll use a system agent ID.
    system_agent_id = f"ag_sys_refiner_{validation_episode_id}"
    graph_store.conn.execute("MERGE (a:Agent {id: $id}) ON CREATE SET a.task = 'Refinement System', a.intent = 'SYSTEM'", {"id": system_agent_id})
    
    artifact_id = graph_store.save_artifact(
        agent_id=system_agent_id,
        title=f"[Refined] {candidate['title']}",
        artifact_type="procedure",
        content=json.dumps(prov_content)
    )
    
    return artifact_id
