import os
from graph.store import AgentGraphStore

PROD_DB_PATH = "/tmp/graph.db_copy"
store = AgentGraphStore(PROD_DB_PATH)

results = store.conn.execute("MATCH (a:Artifact) WHERE a.artifact_type = 'procedure' RETURN a.id, a.title, a.content")
while results.has_next():
    print(results.get_next())
