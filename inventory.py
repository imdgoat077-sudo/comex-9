import kuzu
import os
import json

db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

print("=== AGENTS ===")
res = conn.execute("MATCH (a:Agent) RETURN a.id, a.task, a.intent, a.created_at ORDER BY a.created_at ASC")
while res.has_next():
    row = res.get_next()
    print(f"Agent ID: {row[0]}")
    print(f"  Task: {row[1]}")
    print(f"  Intent: {row[2]}")
    print(f"  Created At: {row[3]}")
    print()

print("=== EPISODES ===")
res = conn.execute("MATCH (e:Episode) RETURN e.id, e.outcome_status, e.self_reported, e.created_at ORDER BY e.created_at ASC")
while res.has_next():
    row = res.get_next()
    print(f"Episode ID: {row[0]}")
    print(f"  Outcome: {row[1]}")
    print(f"  Created At: {row[3]}")
    sr = str(row[2])
    print(f"  Self-reported: {sr[:100]}..." if len(sr) > 100 else f"  Self-reported: {sr}")
    print()

print("=== EPISODE -> AGENT FOR RELATIONSHIPS ===")
res = conn.execute("MATCH (e:Episode)-[r:FOR]->(a:Agent) RETURN e.id, a.id ORDER BY e.created_at ASC")
while res.has_next():
    row = res.get_next()
    print(f"Episode: {row[0]} -[FOR]-> Agent: {row[1]}")
print()

print("=== AGENT -> TOOLCALL TRACES ===")
res = conn.execute("MATCH (a:Agent)-[r:EXECUTED]->(t:ToolCall) RETURN a.id, t.id, t.tool_name, t.success, t.step_index ORDER BY a.created_at ASC, t.step_index ASC")
while res.has_next():
    row = res.get_next()
    print(f"Agent: {row[0]} -[EXECUTED]-> ToolCall: {row[1]} (name={row[2]}, success={row[3]}, step={row[4]})")
print()

print("=== COUNTS ===")
agent_count = conn.execute("MATCH (a:Agent) RETURN count(a)").get_next()[0]
episode_count = conn.execute("MATCH (e:Episode) RETURN count(e)").get_next()[0]
for_count = conn.execute("MATCH (e:Episode)-[r:FOR]->(a:Agent) RETURN count(r)").get_next()[0]
toolcall_count = conn.execute("MATCH (t:ToolCall) RETURN count(t)").get_next()[0]
print(f"Agents: {agent_count}")
print(f"Episodes: {episode_count}")
print(f"FOR relationships: {for_count}")
print(f"ToolCalls: {toolcall_count}")
