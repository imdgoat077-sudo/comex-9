import asyncio
import os
import json

# Setup isolated temp DB
import tempfile
temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, "graph.db")
os.environ["GRAPH_DB_PATH"] = db_path

# Seed the DB so it actually retrieves something
from graph.store import AgentGraphStore
store = AgentGraphStore(db_path)
store.conn.execute("""
    CREATE (a:Artifact {
        id: 'test-proc', 
        artifact_type: 'procedure', 
        title: 'Procedural Candidate: Form Submission', 
        content: 'Goal: Click a link.\\nProcedure: Click it.', 
        created_at: timestamp('2026-01-01 00:00:00'), 
        source_agent_id: 'seed'
    })
""")
del store

from agent_service import execute_agent_loop

async def main():
    print("Testing GATED_PROCEDURAL directly with seeded DB...")
    res, meta = await execute_agent_loop(
        task="Go to https://the-internet.herokuapp.com/login and login",
        default_cdp_url="ws://127.0.0.1:9222/devtools/browser/xyz",
        intent="VISIBLE_BROWSER_TASK",
        use_procedures=True,
        procedure_mode="gated"
    )
    print("Gate Reason:", meta.get("gate_reason"))
    print("Gate Exception:", meta.get("gate_exception", "Unknown"))

asyncio.run(main())
