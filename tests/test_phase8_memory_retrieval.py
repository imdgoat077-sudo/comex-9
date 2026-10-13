import os
import shutil
import tempfile
import json
import pytest

from graph.store import AgentGraphStore
from graph.schema import run_migrations

@pytest.fixture
def temp_graph_store():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_p8.db")
    store = AgentGraphStore(db_path)
    yield store, db_path
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_fts_index_creation_and_routing(temp_graph_store):
    store, _ = temp_graph_store
    
    # Create an agent
    store.create_agent("agent_1", "find cheap monitors", "RESEARCH")
    
    # Create a tool call
    tc_id = store.record_tool_call("agent_1", "run_browser_harness", '{"code": "find()"}', "Found 5 items: question 1 is about space.", 1, True)
    
    # Create an entity
    store.upsert_entity(tc_id, None, "product", "Monitor XYZ", 12000.0, "INR", {"rating": 4.5})
    
    # Search ENTITIES
    res_entities = store.search_memory("Monitor", domain="ENTITIES")
    assert len(res_entities) == 1
    assert res_entities[0]["memory_type"] == "Entity"
    assert "Monitor XYZ" in res_entities[0]["content_excerpt"]
    
    # Search HISTORY
    res_history_agent = store.search_memory("cheap", domain="HISTORY")
    assert len(res_history_agent) == 1
    assert res_history_agent[0]["memory_type"] == "Agent"
    assert "cheap monitors" in res_history_agent[0]["content_excerpt"]
    
    res_history_tc = store.search_memory("space", domain="HISTORY")
    assert len(res_history_tc) == 1
    assert res_history_tc[0]["memory_type"] == "ToolCall"
    assert "space" in res_history_tc[0]["content_excerpt"]
    
    # Search ALL
    res_all = store.search_memory("monitor", domain="ALL")
    # Should find Agent (cheap monitors) and Entity (Monitor XYZ)
    assert len(res_all) == 2
    types = {r["memory_type"] for r in res_all}
    assert types == {"Agent", "Entity"}

def test_truncation_limits(temp_graph_store):
    store, _ = temp_graph_store
    
    long_text = "reallylongword " * 100
    store.create_agent("agent_1", long_text, "RESEARCH")
    
    res = store.search_memory("reallylongword", domain="HISTORY", limit=1)
    assert len(res) == 1
    # Should be truncated to 500 chars (497 + ...)
    assert len(res[0]["content_excerpt"]) == 500
    assert res[0]["content_excerpt"].endswith("...")
    
def test_relevance_and_limit(temp_graph_store):
    store, _ = temp_graph_store
    
    store.create_agent("agent_1", "apple pie recipe", "RESEARCH")
    store.create_agent("agent_2", "apple juice", "RESEARCH")
    store.create_agent("agent_3", "banana split", "RESEARCH")
    
    res = store.search_memory("apple", domain="HISTORY", limit=1)
    assert len(res) == 1
    assert "apple" in res[0]["content_excerpt"]
