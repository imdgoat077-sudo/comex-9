import json
import sys

def patch():
    with open("tests/test_phase9_artifact_memory.py", "r") as f:
        content = f.read()
        
    old_task_a = """
        # --- TASK A ---
        mock_run_a = mock.MagicMock()
        mock_run_a.returncode = 0
        mock_run_a.stdout = "Q1: What is Python?\\nQ2: What is Java?"
        mock_run_a.stderr = ""
        
        # We will mock the LLM for Task A to output a save_artifact tool call, then finish.
        mock_llm_a = mock.MagicMock()
        mock_llm_a.bind_tools.return_value = mock_llm_a
        
        call_count_a = 0
        async def side_effect_a(*args, **kwargs):
            nonlocal call_count_a
            call_count_a += 1
            if call_count_a == 1:
                # Agent decides to save artifact
                return AIMessage(content="", tool_calls=[{
                    "name": "save_artifact",
                    "args": {
                        "title": "Programming Test Questions",
                        "artifact_type": "report",
                        "content": "Q1: What is Python?\\nQ2: What is Java?"
                    },
                    "id": "call_1"
                }])
            else:
                return AIMessage(content="I have saved the artifact.", tool_calls=[])
                
        mock_llm_a.ainvoke.side_effect = side_effect_a"""
        
    new_task_a = """
        # --- TASK A ---
        mock_run_a = mock.MagicMock()
        mock_run_a.returncode = 0
        mock_run_a.stdout = ""
        mock_run_a.stderr = ""
        
        # We will mock the LLM for Task A to output a save_artifact tool call, then finish.
        mock_llm_a = mock.MagicMock()
        mock_llm_a.bind_tools.return_value = mock_llm_a
        
        call_count_a = 0
        async def side_effect_a(messages, **kwargs):
            nonlocal call_count_a
            call_count_a += 1
            if call_count_a == 1:
                # Agent decides to save artifact
                return AIMessage(content="", tool_calls=[{
                    "name": "save_artifact",
                    "args": {
                        "title": "Programming Test Questions",
                        "artifact_type": "report",
                        "content": "SENTINEL_Q1: What is Python?\\nSENTINEL_Q2: What is Java?"
                    },
                    "id": "call_1"
                }])
            else:
                return AIMessage(content="I have saved the artifact.", tool_calls=[])
                
        mock_llm_a.ainvoke.side_effect = side_effect_a"""

    old_task_b = """
        # --- TASK B ---
        mock_llm_b = mock.MagicMock()
        mock_llm_b.bind_tools.return_value = mock_llm_b
        
        call_count_b = 0
        async def side_effect_b(*args, **kwargs):
            nonlocal call_count_b
            call_count_b += 1
            if call_count_b == 1:
                # Agent searches memory
                return AIMessage(content="", tool_calls=[{
                    "name": "search_memory",
                    "args": {"query": "Programming Test Questions", "domain": "ARTIFACTS"},
                    "id": "call_2"
                }])
            else:
                return AIMessage(content="The questions are: Q1: What is Python? Q2: What is Java?", tool_calls=[])
                
        mock_llm_b.ainvoke.side_effect = side_effect_b"""
        
    new_task_b = """
        # --- TASK B ---
        mock_llm_b = mock.MagicMock()
        mock_llm_b.bind_tools.return_value = mock_llm_b
        
        call_count_b = 0
        async def side_effect_b(messages, **kwargs):
            nonlocal call_count_b
            call_count_b += 1
            if call_count_b == 1:
                # Agent searches memory
                return AIMessage(content="", tool_calls=[{
                    "name": "search_memory",
                    "args": {"query": "Programming Test Questions", "domain": "ARTIFACTS"},
                    "id": "call_2"
                }])
            else:
                last_msg = messages[-1]
                assert last_msg.type == "tool", f"Expected tool message, got {last_msg.type}"
                try:
                    import json
                    results = json.loads(last_msg.content)
                except Exception:
                    results = []
                
                if not results:
                    return AIMessage(content="Memory is empty or corrupted.", tool_calls=[])
                
                excerpt = results[0].get("content_excerpt", "")
                if "SENTINEL_Q1" not in excerpt:
                    return AIMessage(content="Sentinel missing.", tool_calls=[])
                
                return AIMessage(content=f"The retrieved questions are: {excerpt}", tool_calls=[])
                
        mock_llm_b.ainvoke.side_effect = side_effect_b"""
        
    old_task_b_assert = 'assert "Q1: What is Python? Q2: What is Java?" in res_b'
    new_task_b_assert = 'assert "SENTINEL_Q1" in res_b and "SENTINEL_Q2" in res_b'
    
    old_task_c = """
        # --- TASK C (Negative Control) ---
        mock_llm_c = mock.MagicMock()
        mock_llm_c.bind_tools.return_value = mock_llm_c
        
        call_count_c = 0
        async def side_effect_c(*args, **kwargs):
            nonlocal call_count_c
            call_count_c += 1
            if call_count_c == 1:
                # Agent searches memory
                return AIMessage(content="", tool_calls=[{
                    "name": "search_memory",
                    "args": {"query": "Chemistry Test Questions", "domain": "ARTIFACTS"},
                    "id": "call_3"
                }])
            else:
                return AIMessage(content="The requested artifact is unavailable.", tool_calls=[])
                
        mock_llm_c.ainvoke.side_effect = side_effect_c"""
        
    new_task_c = """
        # --- TASK C (Negative Control) ---
        mock_llm_c = mock.MagicMock()
        mock_llm_c.bind_tools.return_value = mock_llm_c
        
        call_count_c = 0
        async def side_effect_c(messages, **kwargs):
            nonlocal call_count_c
            call_count_c += 1
            if call_count_c == 1:
                # Agent searches memory
                return AIMessage(content="", tool_calls=[{
                    "name": "search_memory",
                    "args": {"query": "Chemistry Test Questions", "domain": "ARTIFACTS"},
                    "id": "call_3"
                }])
            else:
                last_msg = messages[-1]
                assert last_msg.type == "tool"
                try:
                    import json
                    results = json.loads(last_msg.content)
                except Exception:
                    results = []
                    
                if not results:
                    return AIMessage(content="The requested artifact is unavailable.", tool_calls=[])
                else:
                    return AIMessage(content="Wait, I found something!", tool_calls=[])
                
        mock_llm_c.ainvoke.side_effect = side_effect_c"""

    content = content.replace(old_task_a, new_task_a)
    content = content.replace(old_task_b, new_task_b)
    content = content.replace(old_task_b_assert, new_task_b_assert)
    content = content.replace(old_task_c, new_task_c)

    # I need to assert provenance is set for task A. 
    # Let's add that under 'artifacts = store.conn.execute("MATCH (a:Artifact) RETURN count(a)").get_next()[0]'
    old_verify = """        # Verify artifact is stored
        artifacts = store.conn.execute("MATCH (a:Artifact) RETURN count(a)").get_next()[0]
        assert artifacts == 1"""
        
    new_verify = """        # Verify artifact is stored
        artifacts = store.conn.execute("MATCH (a:Artifact) RETURN count(a)").get_next()[0]
        assert artifacts == 1
        
        # Verify provenance
        has_edge = store.conn.execute("MATCH (ag:Agent)-[:CREATED_ARTIFACT]->(a:Artifact) RETURN count(a)").get_next()[0]
        assert has_edge == 1"""
        
    content = content.replace(old_verify, new_verify)

    with open("tests/test_phase9_artifact_memory.py", "w") as f:
        f.write(content)
        print("Patched E2E test in test_phase9_artifact_memory.py")

patch()
