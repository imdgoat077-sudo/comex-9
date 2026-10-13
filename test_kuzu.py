import os
import shutil
from graph.store import AgentGraphStore

db_path = os.path.expanduser("~/.comex/test_kuzu.db")
if os.path.exists(db_path):
    if os.path.isdir(db_path):
        shutil.rmtree(db_path)
    else:
        os.remove(db_path)

store = AgentGraphStore(db_path)
store.save_artifact("ag", "Project Specs", "report", "Python 3.10")
res1 = store.search_memory("project specs", "ALL")
print("Results 1 (project specs):", len(res1))
res2 = store.search_memory("Python 3.10", "ALL")
print("Results 2 (Python 3.10):", len(res2))
res3 = store.search_memory("Project Specs what did you find", "ALL")
print("Results 3 (long query):", len(res3))
