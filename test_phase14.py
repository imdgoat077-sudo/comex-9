import asyncio
import json
import tempfile
import os

from langchain_openai import ChatOpenAI
from graph.store import AgentGraphStore
from validation_and_refinement import evaluate_transfer, refine_procedure

class MockEvalLLM:
    def __init__(self, mode="helpful", missing_field=False):
        self.mode = mode
        self.missing_field = missing_field
        
    async def ainvoke(self, messages):
        class MockResp:
            def __init__(self, content):
                self.content = content
        
        if self.mode == "malformed":
            return MockResp("NOT JSON {")
            
        base_resp = {
            "classification": self.mode.capitalize(),
            "reasoning": f"Because {self.mode}",
            "needs_refinement": self.mode in ["harmful", "ignored"]
        }
        
        if base_resp["needs_refinement"]:
            base_resp["refinement_rationale"] = "Needs more abstraction"
            cand = {
                "title": "Refined v2",
                "capability": "test_cap",
                "goal": "do better",
                "preconditions": [],
                "ordered_steps": ["step 1"],
                "applicability_notes": "",
                "limitations_caveats": ""
            }
            if self.missing_field:
                del cand["capability"]
            base_resp["refined_procedure_candidate"] = cand
            
        return MockResp(json.dumps(base_resp))

def setup_db(db_path: str):
    return AgentGraphStore(db_path)

async def run_tests():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "graph.db")
    store = setup_db(db_path)
    
    # Fake original procedure
    orig_proc = {
        "title": "v1", "capability": "test_cap", "goal": "v1 goal",
        "provenance": {"source_episode_id": "ep_orig"}
    }
    orig_id = store.save_artifact("ag_dummy", "v1", "procedure", json.dumps(orig_proc))
    
    print("Testing 1-11: Classifications and Refinement Generation")
    
    # 1. Helpful
    res_helpful = await evaluate_transfer("Task", "B", False, "P", True, orig_proc, MockEvalLLM("helpful"))
    assert res_helpful["classification"] == "Helpful"
    assert not refine_procedure(store, res_helpful, orig_id, orig_proc, "ep_val", "mock_model")
    
    # 2. Neutral
    res_neutral = await evaluate_transfer("Task", "B", True, "P", True, orig_proc, MockEvalLLM("neutral"))
    assert res_neutral["classification"] == "Neutral"
    
    # 3. Harmful -> Triggers Refinement
    res_harmful = await evaluate_transfer("Task", "B", True, "P", False, orig_proc, MockEvalLLM("harmful"))
    assert res_harmful["classification"] == "Harmful"
    assert res_harmful["needs_refinement"]
    
    # Save refinement
    ref_id = refine_procedure(store, res_harmful, orig_id, orig_proc, "ep_val_harm", "mock_model")
    assert ref_id != ""
    assert ref_id != orig_id # Requirement 14: preserves original
    
    # Verify provenance (Req 15)
    arts = store.conn.execute("MATCH (a:Artifact {id: $id}) RETURN a.content", {"id": ref_id}).get_next()[0]
    parsed_art = json.loads(arts)
    assert parsed_art["provenance"]["refined_from_procedure_id"] == orig_id
    assert parsed_art["provenance"]["original_source_episode_id"] == "ep_orig"
    assert parsed_art["provenance"]["validation_episode_id"] == "ep_val_harm"
    
    print("Testing 16: Malformed/Missing fields rejected")
    res_malformed = await evaluate_transfer("T", "B", True, "P", False, orig_proc, MockEvalLLM("malformed"))
    assert res_malformed["classification"] == "Invalid"
    
    res_missing = await evaluate_transfer("T", "B", True, "P", False, orig_proc, MockEvalLLM("harmful", missing_field=True))
    ref_id2 = refine_procedure(store, res_missing, orig_id, orig_proc, "ep_val2", "mock_model")
    assert ref_id2 == "" # Rejected
    
    print("ALL TESTS PASSED")

if __name__ == "__main__":
    asyncio.run(run_tests())
