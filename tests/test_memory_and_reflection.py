import pytest
from unittest.mock import AsyncMock, MagicMock
from graph.store import AgentGraphStore
from langchain_core.messages import AIMessage
import json


def test_user_memory_crud_and_fts(graph_store):
    # 1. Upsert user memory
    m1 = graph_store.set_user_memory(key="default_currency", value="INR", category="preference")
    assert m1.startswith("usr_")

    m2 = graph_store.set_user_memory(key="shipping_city", value="Bengaluru", category="profile")
    assert m2.startswith("usr_")

    # 2. Retrieve all
    all_mems = graph_store.get_all_user_memory()
    assert len(all_mems) == 2
    keys = [m["key"] for m in all_mems]
    assert "default_currency" in keys
    assert "shipping_city" in keys

    # 3. Filter by category
    prefs = graph_store.get_all_user_memory(category="preference")
    assert len(prefs) == 1
    assert prefs[0]["value"] == "INR"

    # 4. Search via unified FTS
    results = graph_store.search_memory(query="Bengaluru", domain="USER")
    assert len(results) >= 1
    assert "Bengaluru" in results[0]["content_excerpt"]


def test_skill_storage_and_domain_lookup(graph_store):
    # 1. Save skills
    s1 = graph_store.save_skill(
        name="amazon-bypass-overlay",
        domain="amazon.in",
        description="Dismisses prime overlay banner",
        code_snippet="js('document.querySelector(\".prime-close\")?.click()')"
    )
    assert s1.startswith("skl_")

    s2 = graph_store.save_skill(
        name="generic-scroll",
        domain="*",
        description="Scroll to bottom",
        code_snippet="scroll_to_bottom()"
    )
    assert s2.startswith("skl_")

    # 2. Find skills for domain
    domain_skills = graph_store.find_skills_for_domain("amazon.in")
    names = [s["name"] for s in domain_skills]
    assert "amazon-bypass-overlay" in names
    assert "generic-scroll" in names

    # 3. Search via FTS
    results = graph_store.search_memory(query="Dismisses prime", domain="SKILLS")
    assert len(results) >= 1
    assert "amazon-bypass-overlay" in results[0]["content_excerpt"]


def test_reflection_recording(graph_store):
    ref_id = graph_store.record_reflection(
        agent_id="test_agent_123",
        is_novel=True,
        novelty_reason="First time encountering complex modal dialog on target site",
        critique="Initial selector failed; succeeded after checking shadow DOM",
        lesson_learned="Always check shadow DOM for modern shopping carts",
        suggested_skill_name="shadow-dom-click"
    )
    assert ref_id.startswith("ref_")

    stats = graph_store.get_stats()
    assert stats["reflection_count"] >= 1


@pytest.mark.asyncio
async def test_reflect_and_distill_worker(graph_store):
    from agent_service import reflect_and_distill

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock()

    reflection_json = {
        "is_novel": True,
        "novelty_reason": "New interactive calendar widget",
        "critique": "Took 3 extra clicks to find date cell",
        "lesson_learned": "Click data-date attribute directly",
        "distill_skill": True,
        "skill_name": "calendar-date-pick",
        "skill_domain": "booking.com",
        "skill_description": "Selects a check-in date directly via attribute",
        "skill_code": "js('document.querySelector(\"[data-date=2026-09-10]\")?.click()')",
        "learned_user_facts": [
            {"key": "preferred_airline", "value": "IndiGo", "category": "preference"}
        ]
    }

    mock_llm.ainvoke.return_value = AIMessage(content=json.dumps(reflection_json))

    await reflect_and_distill(
        agent_id="ag_test_worker",
        task="Book flight on booking.com",
        final_result="Successfully selected date",
        tool_traces=[{"tool": "run_browser_harness", "success": True}],
        outcome="completed",
        store=graph_store,
        llm=mock_llm
    )

    # Verify skill was distilled into store
    skills = graph_store.find_skills_for_domain("booking.com")
    assert any(s["name"] == "calendar-date-pick" for s in skills)

    # Verify user memory was recorded
    user_mems = graph_store.get_all_user_memory()
    assert any(m["key"] == "preferred_airline" and m["value"] == "IndiGo" for m in user_mems)

    # Verify reflection was recorded
    stats = graph_store.get_stats()
    assert stats["reflection_count"] >= 1
