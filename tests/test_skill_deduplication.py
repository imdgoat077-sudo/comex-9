import os
import tempfile
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from graph.store import AgentGraphStore
import agent_service

client = TestClient(agent_service.app)

@pytest.fixture
def fresh_store():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_dedup.db")
    store = AgentGraphStore(db_path)
    old_store = agent_service.graph_store
    agent_service.graph_store = store
    yield store
    agent_service.graph_store = old_store

def test_semantic_deduplication_on_save(fresh_store):
    # 1. Save initial skill
    id1 = fresh_store.save_skill(
        name="excalidraw-scene-inject",
        domain="excalidraw.com",
        description="Programmatically inject nodes, shapes, and text into Excalidraw canvas via React internal stateNode",
        code_snippet="def inject_excalidraw_scene(elements): pass"
    )

    # 2. Save near-identical skill with different name and more details
    id2 = fresh_store.save_skill(
        name="excalidraw-react-fiber-scene-inject",
        domain="excalidraw.com",
        description="Locates Excalidraw React component instance via DOM React Fiber and updates scene elements and appState programmatically.",
        code_snippet="def inject_excalidraw_scene(elements, app_state=None):\n    # traverse __reactFiber\n    pass"
    )

    # id2 should merge into id1, not create a duplicate
    assert id1 == id2

    skills = fresh_store.find_skills_for_domain("excalidraw.com")
    assert len(skills) == 1
    assert skills[0]["id"] == id1
    # Usage count should have incremented
    assert skills[0]["usage_count"] == 2
    # Longer description and snippet should be retained
    assert "Fiber" in skills[0]["description"]
    assert "app_state=None" in skills[0]["code_snippet"]

def test_consolidate_skills_utility(fresh_store):
    # Bypass semantic dedup by saving with forced distinct IDs or distinct initial tokens
    # Save first skill
    id1 = fresh_store.save_skill(
        name="github-repo-search",
        domain="github.com",
        description="Search repos on GitHub",
        code_snippet="click('#search-input')"
    )

    # Manually insert a duplicate with raw Cypher to simulate legacy pre-dedup database state
    with fresh_store._lock:
        now = datetime.now(timezone.utc)
        fresh_store.conn.execute("""
        CREATE (s:Skill {
            id: 'skl_github_dup_legacy',
            name: 'github-repository-search-filter',
            domain: 'github.com',
            description: 'Search and filter repositories on GitHub search page',
            code_snippet: 'click(\\'#search-input\\'); filter_language()',
            usage_count: 3,
            success_count: 2,
            created_at: $now,
            updated_at: $now,
            source_agent_id: ''
        })
        """, {"now": now})

    # Verify 2 skills exist before consolidation
    skills_before = fresh_store.find_skills_for_domain("github.com")
    assert len(skills_before) == 2

    # Run consolidation
    res = client.post("/agent/skills/consolidate")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["consolidated_count"] >= 1

    # Verify only 1 canonical skill remains
    skills_after = fresh_store.find_skills_for_domain("github.com")
    assert len(skills_after) == 1
    canonical = skills_after[0]
    assert canonical["usage_count"] >= 4
    assert "filter_language" in canonical["code_snippet"]
