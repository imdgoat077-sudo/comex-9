import os
import shutil
import tempfile
import unittest.mock as mock
import pytest
from fastapi.testclient import TestClient

import agent_service
from graph.store import AgentGraphStore

client = TestClient(agent_service.app)


@pytest.fixture
def temp_graph_store():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_p5_debug.db")
    store = AgentGraphStore(db_path)
    yield store, db_path, temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# =====================================================================
# 1. Stats Endpoint
# =====================================================================

def test_stats_endpoint_enabled(temp_graph_store):
    store, _, _ = temp_graph_store
    store.create_agent("agent_p5_1", "Stats test", "RESEARCH")

    with mock.patch("agent_service.graph_store", store):
        response = client.get("/agent/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert "agent_count" in data
        assert data["agent_count"] == 1
        assert "entity_count" in data
        assert "db_file_bytes" in data


def test_stats_endpoint_disabled():
    with mock.patch("agent_service.graph_store", None):
        response = client.get("/agent/graph/stats")
        assert response.status_code == 200
        assert response.json() == {"enabled": False}


# =====================================================================
# 2. Provenance Endpoint
# =====================================================================

def test_provenance_endpoint_enabled(temp_graph_store):
    store, _, _ = temp_graph_store
    agent_id = "agent_p5_prov"
    store.create_agent(agent_id, "Provenance endpoint test", "RESEARCH")
    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")
    store.upsert_entity(tc_id, page_id, "product", "Prov Monitor", 15000.0, "INR", {})

    with mock.patch("agent_service.graph_store", store):
        response = client.get(f"/agent/graph/agent/{agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent_id
        assert len(data["tool_calls"]) == 1
        assert len(data["tool_calls"][0]["entities"]) == 1


def test_provenance_endpoint_disabled():
    with mock.patch("agent_service.graph_store", None):
        response = client.get("/agent/graph/agent/some_id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Graph memory disabled"


# =====================================================================
# 3. Entities Endpoint
# =====================================================================

def test_entities_endpoint_enabled(temp_graph_store):
    store, _, _ = temp_graph_store
    agent_id = "agent_p5_entities"
    store.create_agent(agent_id, "Entities test", "RESEARCH")
    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")
    store.upsert_entity(tc_id, page_id, "product", "Cheap Monitor", 10000.0, "INR", {})
    store.upsert_entity(tc_id, page_id, "product", "Expensive Monitor", 30000.0, "INR", {})

    with mock.patch("agent_service.graph_store", store):
        # Test max_price filter
        res = client.get("/agent/graph/entities?type=product&max_price=15000.0")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["name"] == "Cheap Monitor"

        # Test default
        res_default = client.get("/agent/graph/entities")
        assert res_default.status_code == 200
        assert len(res_default.json()) == 2


def test_entities_endpoint_disabled():
    with mock.patch("agent_service.graph_store", None):
        response = client.get("/agent/graph/entities")
        assert response.status_code == 404
        assert response.json()["detail"] == "Graph memory disabled"


# =====================================================================
# 4. Reset Endpoint Safety & Functional Verification
# =====================================================================

def test_reset_endpoint_missing_confirm(temp_graph_store):
    store, _, _ = temp_graph_store
    with mock.patch("agent_service.graph_store", store):
        res = client.post("/agent/graph/reset")
        assert res.status_code == 400
        assert "confirm=true" in res.json()["detail"]

        res_false = client.post("/agent/graph/reset?confirm=false")
        assert res_false.status_code == 400


def test_reset_endpoint_disabled():
    with mock.patch("agent_service.graph_store", None):
        res = client.post("/agent/graph/reset?confirm=true")
        assert res.status_code == 404
        assert res.json()["detail"] == "Graph memory disabled"


def test_reset_endpoint_confirmed(temp_graph_store):
    store, db_path, temp_dir = temp_graph_store
    store.create_agent("agent_to_reset", "Task before reset", "RESEARCH")
    assert store.get_stats()["agent_count"] == 1

    with mock.patch("agent_service.graph_store", store), \
         mock.patch("agent_service.GRAPH_DB_PATH", db_path):
        res = client.post("/agent/graph/reset?confirm=true")
        assert res.status_code == 200
        assert res.json()["status"] == "reset"

        # Verify store was reinitialized and cleared
        stats = store.get_stats()
        assert stats["agent_count"] == 0
        assert stats["entity_count"] == 0

        # Verify SchemaMeta version is preserved after reset
        from graph.schema import SCHEMA_VERSION
        with store._lock:
            schema_res = store.conn.execute("MATCH (s:SchemaMeta {key: 'schema_version'}) RETURN s.value")
            assert schema_res.has_next()
            assert schema_res.get_next()[0] == SCHEMA_VERSION

        # Verify store remains usable after reset
        store.create_agent("agent_after_reset", "Task after reset", "RESEARCH")
        assert store.get_stats()["agent_count"] == 1
