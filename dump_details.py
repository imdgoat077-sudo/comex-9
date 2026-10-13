import kuzu
import os

db_path = os.path.expanduser("~/.comex/graph.db")
conn = kuzu.Connection(kuzu.Database(db_path))

res = conn.execute("MATCH (a:Agent) RETURN a.id, a.task ORDER BY a.created_at DESC LIMIT 6")
agents = []
while res.has_next():
    agents.append(res.get_next())

agents = list(reversed(agents))

with open("efficacy_experiment_details.txt", "w") as f:
    for a in agents:
        a_id = a[0]
        task = a[1]
        f.write(f"\n====================\nTask: {task[:60]}...\n")
        
        t_res = conn.execute("MATCH (a:Agent {id: $aid})-[r:EXECUTED]->(t:ToolCall) RETURN t.step_index, t.tool_name, t.success, t.args_json ORDER BY t.step_index ASC", {"aid": a_id})
        while t_res.has_next():
            t = t_res.get_next()
            f.write(f"\nStep {t[0]} - {t[1]} (Success={t[2]}):\n{t[3][:300]}\n")
