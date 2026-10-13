"""
Conversations that continue, chats that belong to tabs and tab groups, and agents that work across a group's tabs.

The identity model: group_id (tabs sharing one chat) -> conversation_id (the chat) -> run_id (one execution) ->
tab_id (a browser tab) -> worker_id (an agent's own authority). These tests cover the backend half; the interface
keeps a group id on every tab and asks the backend for that group's chat.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import agent_service as A
from nervous.action_policy import get_target_registry
from services.chat_store import ChatStore, set_chat_store
from services.conversation import (TurnRecorder, conversation_brief, outcomes_block, page_block,
                                   pick_result_tab)
from services.orchestrator import OrchestratorTask, WorkerResult, build_worker_brief

client = TestClient(A.app)


@pytest.fixture(autouse=True)
def store():
    s = ChatStore(os.path.join(tempfile.mkdtemp(prefix="conv-groups-"), "chats.db"))
    set_chat_store(s)
    yield s
    set_chat_store(None)
    get_target_registry().reset()
    A._FG_PINS.clear()


class _Result:
    def __init__(self, text, metadata=None):
        self._t, self.metadata = text, metadata or {}

    def __str__(self):
        return self._t


def _stream(task, task_id, conversation_id, group_id="grp-tab-1", **extra):
    return client.post("/agent/run/stream", json={
        "task": task, "taskId": task_id, "tabId": "active_tab", "conversation_id": conversation_id,
        "group_id": group_id, "ui_tab_id": "tab-1", "contextToken": A._INTERNAL_APP_TOKEN, **extra})


# ── chats per tab and per group (HTTP API) ─────────────────────────────────────────────────────────

def test_each_independent_tab_gets_its_own_chat_and_a_group_shares_one():
    a = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1", "tab_id": "tab-1"}).json()
    b = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-2", "tab_id": "tab-2"}).json()
    assert a["conversation_id"] != b["conversation_id"]
    client.post("/chat/groups/join", json={"group_id": "grp-tab-1", "tab_id": "tab_amazon_r1", "role": "agent"})
    again = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1"}).json()
    assert again["conversation_id"] == a["conversation_id"]
    assert {t["tab_id"] for t in again["tabs"]} == {"tab-1", "tab_amazon_r1"}


def test_new_chat_keeps_group_tabs_and_the_old_conversation():
    first = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1", "tab_id": "tab-1"}).json()
    client.post("/chat/groups/join", json={"group_id": "grp-tab-1", "tab_id": "tab_w1", "role": "agent"})
    new = client.post("/chat/groups/new", json={"group_id": "grp-tab-1"}).json()
    assert new["conversation_id"] != first["conversation_id"] and new["messages"] == []
    tabs = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1"}).json()["tabs"]
    assert {t["tab_id"] for t in tabs} == {"tab-1", "tab_w1"}


def test_closing_a_worker_tab_does_not_close_the_chat():
    cid = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1", "tab_id": "tab-1"}).json()["conversation_id"]
    client.post("/chat/groups/join", json={"group_id": "grp-tab-1", "tab_id": "tab_w1", "role": "agent"})
    assert client.post("/chat/tabs/tab_w1/closed").json()["closed_conversation_id"] is None
    assert client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1"}).json()["conversation_id"] == cid


def test_bad_ids_are_rejected():
    assert client.post("/chat/groups/ensure", json={"group_id": "../etc"}).status_code == 400
    assert client.post("/chat/groups/attach", json={"group_id": "grp-tab-1", "conversation_id": "conv_nope"}).status_code == 404


# ── a turn is stored, and the next turn sees it ─────────────────────────────────────────────────────

def test_a_follow_up_sees_the_stored_history_and_the_verified_outcome():
    cid = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1", "tab_id": "tab-1"}).json()["conversation_id"]
    seen = []

    async def loop(task, cdp, **kw):
        seen.append(kw)
        cb = kw["event_callback"]
        await cb("step", {"step": 1, "tool": "browser_click", "label": "Clicking “Add to cart”"})
        await cb("step_done", {"step": 1, "tool": "browser_click", "success": True})
        if len(seen) == 1:
            return _Result("Added Problems in General Physics to your cart (₹173).",
                           {"task_outcome": {"action": "browser_click", "status": "success", "url": "https://www.amazon.in/dp/9368402558",
                                             "details": "Added Problems in General Physics to the cart"}})
        return _Result("It costs ₹173.")

    with patch("agent_service._resolve_verified_tab_ws", return_value=("T", "ws://127.0.0.1:9222/devtools/page/T")), \
         patch("agent_service.execute_agent_loop", side_effect=loop):
        assert "event: done" in _stream("add the irodov book to my cart", "task-1", cid).text
        _stream("how much was it?", "task-2", cid)

    second = seen[1]
    assert [m["role"] for m in second["conversation_messages"]] == ["user", "assistant"]
    assert "Added Problems in General Physics" in second["conversation_messages"][1]["content"]
    assert second["conversation_outcomes"][0]["url"] == "https://www.amazon.in/dp/9368402558"
    assert second["group_id"] == "grp-tab-1" and second["ui_tab_id"] == "tab-1"
    stored = client.post("/chat/groups/ensure", json={"group_id": "grp-tab-1"}).json()["messages"]
    assert [m["role"] for m in stored] == ["user", "assistant", "user", "assistant"]
    assert stored[1]["meta"]["activity"][0]["label"] == "Clicking “Add to cart”"
    assert stored[1]["meta"]["status"] == "completed"


def test_without_a_conversation_nothing_is_stored_and_the_run_still_works():
    with patch("agent_service._resolve_verified_tab_ws", return_value=("T", "ws://127.0.0.1:9222/devtools/page/T")), \
         patch("agent_service.execute_agent_loop", new_callable=AsyncMock, return_value=_Result("ok")) as loop:
        r = client.post("/agent/run/stream", json={"task": "hi", "taskId": "t-x", "tabId": "active_tab",
                                                   "contextToken": A._INTERNAL_APP_TOKEN})
    assert "event: done" in r.text
    assert loop.call_args.kwargs["conversation_outcomes"] is None


def test_a_failed_turn_is_stored_as_failed_and_records_no_outcome(store):
    cid = store.ensure_group("grp-tab-1")["conversation_id"]

    async def boom(task, cdp, **kw):
        raise RuntimeError("model unreachable")

    with patch("agent_service._resolve_verified_tab_ws", return_value=("T", "ws://127.0.0.1:9222/devtools/page/T")), \
         patch("agent_service.execute_agent_loop", side_effect=boom):
        _stream("book it", "task-9", cid)
    msgs = store.messages(cid)
    assert msgs[-1]["meta"]["status"] == "failed" and store.outcomes(cid) == []


def test_a_turn_is_stored_once_even_if_finished_twice(store):
    cid = store.ensure_group("g")["conversation_id"]
    rec = TurnRecorder.open(store, cid, "task-1", "hi")
    rec.finish("hello", "completed")
    rec.finish("hello again", "completed")
    again = TurnRecorder(store, cid, "task-1")
    again.finish("retried write", "completed")
    assert [m["content"] for m in store.messages(cid)] == ["hi", "hello"]


# ── what the agent is told ──────────────────────────────────────────────────────────────────────────

def test_the_done_list_tells_the_agent_not_to_repeat_actions():
    text = outcomes_block([{"action": "Added Irodov to the cart", "status": "completed", "url": "https://amazon.in/cart"}])
    assert "Do not repeat" in text and "Added Irodov to the cart" in text
    assert outcomes_block([]) == ""


def test_page_context_is_small_and_only_for_web_pages():
    block = page_block({"url": "https://www.amazon.in/dp/1", "title": "Irodov", "text": "x" * 5000}, 1200)
    assert "https://www.amazon.in/dp/1" in block and len(block) < 1600 and "untrusted" in block
    assert page_block({"url": "comex://launchpad", "title": "Launchpad", "text": "hi"}) == ""


async def test_the_parent_agent_starts_with_the_live_page_and_the_done_list():
    captured = {}

    class LLM:
        def bind_tools(self, tools):
            captured["tools"] = [t.name for t in tools]
            return self

        async def ainvoke(self, messages, **kw):
            from langchain_core.messages import AIMessage
            captured["prompt"] = "\n".join(str(m.content) for m in messages)
            return AIMessage(content="It was ₹173.", tool_calls=[])

    svc = AsyncMock()
    svc.extract = AsyncMock(return_value=type("R", (), {"success": True, "data": {
        "url": "https://www.amazon.in/gp/cart/view.html", "title": "Amazon.in Shopping Cart", "text": "Subtotal ₹173 Problems in General Physics"}})())
    with patch.object(A, "ChatOpenAI", return_value=LLM()), \
         patch.object(A, "_make_agent_loop_context", return_value=AsyncMock()), \
         patch.object(A, "_get_comex_tool_service", return_value=svc, create=True):
        await A._execute_agent_loop_impl(
            task="how much was it?", default_cdp_url="http://127.0.0.1:9222", use_graph=False, trusted_app_context=True,
            tool_service=svc, conversation_outcomes=[{"action": "Added Irodov to the cart", "status": "completed",
                                                      "url": "https://www.amazon.in/cart"}])
    assert "Added Irodov to the cart" in captured["prompt"]
    assert "Amazon.in Shopping Cart" in captured["prompt"] and "Subtotal ₹173" in captured["prompt"]


# ── workers inherit the conversation, not the whole chat ────────────────────────────────────────────

def test_a_worker_gets_a_brief_of_the_conversation_and_its_own_objective():
    brief_text = conversation_brief(
        [{"role": "user", "content": "find GATE aptitude books"}, {"role": "assistant", "content": "Best: PW GATE Aptitude, ₹499"}],
        [{"action": "Opened the PW store page", "status": "completed", "url": "https://store.pw.live/x"}])
    task = OrchestratorTask(id="flipkart", description="Price of PW GATE Aptitude on Flipkart")
    brief = build_worker_brief("compare it on flipkart", task, [task], brief_text)
    assert "YOUR OBJECTIVE: Price of PW GATE Aptitude on Flipkart" in brief
    assert "Best: PW GATE Aptitude" in brief and "UNTRUSTED DATA START" in brief


async def test_worker_tabs_open_in_the_runs_group_and_join_it_in_the_store(store):
    from services.orchestrator import MultiAgentOrchestrator
    opened = []

    async def provision(tab_id, url, label, group_id=None):
        opened.append((tab_id, group_id))
        return "TARGET", "ws://127.0.0.1:9222/devtools/page/TARGET"

    def factory(brief):
        async def fn(ctx, svc):
            return WorkerResult(findings="ok", success=True)
        return fn

    orch = MultiAgentOrchestrator(tool_service=AsyncMock(), tab_provisioner=provision, worker_factory=factory)
    run = orch.create_run("compare", [OrchestratorTask(id="a", description="A")], group_id="grp-tab-1", context="earlier: X")
    await orch.execute_run(run)
    assert opened and opened[0][1] == "grp-tab-1"
    assert run.context == "earlier: X"


# ── the parent agent can move between its group's tabs, and only those ──────────────────────────────

async def test_switching_tabs_is_limited_to_the_conversations_group(store):
    store.ensure_group("grp-tab-1", tab_id="tab-1")
    store.join_group("grp-tab-1", "tab_amazon_r1", role="agent")
    store.ensure_group("grp-tab-2", tab_id="tab-2")
    get_target_registry().register_tab_target("fg-run1", "T1", "ws://127.0.0.1:9222/devtools/page/T1")
    A._FG_PINS["fg-run1"] = "tab-1"
    events = []

    async def emit(kind, data):
        events.append((kind, data))

    infos = {"tab_amazon_r1": {"tabId": "tab_amazon_r1", "targetId": "T9", "url": "https://amazon.in/dp/1", "title": "Irodov"},
             "tab-2": {"tabId": "tab-2", "targetId": "T2", "url": "https://other.example", "title": "Other"}}
    with patch("services.tab_provisioning.describe_tab", new_callable=AsyncMock, side_effect=lambda tid, cdp: infos.get(tid)), \
         patch("services.tab_provisioning.target_ws_url", side_effect=lambda t, c: f"ws://127.0.0.1:9222/devtools/page/{t}"), \
         patch("services.tab_provisioning.bring_tab_to_front", new_callable=AsyncMock) as front, \
         patch("nervous.cdp_session.close_tab_session", new_callable=AsyncMock):
        tools = {t.name: t for t in A._build_group_tab_tools("fg-run1", "grp-tab-1", emit)}
        refused = await tools["browser_switch_tab"].ainvoke({"tab_id": "tab-2"})
        assert refused.startswith("Error") and get_target_registry().lookup_tab_target("fg-run1")[0] == "T1"
        moved = await tools["browser_switch_tab"].ainvoke({"tab_id": "tab_amazon_r1"})
    assert "Now working in tab tab_amazon_r1" in moved
    assert get_target_registry().lookup_tab_target("fg-run1")[0] == "T9"
    assert A._FG_PINS["fg-run1"] == "tab_amazon_r1"
    front.assert_awaited_once()
    assert events[-1] == ("tab_switched", {"tab_id": "tab_amazon_r1", "url": "https://amazon.in/dp/1"})


# ── when a run ends, the tab the answer points at stays ────────────────────────────────────────────

def test_the_result_tab_is_the_one_the_answer_links_to():
    answer = "Cheapest is on Flipkart: https://www.flipkart.com/pw-gate/p/itm1?pid=9 (₹449). Amazon has it at ₹499."
    cands = [("tab_amazon", ["https://www.amazon.in/s?k=pw+gate"]), ("tab_flipkart", ["https://flipkart.com/pw-gate/p/itm1"])]
    assert pick_result_tab(answer, cands) == "tab_flipkart"
    assert pick_result_tab("No links at all.", cands) is None


def test_the_run_report_prefers_the_tab_where_the_approved_action_happened():
    from services.orchestrator import AggregatedResult, OrchestrationRun
    run = OrchestrationRun(id="run_1", user_request="x", tasks={
        "a": OrchestratorTask(id="a", description="A", assigned_tab_id="tab_a"),
        "b": OrchestratorTask(id="b", description="B", assigned_tab_id="tab_b")})
    res = AggregatedResult(summary="", final_answer="see https://b.example/item",
                           task_results={"a": WorkerResult(findings="", source_urls=["https://a.example/x"], tab_id="tab_a"),
                                         "b": WorkerResult(findings="", source_urls=["https://b.example/item"], tab_id="tab_b")})
    assert A._run_tab_report(run, res) == {"agent_tab_ids": ["tab_a", "tab_b"], "result_tab_id": "tab_b"}
    res.follow_up = {"status": "completed", "tab_id": "tab_follow"}
    report = A._run_tab_report(run, res)
    assert report["result_tab_id"] == "tab_follow" and "tab_follow" in report["agent_tab_ids"]


def test_a_multi_agent_run_is_stored_in_its_conversation_with_a_brief_for_the_planner(store):
    cid = store.ensure_group("grp-tab-1", tab_id="tab-1")["conversation_id"]
    store.append_message(cid, "user", "find GATE aptitude books")
    store.append_message(cid, "assistant", "PW GATE Aptitude is ₹499 on store.pw.live")
    seen = {}

    async def fake_create(req, context=""):
        seen["context"], seen["group"] = context, req.group_id
        from services.orchestrator import OrchestrationRun
        return OrchestrationRun(id="run_x", user_request=req.user_request,
                                tasks={"a": OrchestratorTask(id="a", description="A", assigned_tab_id="tab_a")})

    from services.orchestrator import AggregatedResult
    fake_res = AggregatedResult(summary="", final_answer="Flipkart has it for ₹449.")
    orch = AsyncMock()
    orch.execute_run = AsyncMock(return_value=fake_res)
    with patch.object(A, "_create_orchestration_run", side_effect=fake_create), patch.object(A, "_get_orchestrator", return_value=orch):
        r = client.post("/agent/orchestrate/stream", json={"user_request": "compare it on flipkart", "conversation_id": cid,
                                                         "group_id": "grp-tab-1", "taskId": "task-77"})
    assert "event: done" in r.text
    assert "PW GATE Aptitude is ₹499" in seen["context"] and seen["group"] == "grp-tab-1"
    msgs = store.messages(cid)
    assert msgs[-2]["content"] == "compare it on flipkart" and msgs[-1]["content"] == "Flipkart has it for ₹449."
    assert msgs[-1]["kind"] == "run" and msgs[-1]["meta"]["run"]["agents"][0]["tabId"] == "tab_a"
