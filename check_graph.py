import kuzu
import os
import json

db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

res = conn.execute("MATCH (a:Agent) RETURN count(a)").get_next()
agent_count = res[0]

res = conn.execute("MATCH (e:Episode) RETURN count(e)").get_next()
episode_count = res[0]

res = conn.execute("MATCH (e:Episode)-[r:FOR]->(a:Agent) RETURN count(r)").get_next()
for_count = res[0]

print(f"Agent count: {agent_count}")
print(f"Episode count: {episode_count}")
print(f"FOR relationship count: {for_count}")

# Get the newly created Agent (the only one)
res = conn.execute("MATCH (a:Agent) RETURN a.id, a.task, a.intent")
if res.has_next():
    agent_row = res.get_next()
    print(f"\nAgent:")
    print(f"  ID: {agent_row[0]}")
    print(f"  Task: {agent_row[1]}")
    print(f"  Intent: {agent_row[2]}")
    new_agent_id = agent_row[0]
else:
    print("\nNo Agent found!")

# Get the newly created Episode (the one pointing to this Agent, or the 9th episode)
res = conn.execute("MATCH (e:Episode) WHERE e.agent_id = $aid RETURN e.id, e.outcome_status, e.self_reported, e.created_at", {"aid": new_agent_id})
if res.has_next():
    ep_row = res.get_next()
    print(f"\nEpisode:")
    print(f"  ID: {ep_row[0]}")
    print(f"  Agent ID (Foreign Key): {new_agent_id}")
    print(f"  Outcome Status: {ep_row[1]}")
    print(f"  Created At: {ep_row[3]}")
    
    sr = ep_row[2]
    sr_len = len(sr)
    print(f"  Self-reported Length: {sr_len}")
    if sr_len < 1000:
        print(f"  Self-reported snippet:\n{sr[:200]}...")
    
    # Check relationship
    res = conn.execute("MATCH (e:Episode {id: $eid})-[r:FOR]->(a:Agent {id: $aid}) RETURN count(r)", {"eid": ep_row[0], "aid": new_agent_id}).get_next()
    print(f"  [:FOR] relationship exists: {res[0] > 0}")
else:
    print(f"\nNo Episode found for Agent {new_agent_id}!")

# Inspect ToolCall/Page/Entity records
res = conn.execute("MATCH (t:ToolCall) RETURN count(t)").get_next()
print(f"\nToolCall count: {res[0]}")

res = conn.execute("MATCH (p:Page) RETURN count(p)").get_next()
print(f"Page count: {res[0]}")

res = conn.execute("MATCH (e:Entity) RETURN count(e)").get_next()
print(f"Entity count: {res[0]}")

print(f"\nDB Path: {db_path}")
