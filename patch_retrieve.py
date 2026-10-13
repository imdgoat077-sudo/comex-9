with open("agent_service.py", "r") as f:
    content = f.read()

content = content.replace(
    'def retrieve_procedures(abstract_query: str, capability: str) -> list:',
    'def retrieve_procedures(abstract_query: str, capability: str, store) -> list:'
)
content = content.replace(
    '    if not graph_store or capability == "none" or not abstract_query:\n        return []\n    return active_graph_store.search_procedures(abstract_query, limit=2, threshold=0.1)',
    '    if not store or capability == "none" or not abstract_query:\n        return []\n    return store.search_procedures(abstract_query, limit=2, threshold=0.1)'
)
content = content.replace(
    'candidates = retrieve_procedures(route.abstract_query, route.capability)',
    'candidates = retrieve_procedures(route.abstract_query, route.capability, active_graph_store)'
)

with open("agent_service.py", "w") as f:
    f.write(content)
