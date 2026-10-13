import asyncio
import os

import tempfile
temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, "graph.db")
os.environ["GRAPH_DB_PATH"] = db_path

from graph.store import AgentGraphStore
store = AgentGraphStore(db_path)
store.conn.execute("""
    CREATE (a:Artifact {
        id: 'test-proc', 
        artifact_type: 'procedure', 
        capability: 'click_detail_and_extract',
        title: 'Procedural Candidate: Click Detail', 
        content: 'Goal: Click a link.\\nProcedure: Click it.', 
        created_at: timestamp('2026-01-01 00:00:00'), 
        source_agent_id: 'seed'
    })
""")
del store

from agent_service import execute_agent_loop

async def main():
    print("Testing GATED_PROCEDURAL T10...")
    res, meta = await execute_agent_loop(
        task="Go to https://petstore.octoperf.com/actions/Catalog.action, click the link for 'Reptiles', and extract the first product ID.",
        default_cdp_url="ws://127.0.0.1:9222/devtools/browser/xyz",
        intent="VISIBLE_BROWSER_TASK",
        use_procedures=True,
        procedure_mode="gated"
    )
    print("Retrieved Procedure IDs:", meta.get("retrieved_procedure_ids"))
    print("Gate Reason:", meta.get("gate_reason"))
    print("Gate Exception:", meta.get("gate_exception", "No exception logged"))

asyncio.run(main())
