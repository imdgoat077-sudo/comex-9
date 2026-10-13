import os
import shutil
import json
from graph.store import AgentGraphStore

db_path = os.path.expanduser("~/.comex/audit_budget.db")
if os.path.exists(db_path):
    if os.path.isdir(db_path): shutil.rmtree(db_path)
    else: os.remove(db_path)
    
store = AgentGraphStore(db_path)

# Create a huge artifact (100k chars)
huge_content = "Word. " * 20000
store.save_artifact("ag_huge", "Huge Artifact", "report", huge_content)

res = store.search_memory("huge artifact", "ALL")
for r in res:
    excerpt = r.get("content_excerpt", "")
    print(f"Retrieved excerpt length: {len(excerpt)} chars")

EOF
