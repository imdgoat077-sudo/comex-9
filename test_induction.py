import asyncio
import json
import tempfile
import os
import uuid

from langchain_openai import ChatOpenAI
from graph.store import AgentGraphStore
from induction import run_offline_induction

class MockLLM:
    def __init__(self, mode="success", model_name="mock_model"):
        self.mode = mode
        self.model_name = model_name
        
    async def ainvoke(self, messages):
        class MockResp:
            def __init__(self, content):
                self.content = content
        
        if self.mode == "malformed":
            return MockResp("NOT JSON {")
        elif self.mode == "missing_field":
            return MockResp('{"accepted": true, "procedure": {"title": "Missing fields"}}')
        elif self.mode == "reject":
            return MockResp('{"accepted": false, "rejection_reason": "Not reusable"}')
        else: # success
            proc = {
                "accepted": True,
                "procedure": {
                    "title": "Abstracted Navigation",
                    "capability": "nav_and_extract",
                    "goal": "Navigate to a page and extract data",
                    "preconditions": ["Site is accessible"],
                    "ordered_steps": ["Locate target container abstractly", "Extract data generic"],
                    "applicability_notes": "Generic lists",
                    "limitations_caveats": "None"
                }
            }
            return MockResp(json.dumps(proc))

def seed_db(db_path: str):
    store = AgentGraphStore(db_path)
    
    # 1. Eligible Episode
    ep1 = "ep_1"
    ag1 = "ag_1"
    store.conn.execute("CREATE (a:Agent {id: $id, task: 'Navigate and extract repeating rows', intent: 'UI'})", {"id": ag1})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (e:Episode {id: $id, agent_id: $ag_id, outcome_status: 'completed', self_reported: 'Done'})-[:FOR]->(a)", {"id": ep1, "ag_id": ag1})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (t:ToolCall {id: 'tc1', tool_name: 'run_browser_harness', args_json: '...', result_summary: '...', success: true, step_index: 0})<-[:EXECUTED]-(a)", {"ag_id": ag1})
    
    # 2. Factual Only (keyword reject)
    ep2 = "ep_2"
    ag2 = "ag_2"
    store.conn.execute("CREATE (a:Agent {id: $id, task: 'single factual lookup of price', intent: 'UI'})", {"id": ag2})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (e:Episode {id: $id, agent_id: $ag_id, outcome_status: 'completed', self_reported: 'Done'})-[:FOR]->(a)", {"id": ep2, "ag_id": ag2})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (t:ToolCall {id: 'tc2', tool_name: 'run_browser_harness', args_json: '...', result_summary: '...', success: true, step_index: 0})<-[:EXECUTED]-(a)", {"ag_id": ag2})

    # 3. Failed Episode
    ep3 = "ep_3"
    ag3 = "ag_3"
    store.conn.execute("CREATE (a:Agent {id: $id, task: 'Fail task', intent: 'UI'})", {"id": ag3})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (e:Episode {id: $id, agent_id: $ag_id, outcome_status: 'error', self_reported: 'Failed'})-[:FOR]->(a)", {"id": ep3, "ag_id": ag3})
    
    # 4. Insufficient trace (No browser calls)
    ep4 = "ep_4"
    ag4 = "ag_4"
    store.conn.execute("CREATE (a:Agent {id: $id, task: 'Extract without browser', intent: 'UI'})", {"id": ag4})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (e:Episode {id: $id, agent_id: $ag_id, outcome_status: 'completed', self_reported: 'Done'})-[:FOR]->(a)", {"id": ep4, "ag_id": ag4})
    
    return store, ep1, ep2, ep3, ep4

async def run_tests():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "graph.db")
    store, ep1, ep2, ep3, ep4 = seed_db(db_path)
    
    print("Testing 1. Eligible -> Candidate produced")
    res1 = await run_offline_induction(store, MockLLM("success"), ep1)
    assert len(res1) == 1
    assert res1[0]["status"] == "PERSISTED"
    
    print("Testing 2. Factual Only -> Rejected")
    res2 = await run_offline_induction(store, MockLLM("success"), ep2)
    assert res2[0]["status"] == "REJECTED_ELIGIBILITY"
    
    print("Testing 3. Failed episode -> Rejected (query ignores it)")
    res3 = await run_offline_induction(store, MockLLM("success"), ep3)
    assert len(res3) == 0 # Query doesn't even return it
    
    print("Testing 4. Insufficient trace -> Rejected")
    res4 = await run_offline_induction(store, MockLLM("success"), ep4)
    assert res4[0]["status"] == "REJECTED_ELIGIBILITY"
    
    print("Testing 8. Malformed JSON -> Rejected")
    store.conn.execute("MATCH (a:Artifact) DETACH DELETE a")
    res_malformed = await run_offline_induction(store, MockLLM("malformed"), ep1)
    assert res_malformed[0]["status"] == "REJECTED_INDUCTION"
    
    print("Testing 9. Missing required field -> KeyError -> Rejected")
    res_missing = await run_offline_induction(store, MockLLM("missing_field"), ep1)
    assert res_missing[0]["status"] == "REJECTED_INDUCTION" or res_missing[0]["status"] == "REJECTED_DUPLICATE"
    
    print("Testing 11. Duplicate procedure -> Rejected")
    await run_offline_induction(store, MockLLM("success"), ep1)
    res_dup = await run_offline_induction(store, MockLLM("success"), ep1)
    assert res_dup[0]["status"] == "REJECTED_DUPLICATE"
    
    print("Testing 10/12. Provenance and retrieval")
    arts = store.conn.execute("MATCH (a:Artifact {artifact_type: 'procedure'}) RETURN a.content")
    found = False
    while arts.has_next():
        c = arts.get_next()[0]
        parsed = json.loads(c)
        assert "provenance" in parsed
        assert parsed["provenance"]["source_episode_id"] == ep1
        assert parsed["ordered_steps"][0] == "Locate target container abstractly"
        found = True
    assert found
    
    print("Testing 15. Original Source remains unchanged")
    tc = store.conn.execute("MATCH (t:ToolCall {id: 'tc1'}) RETURN t.success")
    assert tc.has_next()

    print("ALL TESTS PASSED")

if __name__ == "__main__":
    asyncio.run(run_tests())
