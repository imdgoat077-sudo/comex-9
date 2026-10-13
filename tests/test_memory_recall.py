"""
Automatic memory recall (graph/recall.py, Phase C): the query is what the task is about (plus the site, plus the
previous turn for a follow-up), only related memory is injected, procedures are left to their own retrieval, and
lessons are searchable.
"""

from __future__ import annotations

import uuid

import pytest

from graph.recall import build_query, focus_text, recall
from graph.store import AgentGraphStore


@pytest.fixture
def store(tmp_path):
    return AgentGraphStore(str(tmp_path / f"g_{uuid.uuid4().hex}.db"))


def test_query_uses_content_words_and_site():
    q, terms = build_query("Please find wireless headphones under 3000", site="amazon.in")
    assert "wireless" in terms and "headphones" in terms and "amazon" in terms
    assert "please" not in terms and "find" not in terms


def test_referential_follow_up_borrows_the_previous_turn():
    history = [{"role": "user", "content": "Find Sony WH-1000XM5 headphones price"},
               {"role": "assistant", "content": "The Sony WH-1000XM5 costs 26990 on Amazon."}]
    _, terms = build_query("add that to the cart", history=history)
    assert "sony" in terms and "cart" in terms
    _, alone = build_query("compare laptop battery life across brands", history=history)
    assert "sony" not in alone  # a self-contained task does not drag in the last turn


def test_worker_focus_is_its_objective_not_its_whole_brief():
    brief = ("You are a research agent.\nThe user's request: best budget phones\nYOUR OBJECTIVE: Poco phones under 15000\n"
             "HOW TO WORK:\n- Prefer authoritative sources over blogs and aggregators.")
    focus = focus_text(brief)
    assert "Poco" in focus and "budget" in focus and "authoritative" not in focus


def test_relevant_memory_is_injected_and_unrelated_is_not(store):
    store.save_artifact("a1", "Headphone research", "report", "Sony WH-1000XM5 wireless headphones: 26990 INR on amazon.")
    store.save_artifact("a2", "Trip notes", "report", "Goa trip: wireless internet at the hotel was slow.")
    out = recall(store, "find wireless headphones deals", site="amazon.in")
    ids = [r["source_id"] for r in out["results"]]
    assert len(ids) == 1 and "[PERSISTENT MEMORY CONTEXT]" in out["text"] and "UNTRUSTED DATA" in out["text"]
    assert "Sony" in out["text"] and "Goa" not in out["text"]  # one shared word ("wireless") is not enough
    assert out["ms"] >= 0 and not out["triggered"]


def test_nothing_related_injects_nothing(store):
    store.save_artifact("a2", "Trip notes", "report", "Goa trip: the hotel was slow.")
    out = recall(store, "find wireless headphones deals")
    assert out["text"] == "" and out["results"] == []


def test_procedures_are_not_recalled_as_generic_memory(store):
    store.save_artifact("a1", "Target Procedure", "procedure", "Magic pattern to extract items.")
    assert recall(store, "Extract magic items")["results"] == []


def test_a_summary_of_an_earlier_chat_is_recalled(store):
    store.upsert_conversation_summary("conv1", "Laptop hunt", "User wanted a gaming laptop under 80000; best was ASUS TUF A15 at 74990.")
    out = recall(store, "show gaming laptop options again")
    assert "ASUS TUF" in out["text"]


def test_an_explicit_memory_question_searches_history(store):
    store.create_agent("ag1", "research rust async runtimes", "RESEARCH")
    out = recall(store, "what did you find previously about rust async runtimes")
    assert out["triggered"] and any(r["memory_type"] == "Agent" for r in out["results"])


def test_lessons_are_searchable_and_demoted_ones_are_hidden(store):
    lid = store.save_lesson("flipkart.com", "login popup covers the search results", "press Escape then scroll", agent_id="a1")
    found = store.search_memory("login popup", domain="LESSONS")
    assert [r["source_id"] for r in found] == [lid] and "press Escape" in found[0]["content_excerpt"]
    store.record_lesson_outcome([lid, lid, lid], False)
    assert store.search_memory("login popup", domain="LESSONS") == []


def test_search_says_when_the_match_is_already_in_the_prompt(store):
    from graph.tools import make_search_memory_tool
    store.save_artifact("a1", "Headphone research", "report", "Sony WH-1000XM5 wireless headphones: 26990 INR.")
    seen: set = set()
    shown = recall(store, "wireless headphones research")
    seen.update(hash(r["content_excerpt"]) for r in shown["results"])
    tool = make_search_memory_tool(store, "ag1", {"value": 0}, seen, legacy_mode=True)
    reply = tool.invoke({"query": "wireless headphones research", "domain": "ARTIFACTS"})
    assert "already shown" in reply and "No matching memory" not in reply
