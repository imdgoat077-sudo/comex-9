import kuzu
import os
import json

db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

with open("/Users/pranavkumarn/.gemini/antigravity-cli/brain/0a10a024-ca33-4b35-acbb-3a40372c98d1/real_task_inventory.md", "w") as f:
    f.write("# Real Task Graph Database Inventory\n\n")

    f.write("## === AGENTS ===\n")
    res = conn.execute("MATCH (a:Agent) RETURN a.id, a.task, a.intent, a.created_at ORDER BY a.created_at ASC")
    while res.has_next():
        row = res.get_next()
        f.write(f"- **Agent ID:** {row[0]}\n")
        f.write(f"  - **Task:** {row[1]}\n")
        f.write(f"  - **Intent:** {row[2]}\n")
        f.write(f"  - **Created At:** {row[3]}\n\n")

    f.write("## === EPISODES ===\n")
    res = conn.execute("MATCH (e:Episode) RETURN e.id, e.outcome_status, e.self_reported, e.created_at ORDER BY e.created_at ASC")
    while res.has_next():
        row = res.get_next()
        f.write(f"- **Episode ID:** {row[0]}\n")
        f.write(f"  - **Outcome:** {row[1]}\n")
        f.write(f"  - **Created At:** {row[3]}\n")
        sr = str(row[2])
        sr_snippet = sr[:150].replace('\n', ' ') + "..." if len(sr) > 150 else sr.replace('\n', ' ')
        f.write(f"  - **Self-reported:** {sr_snippet}\n\n")

    f.write("## === EPISODE -> AGENT FOR RELATIONSHIPS ===\n")
    res = conn.execute("MATCH (e:Episode)-[r:FOR]->(a:Agent) RETURN e.id, a.id ORDER BY e.created_at ASC")
    while res.has_next():
        row = res.get_next()
        f.write(f"- `{row[0]}` -[FOR]-> `{row[1]}`\n")
    f.write("\n")

    f.write("## === AGENT -> TOOLCALL TRACES ===\n")
    res = conn.execute("MATCH (a:Agent)-[r:EXECUTED]->(t:ToolCall) RETURN a.id, t.id, t.tool_name, t.success, t.step_index ORDER BY a.created_at ASC, t.step_index ASC")
    current_agent = ""
    while res.has_next():
        row = res.get_next()
        agent_id = row[0]
        if agent_id != current_agent:
            if current_agent != "":
                f.write("\n")
            f.write(f"**Agent:** `{agent_id}`\n")
            current_agent = agent_id
        f.write(f"- `[Step {row[4]}]` -[EXECUTED]-> ToolCall: `{row[1]}` (name={row[2]}, success={row[3]})\n")
    f.write("\n")

    f.write("## === COUNTS ===\n")
    agent_count = conn.execute("MATCH (a:Agent) RETURN count(a)").get_next()[0]
    episode_count = conn.execute("MATCH (e:Episode) RETURN count(e)").get_next()[0]
    for_count = conn.execute("MATCH (e:Episode)-[r:FOR]->(a:Agent) RETURN count(r)").get_next()[0]
    toolcall_count = conn.execute("MATCH (t:ToolCall) RETURN count(t)").get_next()[0]
    f.write(f"- Agents: {agent_count}\n")
    f.write(f"- Episodes: {episode_count}\n")
    f.write(f"- FOR relationships: {for_count}\n")
    f.write(f"- ToolCalls: {toolcall_count}\n")
