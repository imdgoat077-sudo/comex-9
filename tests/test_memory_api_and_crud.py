import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from graph.store import AgentGraphStore
import agent_service

client = TestClient(agent_service.app)

@pytest.fixture
def fresh_store():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_api.db")
    store = AgentGraphStore(db_path)
    old_store = agent_service.graph_store
    agent_service.graph_store = store
    yield store
    agent_service.graph_store = old_store

def test_user_memory_api_crud(fresh_store):
    # 1. Initially empty
    res = client.get("/agent/user/memory")
    assert res.status_code == 200
    assert res.json() == []

    # 2. Add memory via POST
    res = client.post("/agent/user/memory", json={
        "key": "theme_preference",
        "value": "dark_minimal",
        "category": "preference"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "saved"

    # 3. Retrieve memory
    res = client.get("/agent/user/memory")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["key"] == "theme_preference"
    assert data[0]["value"] == "dark_minimal"

    # 4. Filter by category
    res_pref = client.get("/agent/user/memory?category=preference")
    assert len(res_pref.json()) == 1
    res_other = client.get("/agent/user/memory?category=constraint")
    assert len(res_other.json()) == 0

    # 5. Delete memory
    res_del = client.delete("/agent/user/memory/theme_preference")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"

    res_after = client.get("/agent/user/memory")
    assert len(res_after.json()) == 0

def test_skills_and_reflections_api(fresh_store):
    # 1. Save a skill
    skill_id = fresh_store.save_skill(
        name="github-repo-search",
        domain="github.com",
        description="Search repos on GitHub",
        code_snippet="click('#search-input')"
    )

    # 2. GET /agent/skills
    res = client.get("/agent/skills?domain=github.com")
    assert res.status_code == 200
    skills = res.json()
    assert len(skills) >= 1
    assert skills[0]["name"] == "github-repo-search"

    # 3. DELETE /agent/skills/{id}
    res_del = client.delete(f"/agent/skills/{skill_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"

    # 4. Record reflection
    ref_id = fresh_store.record_reflection(
        agent_id="agent_123",
        is_novel=True,
        novelty_reason="Encountered new multi-step dynamic modal",
        critique="Too many DOM evaluations",
        lesson_learned="Use direct selector instead of search",
        suggested_skill_name="modal-dismiss"
    )

    # 5. GET /agent/reflections
    res_ref = client.get("/agent/reflections?limit=5")
    assert res_ref.status_code == 200
    refs = res_ref.json()
    assert len(refs) >= 1
    assert refs[0]["is_novel"] is True
    assert "modal" in refs[0]["novelty_reason"]

    # 6. GET /agent/memory/overview
    res_ov = client.get("/agent/memory/overview")
    assert res_ov.status_code == 200
    assert res_ov.json()["enabled"] is True
    stats = res_ov.json()["stats"]
    assert stats["reflection_count"] >= 1
