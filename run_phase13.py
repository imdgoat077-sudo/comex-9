import asyncio
import json
import tempfile
import os

from langchain_openai import ChatOpenAI
from graph.store import AgentGraphStore
from induction import run_offline_induction

def seed_controlled_dataset(db_path: str):
    store = AgentGraphStore(db_path)
    
    # 1. Multi-step Form (Reusable & Complete)
    ep1 = "ep_multi_form"
    ag1 = "ag_multi_form"
    store.conn.execute("CREATE (a:Agent {id: $id, task: 'Login to demo site, go to cart, and complete checkout', intent: 'UI'})", {"id": ag1})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (e:Episode {id: $id, agent_id: $ag_id, outcome_status: 'completed', self_reported: 'Checkout complete'})-[:FOR]->(a)", {"id": ep1, "ag_id": ag1})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (t:ToolCall {id: 'tc1a', tool_name: 'run_browser_harness', args_json: 'fill username \"bob\", fill pass \"123\", click #login', result_summary: 'Logged in successfully', success: true, step_index: 0})<-[:EXECUTED]-(a)", {"ag_id": ag1})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (t:ToolCall {id: 'tc1b', tool_name: 'run_browser_harness', args_json: 'click .cart-icon, click .checkout', result_summary: 'On checkout billing page', success: true, step_index: 1})<-[:EXECUTED]-(a)", {"ag_id": ag1})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (t:ToolCall {id: 'tc1c', tool_name: 'run_browser_harness', args_json: 'fill address \"123 Fake St\", fill card \"4444\", click .submit-order', result_summary: 'Order confirmed: #99281', success: true, step_index: 2})<-[:EXECUTED]-(a)", {"ag_id": ag1})
    
    # 3. Ineligible: Current Value Lookup
    ep3 = "ep_value_lookup"
    ag3 = "ag_value_lookup"
    store.conn.execute("CREATE (a:Agent {id: $id, task: 'What is the current price of Bitcoin on coinmarketcap?', intent: 'UI'})", {"id": ag3})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (e:Episode {id: $id, agent_id: $ag_id, outcome_status: 'completed', self_reported: 'Bitcoin is $60k'})-[:FOR]->(a)", {"id": ep3, "ag_id": ag3})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (t:ToolCall {id: 'tc3', tool_name: 'run_browser_harness', args_json: 'read text', result_summary: 'Bitcoin is $60k', success: true, step_index: 0})<-[:EXECUTED]-(a)", {"ag_id": ag3})
    
    # 4. Ineligible: Failed Episode
    ep4 = "ep_fail"
    ag4 = "ag_fail"
    store.conn.execute("CREATE (a:Agent {id: $id, task: 'Extract list', intent: 'UI'})", {"id": ag4})
    store.conn.execute("MATCH (a:Agent {id: $ag_id}) CREATE (e:Episode {id: $id, agent_id: $ag_id, outcome_status: 'error', self_reported: 'Failed to extract'})-[:FOR]->(a)", {"id": ep4, "ag_id": ag4})
    
    return store

async def main():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "graph.db")
    store = seed_controlled_dataset(db_path)
    
    from agent_service import MODEL_NAME, OPENAI_BASE_URL, ROUTER_API_KEY
    llm = ChatOpenAI(
        model=MODEL_NAME,
        base_url=OPENAI_BASE_URL,
        api_key=ROUTER_API_KEY,
    )
    
    print("Running explicit offline procedure induction on dataset...")
    results = await run_offline_induction(store, llm)
    
    for r in results:
        print("\n" + "="*50)
        print(f"Episode: {r['episode_id']} -> Status: {r['status']}")
        if r['status'] == "PERSISTED":
            print("Inducted Procedure:")
            print(json.dumps(r['procedure'], indent=2))
        elif r['status'] == "REJECTED_INDUCTION":
            print("Reason:", r.get('reason'))
        
if __name__ == "__main__":
    asyncio.run(main())
