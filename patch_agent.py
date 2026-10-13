import re

with open("agent_service.py", "r") as f:
    content = f.read()

# Update signature
content = content.replace(
    'async def execute_agent_loop(task: str, default_cdp_url: str, intent: str = "UNKNOWN", use_procedures: bool = True, procedure_mode: str = "blind") -> tuple[str, dict]:',
    'async def execute_agent_loop(task: str, default_cdp_url: str, intent: str = "UNKNOWN", use_procedures: bool = True, procedure_mode: str = "blind", use_graph: bool = True) -> tuple[str, dict]:'
)

# Update local graph_store
content = content.replace(
    '    agent_id = str(uuid.uuid4())\n    step_ref = {"value": 0}\n    if graph_store:',
    '    agent_id = str(uuid.uuid4())\n    step_ref = {"value": 0}\n    active_graph_store = graph_store if use_graph else None\n    if active_graph_store:'
)

content = content.replace('if graph_store and use_procedures:', 'if active_graph_store and use_procedures:')

content = content.replace('    if graph_store:\n        tools.append', '    if active_graph_store:\n        tools.append')
content = content.replace('        search_mem_tool = make_search_memory_tool(graph_store', '        search_mem_tool = make_search_memory_tool(active_graph_store')
content = content.replace('        save_artifact_tool = make_save_artifact_tool(graph_store', '        save_artifact_tool = make_save_artifact_tool(active_graph_store')
content = content.replace('        read_artifact_tool = make_read_artifact_tool(graph_store', '        read_artifact_tool = make_read_artifact_tool(active_graph_store')
content = content.replace('    if graph_store:\n        try:\n            graph_store.update_agent_status', '    if active_graph_store:\n        try:\n            active_graph_store.update_agent_status')
content = content.replace('        if graph_store:\n            try:\n                step_ref["value"] += 1\n                tool_call_id = graph_store.record_tool_call', '        if active_graph_store:\n            try:\n                step_ref["value"] += 1\n                tool_call_id = active_graph_store.record_tool_call')
content = content.replace('                                page_id = graph_store.record_navigation', '                                page_id = active_graph_store.record_navigation')
content = content.replace('                                active_graph_store.record_entity', '                                active_graph_store.record_entity') # wait, graph_store.record_entity

content = re.sub(r'graph_store\.([a-zA-Z_]+)', r'active_graph_store.\1', content)

# But we must restore global graph_store assignment at the top
content = content.replace('active_graph_store = AgentGraphStore(GRAPH_DB_PATH)', 'graph_store = AgentGraphStore(GRAPH_DB_PATH)')
content = content.replace('active_graph_store = None\nelse:\n    logging.info', 'graph_store = None\nelse:\n    logging.info')

# And update run_agent call
content = content.replace(
    'agent_task = asyncio.create_task(execute_agent_loop(request.task, target_cdp_url, request.intent, request.use_procedures, request.procedure_mode))',
    'agent_task = asyncio.create_task(execute_agent_loop(request.task, target_cdp_url, request.intent, request.use_procedures, request.procedure_mode, request.use_graph))'
)

with open("agent_service.py", "w") as f:
    f.write(content)
