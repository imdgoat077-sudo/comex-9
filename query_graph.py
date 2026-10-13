from graph.store import AgentGraphStore
import glob
dirs = glob.glob("/var/folders/2j/3y9wh_s55fl_vxvj7f8ndl1h0000gn/T/tmprx8kys89/graph.db")
if dirs:
    store = AgentGraphStore(dirs[0])
    for table in ["ToolCall", "Entity", "Artifact", "Episode", "Page"]:
        print(f"--- {table} ---")
        try:
            res = store.conn.execute(f"MATCH (n:{table}) RETURN n")
            while res.has_next():
                print(res.get_next())
        except Exception as e:
            print(f"Error: {e}")
