"""
Self-learning (graph/learning.py): lessons from difficult runs, recalled by the site the page is on, credited or demoted
by later runs, and finished conversations compacted into long-term memory once, even across crashes.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

import agent_service as A
from graph.learning import (ConversationCompactor, assess_difficulty, compact_conversation, keep_user_fact,
                            lessons_block, recall_for_site, record_evidence, site_of)
from services.chat_store import ChatStore


# ── what counts as a site, and as a difficult run ──────────────────────────────────────────────────

@pytest.mark.parametrize("url, site", [("https://www.amazon.in/dp/1", "amazon.in"), ("http://vitcolab.example/x?y=1", "vitcolab.example"),
                                       ("amazon.in", "amazon.in"), ("", ""), ("comex://launchpad", "launchpad")])
def test_site_of(url, site):
    assert site_of(url) == site


def _trace(tool, ok=True, url=None):
    return {"tool": tool, "success": ok, "args": {"url": url} if url else {}}


def test_a_routine_run_is_not_difficult():
    assert assess_difficulty({"tool_traces": [_trace("browser_navigate", url="https://amazon.in"), _trace("browser_click")],
                              "failed_tool_call_count": 0}) == []


def test_failures_many_actions_many_sites_or_running_out_make_a_run_difficult():
    assert "2 actions failed" in assess_difficulty({"tool_traces": [_trace("x", False), _trace("y", False)], "failed_tool_call_count": 2})
    assert any("13 actions" in r for r in assess_difficulty({"tool_traces": [_trace("x")] * 13}))
    sites = [_trace("browser_navigate", url=f"https://{d}/") for d in ("anotepad.com", "justpaste.it", "notes.io")]
    assert any("3 sites" in r for r in assess_difficulty({"tool_traces": sites}))
    assert "it ran out of time or actions" in assess_difficulty({"tool_traces": [_trace("x")], "stopped_early": "deadline"})


# ── lessons: stored per site, deduplicated, ranked by evidence, demoted when they keep failing ──────

def test_the_same_obstacle_refines_one_lesson(graph_store):
    a = graph_store.save_lesson("vitcolab.example", "The submit button is hidden behind a cookie banner",
                                "Dismiss the cookie banner first, then click Submit")
    b = graph_store.save_lesson("www.vitcolab.example".removeprefix("www."), "Submit button hidden behind the cookie banner",
                                "Click 'Accept all' on the banner, then Submit")
    c = graph_store.save_lesson("vitcolab.example", "Login page asks for an OTP", "Ask the user for the OTP")
    assert a == b and c != a
    lessons = graph_store.find_lessons("vitcolab.example", limit=5)
    assert len(lessons) == 2
    assert next(l for l in lessons if l["id"] == a)["approach"] == "Click 'Accept all' on the banner, then Submit"


def test_lessons_are_ranked_by_evidence_and_demoted_when_they_keep_failing(graph_store):
    good = graph_store.save_lesson("shop.example", "Search box only accepts Enter", "Type then press Enter")
    bad = graph_store.save_lesson("shop.example", "Price is inside an iframe", "Read the iframe text")
    graph_store.record_lesson_outcome([good], True)
    graph_store.record_lesson_outcome([good], True)
    assert graph_store.find_lessons("shop.example")[0]["id"] == good
    for _ in range(3):
        graph_store.record_lesson_outcome([bad], False)
    assert [l["id"] for l in graph_store.find_lessons("shop.example")] == [good]
    # learning it again puts it on probation, a success makes it active again
    graph_store.save_lesson("shop.example", "Price is inside an iframe", "Switch into the iframe, then read the price")
    assert bad in [l["id"] for l in graph_store.find_lessons("shop.example")]
    graph_store.record_lesson_outcome([bad], True)
    assert next(l for l in graph_store.find_lessons("shop.example") if l["id"] == bad)["status"] == "active"


def test_recall_offers_lessons_for_the_site_only_and_marks_them_as_data(graph_store):
    graph_store.save_lesson("vitcolab.example", "Lab slots load slowly", "Wait for the slot table, then pick")
    graph_store.save_lesson("other.example", "Unrelated", "Unrelated approach")
    out = recall_for_site(graph_store, "vitcolab.example")
    assert len(out["lesson_ids"]) == 1 and "Lab slots load slowly" in out["text"] and "may be outdated" in out["text"]
    assert recall_for_site(graph_store, "nothing.example") == {"text": "", "lesson_ids": []}
    assert lessons_block("x", []) == ""


def test_evidence_counts_lessons_and_skills_offered_to_a_run(graph_store):
    lid = graph_store.save_lesson("s.example", "Obstacle words here", "Approach")
    sid = graph_store.save_skill("s-search", "s.example", "Search s", "navigate to search url")
    record_evidence(graph_store, {"lessons_shown": [lid], "skills_shown": [sid]}, True)
    lesson = graph_store.find_lessons("s.example")[0]
    assert (lesson["uses"], lesson["successes"]) == (1, 1)
    skill = next(s for s in graph_store.find_skills_for_domain("s.example") if s["id"] == sid)
    assert skill["usage_count"] >= 2 and skill["success_count"] >= 2  # saving counts as one use already


def test_skills_saved_with_www_are_still_found(graph_store):
    graph_store.save_skill("amazon-search", "www.amazon.in", "Search Amazon", "navigate to /s?k=")
    assert any(s["name"] == "amazon-search" for s in graph_store.find_skills_for_domain("amazon.in"))


def test_a_user_fact_is_one_memory_even_if_an_older_version_stored_it_under_another_id(graph_store):
    with graph_store._lock:
        graph_store.conn.execute("CREATE (u:UserMemory {id: 'usr_old_random', category: 'preference', key: 'home_city', "
                                 "value: 'Chennai', confidence: 1.0, source_agent_id: '', created_at: timestamp('2026-01-01'), "
                                 "updated_at: timestamp('2026-01-01')})")
    graph_store.set_user_memory("home_city", "Bengaluru")
    mems = [m for m in graph_store.get_all_user_memory() if m["key"] == "home_city"]
    assert len(mems) == 1 and mems[0]["value"] == "Bengaluru"


@pytest.mark.parametrize("fact, keep", [
    ({"key": "preferred_airline", "value": "IndiGo"}, True),
    ({"key": "local_comex_path", "value": "/Users/me/.comex"}, False),
    ({"key": "local_username", "value": "pranav"}, False),
    ({"key": "home_folder", "value": "~/x"}, False),
    ({"key": "", "value": "x"}, False),
])
def test_only_real_user_facts_are_kept(fact, keep):
    assert keep_user_fact(fact) is keep


# ── reflection learns a lesson only from a difficult run ─────────────────────────────────────────────

def _reflection_llm(lesson):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=json.dumps({
        "is_novel": False, "novelty_reason": "", "critique": "", "lesson_learned": "", "distill_skill": False,
        "learned_user_facts": [{"key": "local_username", "value": "pranavkumarn", "category": "profile"}],
        "lesson": lesson})))
    return llm


LESSON = {"site": "justpaste.it", "obstacle": "The note body is a rich-text editor inside an iframe",
          "approach": "Click into the editor with browser_pointer, then browser_keys(text=...)", "avoid": "browser_evaluate writes"}


async def test_a_difficult_run_leaves_a_lesson_for_its_site(graph_store):
    await A.reflect_and_distill("ag1", "write notes", "done", [_trace("browser_navigate", url="https://justpaste.it/")],
                                "completed", graph_store, _reflection_llm(LESSON), difficulty=["2 actions failed"], site="justpaste.it")
    lessons = graph_store.find_lessons("justpaste.it")
    assert len(lessons) == 1 and "iframe" in lessons[0]["obstacle"]
    assert not any(m["key"] == "local_username" for m in graph_store.get_all_user_memory())


async def test_a_routine_run_leaves_no_lesson_even_if_the_model_offers_one(graph_store):
    await A.reflect_and_distill("ag2", "write notes", "done", [], "completed", graph_store, _reflection_llm(LESSON),
                                difficulty=[], site="justpaste.it")
    assert graph_store.find_lessons("justpaste.it") == []


# ── the agent recalls by the page's site, and the run is counted as evidence ─────────────────────────

async def test_the_agent_gets_lessons_for_the_site_its_page_is_on(graph_store):
    lid = graph_store.save_lesson("vitcolab.example", "Lab slot table loads after a spinner", "Wait for the table, then choose")
    captured = {}

    class LLM:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages, **kw):
            captured["prompt"] = "\n".join(str(m.content) for m in messages)
            return AIMessage(content="Booked nothing; here are the slots.", tool_calls=[])

    svc = AsyncMock()
    svc.extract = AsyncMock(return_value=type("R", (), {"success": True, "data": {
        "url": "https://www.vitcolab.example/slots", "title": "Lab slots", "text": "Slots"}})())
    with patch.object(A, "ChatOpenAI", return_value=LLM()), patch.object(A, "graph_store", graph_store), \
         patch.object(A, "_make_agent_loop_context", return_value=AsyncMock()):
        res = await A._execute_agent_loop_impl(task="show me the free lab slots", default_cdp_url="http://127.0.0.1:9222",
                                               use_graph=True, trusted_app_context=True, tool_service=svc)
    assert "Lab slot table loads after a spinner" in captured["prompt"]
    assert res.metadata["site"] == "vitcolab.example" and res.metadata["lessons_shown"] == [lid]
    lesson = graph_store.find_lessons("vitcolab.example")[0]
    assert (lesson["uses"], lesson["successes"]) == (1, 1)


# ── compaction of finished conversations ────────────────────────────────────────────────────────────

def _closed_conversation(store):
    cid = store.ensure_group("grp-t", tab_id="t")["conversation_id"]
    store.append_message(cid, "user", "I live in Chennai. Find train tickets to Bengaluru for Friday")
    store.append_message(cid, "assistant", "Found the Shatabdi at 06:00 for ₹1,105: https://erail.in/x")
    store.remove_tab("t")
    return cid


def _compact_llm():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=json.dumps({
        "summary": "User asked for Friday trains Chennai to Bengaluru; Shatabdi 06:00 ₹1,105 (https://erail.in/x).",
        "user_facts": [{"key": "home_city", "value": "Chennai", "category": "profile"},
                       {"key": "local_path", "value": "/Users/me", "category": "profile"}]})))
    return llm


@pytest.fixture
def chats():
    return ChatStore(os.path.join(tempfile.mkdtemp(prefix="learn-chat-"), "chats.db"))


async def test_a_closed_conversation_is_compacted_once(chats, graph_store):
    cid = _closed_conversation(chats)
    llm = _compact_llm()
    assert await compact_conversation(cid, chats, graph_store, llm) is True
    assert chats.conversation(cid)["compaction_status"] == "done" and "Shatabdi" in chats.conversation(cid)["summary"]
    art = graph_store.get_artifact(f"convsum_{cid}")
    assert "Shatabdi" in str(art)
    facts = {m["key"]: m["value"] for m in graph_store.get_all_user_memory()}
    assert facts.get("home_city") == "Chennai" and "local_path" not in facts
    # a second request does nothing: no model call, no duplicates
    assert await compact_conversation(cid, chats, graph_store, llm) is False
    assert llm.ainvoke.await_count == 1


async def test_compacting_again_after_a_crash_does_not_duplicate_memory(chats, graph_store):
    cid = _closed_conversation(chats)
    await compact_conversation(cid, chats, graph_store, _compact_llm())
    chats.set_compaction(cid, "pending")  # as if the app died before recording "done"
    await compact_conversation(cid, chats, graph_store, _compact_llm())
    with graph_store._lock:
        n_art = graph_store.conn.execute("MATCH (a:Artifact) WHERE a.id = $id RETURN count(a)", {"id": f"convsum_{cid}"}).get_next()[0]
    assert n_art == 1
    assert len([m for m in graph_store.get_all_user_memory() if m["key"] == "home_city"]) == 1


async def test_a_failed_compaction_stays_pending_and_is_finished_after_a_restart(chats, graph_store):
    cid = _closed_conversation(chats)
    broken = MagicMock()
    broken.ainvoke = AsyncMock(side_effect=RuntimeError("model unreachable"))
    first = ConversationCompactor(lambda: chats, lambda: graph_store, lambda: broken)
    assert await first.run_pending() == 0
    assert chats.conversation(cid)["compaction_status"] == "pending"
    restarted = ConversationCompactor(lambda: chats, lambda: graph_store, _compact_llm)
    assert await restarted.run_pending() == 1
    assert chats.pending_compaction() == []
