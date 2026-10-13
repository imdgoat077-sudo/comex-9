"""
Durable conversations: per-tab and per-group chats, persistence across restarts, and the bookkeeping later phases use
(closed conversations waiting for compaction, verified outcomes).
"""

from __future__ import annotations

import os
import tempfile

import pytest

from services.chat_store import ChatStore


@pytest.fixture
def path():
    d = tempfile.mkdtemp(prefix="chat-store-")
    return os.path.join(d, "chats.db")


def test_a_conversation_survives_a_restart(path):
    store = ChatStore(path)
    cid = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.append_message(cid, "user", "Find the Irodov book on Amazon")
    store.append_message(cid, "assistant", "Found it for ₹173.", meta={"task_outcome": {"action": "found", "url": "https://amazon.in/dp/1"}})
    store.close()

    reopened = ChatStore(path)
    again = reopened.ensure_group("grp-tab-1")
    assert again["conversation_id"] == cid
    msgs = reopened.messages(cid)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["meta"]["task_outcome"]["url"] == "https://amazon.in/dp/1"
    assert reopened.conversation(cid)["title"] == "Find the Irodov book on Amazon"


def test_independent_tabs_have_separate_conversations(path):
    store = ChatStore(path)
    a = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    b = store.ensure_group("grp-tab-2", tab_id="tab-2")["conversation_id"]
    store.append_message(a, "user", "only in tab one")
    assert a != b
    assert store.messages(b) == []


def test_tabs_in_one_group_share_its_conversation(path):
    store = ChatStore(path)
    cid = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.join_group("grp-tab-1", "tab_amazon_r1", role="agent", run_id="run_1", worker_id="w1")
    assert store.group_of_tab("tab_amazon_r1") == "grp-tab-1"
    assert store.ensure_group(store.group_of_tab("tab_amazon_r1"))["conversation_id"] == cid
    tabs = {t["tab_id"]: t for t in store.group_tabs("grp-tab-1")}
    assert tabs["tab_amazon_r1"]["run_id"] == "run_1" and tabs["tab_amazon_r1"]["worker_id"] == "w1"


def test_a_tab_is_in_only_one_group_at_a_time(path):
    store = ChatStore(path)
    store.ensure_group("grp-tab-1", tab_id="tab-1")
    store.ensure_group("grp-tab-9", tab_id="tab-9")
    store.join_group("grp-tab-1", "tab-9")
    assert store.group_of_tab("tab-9") == "grp-tab-1"
    assert not store.is_tab_in_group("grp-tab-9", "tab-9")


def test_closing_a_worker_tab_keeps_the_group_conversation(path):
    store = ChatStore(path)
    cid = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.append_message(cid, "user", "compare prices")
    store.join_group("grp-tab-1", "tab_w1", role="agent")
    assert store.remove_tab("tab_w1") is None
    assert store.conversation(cid)["status"] == "open"
    assert store.ensure_group("grp-tab-1")["conversation_id"] == cid


def test_closing_the_last_tab_closes_the_conversation_for_compaction(path):
    store = ChatStore(path)
    cid = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.append_message(cid, "user", "hello")
    assert store.remove_tab("tab-1") == cid
    conv = store.conversation(cid)
    assert conv["status"] == "closed" and conv["compaction_status"] == "pending"
    assert cid in store.pending_compaction()
    # a restart still knows what is left to compact
    store.close()
    assert cid in ChatStore(path).pending_compaction()


def test_an_empty_conversation_is_not_queued_for_compaction(path):
    store = ChatStore(path)
    cid = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.remove_tab("tab-1")
    assert store.conversation(cid)["compaction_status"] == "none"


def test_new_chat_starts_a_fresh_conversation_and_keeps_the_old_one(path):
    store = ChatStore(path)
    old = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.append_message(old, "user", "first chat")
    store.join_group("grp-tab-1", "tab_w1", role="agent")
    new = store.new_conversation("grp-tab-1")
    assert new != old
    assert store.ensure_group("grp-tab-1")["conversation_id"] == new
    assert store.conversation(old)["status"] == "closed" and len(store.messages(old)) == 1
    # group membership is untouched
    assert {t["tab_id"] for t in store.group_tabs("grp-tab-1")} == {"tab-1", "tab_w1"}


def test_an_earlier_conversation_can_be_reopened_in_a_tab(path):
    store = ChatStore(path)
    old = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.append_message(old, "user", "train tickets to Chennai")
    store.remove_tab("tab-1")
    store.ensure_group("grp-tab-5", tab_id="tab-5")
    store.attach_conversation("grp-tab-5", old)
    assert store.ensure_group("grp-tab-5")["conversation_id"] == old
    assert store.conversation(old)["status"] == "open"
    listed = store.list_conversations()
    assert listed[0]["id"] == old and listed[0]["message_count"] == 1


def test_a_retried_write_does_not_duplicate_a_turn(path):
    store = ChatStore(path)
    cid = store.ensure_group("g")["conversation_id"]
    store.append_message(cid, "user", "hi", message_id="task-1:user")
    store.append_message(cid, "user", "hi", message_id="task-1:user")
    assert len(store.messages(cid)) == 1


def test_model_history_is_bounded(path):
    store = ChatStore(path)
    cid = store.ensure_group("g")["conversation_id"]
    for i in range(30):
        store.append_message(cid, "user" if i % 2 == 0 else "assistant", f"message {i} " + "x" * 5000)
    hist = store.history_for_model(cid)
    assert len(hist) == 10 and hist[-1]["content"].startswith("message 29")
    assert all(len(h["content"]) <= 2000 for h in hist)


def test_verified_outcomes_are_kept_per_conversation(path):
    store = ChatStore(path)
    a = store.ensure_group("g1")["conversation_id"]
    b = store.ensure_group("g2")["conversation_id"]
    store.record_outcome(a, "Added Irodov to the cart", "completed", run_id="task-7", url="https://amazon.in/cart")
    assert store.outcomes(a)[0]["action"] == "Added Irodov to the cart"
    assert store.outcomes(b) == []


def test_unknown_conversation_is_rejected(path):
    store = ChatStore(path)
    with pytest.raises(KeyError):
        store.append_message("conv_missing", "user", "x")
