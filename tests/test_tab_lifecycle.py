"""
Closing tabs and groups (browser TabManager contract, backend side): closing a worker's tab stops only that worker;
closing a group stops all of its runs and closes its conversation, which stays in History; other groups are untouched;
restoring the group (undo) continues the same conversation. The stop endpoints are for the app only.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import agent_service as A
from nervous.action_policy import ServerTabLeaseRegistry, ServerTabTargetRegistry
from services.chat_store import ChatStore
from services.orchestrator import MultiAgentOrchestrator, OrchestratorTask, RunStatus, TaskStatus, WorkerResult
from services.tool_service import ComexToolService


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as d:
        s = ChatStore(os.path.join(d, "chats.db"))
        yield s
        s.close()


def test_closing_a_group_closes_only_its_conversation_and_keeps_the_messages(store):
    a = store.ensure_group("g-a", "t-1")["conversation_id"]
    b = store.ensure_group("g-b", "t-2")["conversation_id"]
    store.join_group("g-a", "t-3", "agent")
    store.append_message(a, "user", "find shows")
    assert store.close_group("g-a") == a
    assert store.conversation(a)["status"] == "closed" and store.group_tabs("g-a") == []
    assert [m["content"] for m in store.messages(a)] == ["find shows"]
    assert store.conversation(b)["status"] == "open" and [t["tab_id"] for t in store.group_tabs("g-b")] == ["t-2"]
    assert store.close_group("g-a") is None  # closing twice is harmless


def test_restoring_a_closed_group_continues_its_conversation(store):
    a = store.ensure_group("g-a", "t-1")["conversation_id"]
    store.append_message(a, "user", "find shows")
    store.close_group("g-a")
    again = store.ensure_group("g-a", "t-9")["conversation_id"]
    assert again == a and store.conversation(a)["status"] == "open"
    assert store.conversation(a)["compaction_status"] == "none"


def test_closing_a_worker_tab_keeps_the_parent_conversation(store):
    cid = store.ensure_group("g-a", "t-main")["conversation_id"]
    store.join_group("g-a", "t-worker", "agent")
    assert store.remove_tab("t-worker") is None
    assert store.conversation(cid)["status"] == "open"


def _orch():
    return MultiAgentOrchestrator(tool_service=MagicMock(spec=ComexToolService), lease_registry=ServerTabLeaseRegistry(),
                                  target_registry=ServerTabTargetRegistry())


def _slow_task(task_id, started, finish_after=0.3):
    async def fn(ctx, svc):
        started.add(task_id)
        await asyncio.sleep(finish_after)
        return WorkerResult(findings=f"{task_id} done", success=True)
    return OrchestratorTask(id=task_id, description=task_id, task_fn=fn)


async def test_closing_a_worker_tab_stops_only_that_worker():
    orch, started = _orch(), set()
    run = orch.create_run("compare", [_slow_task("a", started), _slow_task("b", started)], group_id="g-a")
    job = asyncio.create_task(orch.execute_run(run))
    while len(started) < 2:
        await asyncio.sleep(0.01)
    tab_a = run.tasks["a"].assigned_tab_id
    assert orch.cancel_tab(tab_a) == ["a"]
    res = await job
    assert run.tasks["a"].status == TaskStatus.CANCELLED and run.tasks["a"].error == "Its tab was closed."
    assert run.tasks["b"].status == TaskStatus.COMPLETED and "b done" in res.final_answer
    assert run.status != RunStatus.CANCELLED
    assert orch.cancel_tab("tab-that-does-not-exist") == []


async def test_closing_a_group_cancels_its_runs_and_not_the_other_groups():
    orch, started = _orch(), set()
    mine = orch.create_run("x", [_slow_task("a", started, 1.0)], group_id="g-a")
    other = orch.create_run("y", [_slow_task("b", started, 0.2)], group_id="g-b")
    jobs = [asyncio.create_task(orch.execute_run(mine)), asyncio.create_task(orch.execute_run(other))]
    while len(started) < 2:
        await asyncio.sleep(0.01)
    assert orch.cancel_group("g-a") == [mine.id]
    await asyncio.gather(*jobs)
    assert mine.status == RunStatus.CANCELLED and other.status == RunStatus.COMPLETED


def test_single_agent_tasks_are_stopped_by_tab_or_group_only():
    a, b = MagicMock(done=MagicMock(return_value=False)), MagicMock(done=MagicMock(return_value=False))
    with patch.dict(A.active_tasks, {"t1": a, "t2": b}, clear=True), \
         patch.dict(A.active_task_scope, {"t1": {"group_id": "g-a", "tab_ids": {"tab-1"}},
                                          "t2": {"group_id": "g-b", "tab_ids": {"tab-2"}}}, clear=True):
        assert A._stop_single_agents(tab_id="tab-1") == ["t1"]
        a.cancel.assert_called_once()
        b.cancel.assert_not_called()
        assert A._stop_single_agents(group_id="g-b") == ["t2"]


def test_the_stop_endpoints_are_for_the_app_only():
    client = TestClient(A.app)
    assert client.post("/agent/tabs/tab-1/stop").status_code == 403
    assert client.post("/chat/groups/g-a/close").status_code == 403
    with patch.object(A, "_INTERNAL_APP_TOKEN", "secret-for-test"):
        hdr = {"X-Comex-Internal-Token": "secret-for-test"}
        assert client.post("/agent/tabs/bad id!/stop", headers=hdr).status_code in (400, 404)
        r = client.post("/agent/tabs/tab-1/stop", headers=hdr)
        assert r.status_code == 200 and set(r.json()) == {"stopped_workers", "stopped_tasks"}
        r = client.post("/chat/groups/g-zz-unknown/close", headers=hdr)
        assert r.status_code == 200 and r.json()["closed_conversation_id"] is None


def test_a_tab_joining_a_closed_group_reopens_its_chat():
    from services.chat_store import get_chat_store
    client = TestClient(A.app)
    store = get_chat_store()
    cid = store.ensure_group("g-undo", "t-1")["conversation_id"]
    store.close_group("g-undo")
    assert client.post("/chat/groups/join", json={"group_id": "g-undo", "tab_id": "t-2", "role": "link"}).status_code == 200
    assert store.conversation(cid)["status"] == "open"
    assert [t["tab_id"] for t in store.group_tabs("g-undo")] == ["t-2"]


def test_a_reply_after_the_group_closed_is_kept_without_reopening_the_chat(store):
    """Found live: a run stopped by closing its group stored its "Stopped" reply and reopened the chat halfway."""
    cid = store.ensure_group("g-a", "t-1")["conversation_id"]
    store.append_message(cid, "user", "find shows")
    store.close_group("g-a")
    store.set_compaction(cid, "done", "summary")
    store.append_message(cid, "assistant", "Stopped.")
    conv = store.conversation(cid)
    assert conv["status"] == "closed" and conv["compaction_status"] == "pending"
    assert [m["content"] for m in store.messages(cid)] == ["find shows", "Stopped."]


async def test_a_worker_stopped_by_its_tab_does_not_cut_the_others_short():
    """Found live: the straggler rule timed the last worker against one that was stopped after 6 s."""
    from services import orchestrator as O
    orch, started, rushed = _orch(), set(), []

    async def patient(ctx, svc):
        started.add("b")
        await asyncio.sleep(0.8)
        rushed.append(ctx.metadata["soft_stop"].is_set())  # was it asked to wrap up early?
        return WorkerResult(findings="b done", success=True)

    tasks = [_slow_task("a", started, 5.0), OrchestratorTask(id="b", description="b", task_fn=patient)]
    run = orch.create_run("compare", tasks, group_id="g-a")
    with patch.object(O, "STRAGGLER_MIN_GRACE_S", 0.05), patch.object(O, "STRAGGLER_GRACE_FACTOR", 0.1):
        job = asyncio.create_task(orch.execute_run(run))
        while len(started) < 2:
            await asyncio.sleep(0.01)
        orch.cancel_tab(run.tasks["a"].assigned_tab_id)
        res = await job
    assert rushed == [False]
    assert run.tasks["b"].status == TaskStatus.COMPLETED and "b done" in res.final_answer


def test_the_same_run_id_in_two_conversations_stores_both_turns(store):
    """Found live: message ids were global, so a run id seen in another chat dropped this chat's turn silently."""
    from services.conversation import TurnRecorder
    a = store.ensure_group("g-a", "t-1")["conversation_id"]
    b = store.ensure_group("g-b", "t-2")["conversation_id"]
    for cid in (a, b):
        TurnRecorder.open(store, cid, "task-1", "hello").finish("hi there", "completed")
    assert [m["content"] for m in store.messages(a)] == ["hello", "hi there"]
    assert [m["content"] for m in store.messages(b)] == ["hello", "hi there"]
    TurnRecorder.open(store, a, "task-1", "hello")  # a retried write of the same turn stays single
    assert len(store.messages(a)) == 2
