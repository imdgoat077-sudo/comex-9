import kuzu
import os
import json

db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

with open("/Users/pranavkumarn/.gemini/antigravity-cli/brain/0a10a024-ca33-4b35-acbb-3a40372c98d1/analysis_dump.json", "w") as f:
    data = {"agents": [], "legacy_episodes": []}
    
    # Get all episodes mapped to agents (the 13 valid ones)
    res = conn.execute("""
        MATCH (a:Agent)<-[r:FOR]-(e:Episode)
        RETURN a.id, a.task, a.intent, a.created_at, e.id, e.outcome_status, e.self_reported, e.created_at
        ORDER BY a.created_at ASC
    """)
    
    agents = {}
    while res.has_next():
        row = res.get_next()
        a_id = row[0]
        agents[a_id] = {
            "agent_id": a_id,
            "task": row[1],
            "intent": row[2],
            "agent_created_at": str(row[3]),
            "episode_id": row[4],
            "outcome_status": row[5],
            "self_reported": row[6],
            "episode_created_at": str(row[7]),
            "tool_calls": []
        }
        
    # Get tool calls for these agents
    res = conn.execute("""
        MATCH (a:Agent)-[r:EXECUTED]->(t:ToolCall)
        RETURN a.id, t.id, t.tool_name, t.success, t.step_index, t.args_json, t.result_summary
        ORDER BY t.step_index ASC
    """)
    while res.has_next():
        row = res.get_next()
        a_id = row[0]
        if a_id in agents:
            agents[a_id]["tool_calls"].append({
                "id": row[1],
                "tool_name": row[2],
                "success": row[3],
                "step_index": row[4],
                "args_json": row[5],
                "result_summary": row[6]
            })
            
    data["agents"] = list(agents.values())
    
    # Get legacy episodes
    res = conn.execute("""
        MATCH (e:Episode)
        WHERE NOT EXISTS { MATCH (e)-[:FOR]->(:Agent) }
        RETURN e.id, e.outcome_status, e.created_at
    """)
    while res.has_next():
        row = res.get_next()
        data["legacy_episodes"].append({
            "id": row[0],
            "outcome_status": row[1],
            "created_at": str(row[2])
        })
        
    json.dump(data, f, indent=2)
