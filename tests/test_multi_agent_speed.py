"""Multi-agent speed mechanisms: planner read_urls, prefetch before the first model call, straggler policy."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

import agent_service as A
import services.orchestrator as O
from nervous.action_policy import ServerTabLeaseRegistry, ServerTabTargetRegistry
from services.orchestrator import (
    MultiAgentOrchestrator,
    OrchestratorTask,
    WorkerResult,
    _parse_decomposition_response,
    build_worker_brief,
)
from services.tool_service import ComexToolService, ToolResult


@pytest.fixture(autouse=True)
def _isolate_service_singletons():
    saved = (A._comex_tool_service, A._orchestrator_instance)
    yield
    A._comex_tool_service, A._orchestrator_instance = saved


def _plan(*items, follow_up=None):
    return json.dumps({"subtasks": list(items), "follow_up_action": follow_up})


def test_planner_read_urls_are_validated_deduplicated_and_bounded():
    plan = _parse_decomposition_response(_plan(
        {"id": "surveys", "objective": "Survey papers", "collect": "title, link",
         "read_urls": ["https://arxiv.org/search/?query=survey+multi+agent&searchtype=all",
                       "file:///etc/passwd", "javascript:alert(1)", "http://127.0.0.1:8000/health", "http://localhost:20128/v1",
                       "https://scholar.google.com/scholar?q=survey", "https://example.com/a", "https://example.com/b"]},
        {"id": "systems", "objective": "Framework papers",
         "read_urls": ["https://arxiv.org/search/?query=survey+multi+agent&searchtype=all#top", "https://openreview.net/search?term=agents"]},
    ), max_tasks=4)
    a, b = plan.tasks
    ra = a.metadata["package"]["read_urls"]
    assert ra == ["https://arxiv.org/search/?query=survey+multi+agent&searchtype=all",
                  "https://scholar.google.com/scholar?q=survey", "https://example.com/a"], "unsafe URLs dropped, at most 3 kept"
    assert a.url == ra[0], "the tab opens on the first page to read"
    assert b.metadata["package"]["read_urls"] == ["https://openreview.net/search?term=agents"], "a page another package reads is not read twice"


def test_planner_without_urls_still_works_and_old_url_field_is_honoured():
    plan = _parse_decomposition_response(_plan({"id": "x", "objective": "Something", "url": "https://example.com/search?q=x"}), 4)
    t = plan.tasks[0]
    assert t.metadata["package"]["read_urls"] == [] and t.url == "https://example.com/search?q=x"


def test_brief_tells_the_worker_its_pages_are_already_read_and_to_answer_if_enough():
    a = OrchestratorTask(id="a", description="Survey papers", url="https://arxiv.org/x",
                         metadata={"package": {"read_urls": ["https://arxiv.org/x", "https://scholar.google.com/y"], "collect": "title, link"}})
    b = OrchestratorTask(id="b", description="Benchmarks")
    brief = build_worker_brief("Best papers", a, [a, b])
    assert "PAGES ALREADY READ FOR YOU" in brief and "https://scholar.google.com/y" in brief
    assert "write your final answer NOW" in brief and "ONE browser_sequence" in brief
    assert "start there" not in brief
    plain = build_worker_brief("Best papers", b, [a, b])
    assert "PAGES ALREADY READ" not in plain and "Run a search" in plain


class _FakeSvc:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    async def navigate(self, ctx, url):
        self.calls.append(("navigate", url))
        return ToolResult.ok(data={}) if self.pages.get(url) is not None else ToolResult.fail("OPERATION_FAILED", "net::ERR_NAME_NOT_RESOLVED")

    async def wait_for(self, ctx, cond, timeout):
        self.calls.append(("wait", cond["type"]))
        return ToolResult.ok(data={"met": True})

    async def extract(self, ctx, selector, max_chars):
        self.calls.append(("extract", max_chars))
        url = [c for c in self.calls if c[0] == "navigate"][-1][1]
        return ToolResult.ok(data=self.pages[url])


async def test_prefetch_reads_pages_in_order_and_wraps_them_as_untrusted_data():
    pages = {"https://a.example/s": {"title": "A results", "url": "https://a.example/s", "text": "Paper One by X (2024)", "truncated": False,
                                     "length": 21, "links": [{"text": "Paper One", "href": "https://a.example/p1"}]},
             "https://b.example/s": {"title": "B results", "url": "https://b.example/s", "text": "Paper Two", "truncated": True, "length": 9000, "links": []}}
    svc, events = _FakeSvc(pages), []

    async def emit(kind, data):
        events.append((kind, data.get("label")))

    text, meta = await A._prefetch_pages(svc, object(), list(pages), emit)
    assert [c for c in svc.calls if c[0] == "navigate"] == [("navigate", u) for u in pages]
    assert text.startswith("\n\n[UNTRUSTED DATA START") and text.rstrip().endswith("[UNTRUSTED DATA END]")
    assert "Page 1: A results" in text and "Paper One -> https://a.example/p1" in text and "text cut at" in text
    assert meta["pages_read"] == 2 and meta["notes"] == []
    assert events[0] == ("step", "Reading a.example, b.example") and events[-1][0] == "step_done"


async def test_prefetch_survives_a_page_that_fails_and_when_nothing_loads():
    svc = _FakeSvc({"https://ok.example/": {"title": "ok", "url": "https://ok.example/", "text": "fine", "links": []}, "https://bad.example/": None})
    text, meta = await A._prefetch_pages(svc, object(), ["https://bad.example/", "https://ok.example/"], AsyncMock())
    assert meta["pages_read"] == 1 and "bad.example" in meta["notes"][0] and "Pages that could not be read" in text
    none_text, none_meta = await A._prefetch_pages(_FakeSvc({"https://bad.example/": None}), object(), ["https://bad.example/"], AsyncMock())
    assert none_meta["pages_read"] == 0 and "Begin by browsing as usual" in none_text and "UNTRUSTED" not in none_text


def _orch():
    return MultiAgentOrchestrator(tool_service=MagicMock(spec=ComexToolService), lease_registry=ServerTabLeaseRegistry(),
                                  target_registry=ServerTabTargetRegistry(), llm=MagicMock(ainvoke=AsyncMock(return_value=MagicMock(content="merged"))))


async def test_straggler_is_asked_to_wrap_up_once_the_others_finish(monkeypatch):
    monkeypatch.setattr(O, "STRAGGLER_MIN_GRACE_S", 0.3)
    monkeypatch.setattr(O, "STRAGGLER_GRACE_FACTOR", 0.0)
    seen = {}

    def quick(name):
        async def fn(ctx, svc):
            await asyncio.sleep(0.1)
            return WorkerResult(findings=name, success=True)
        return fn

    async def slow(ctx, svc):
        stop = ctx.metadata["soft_stop"]
        t0 = asyncio.get_running_loop().time()
        await asyncio.wait_for(stop.wait(), timeout=5)       # a worker that would otherwise run for a long time
        seen["waited"] = asyncio.get_running_loop().time() - t0
        return WorkerResult(findings="partial", success=True, stopped_early="the other agents have finished")

    orch = _orch()
    run = orch.create_run("q", [OrchestratorTask(id="a", description="A", task_fn=quick("a")),
                                OrchestratorTask(id="b", description="B", task_fn=quick("b")),
                                OrchestratorTask(id="c", description="C", task_fn=slow)])
    result = await asyncio.wait_for(orch.execute_run(run), timeout=8)
    assert 0.3 <= seen["waited"] < 2.0, "grace period applied, then the straggler was told to wrap up"
    assert result.timing["workers"]["c"]["stopped_early"] == "the other agents have finished"
    assert all(t.status.value == "completed" for t in run.tasks.values()), "partial findings are kept, nobody is failed"


async def test_no_soft_stop_when_workers_finish_together_or_run_alone(monkeypatch):
    monkeypatch.setattr(O, "STRAGGLER_MIN_GRACE_S", 0.2)
    flags = []

    def worker(delay):
        async def fn(ctx, svc):
            await asyncio.sleep(delay)
            flags.append(ctx.metadata["soft_stop"].is_set())
            return WorkerResult(findings="x", success=True)
        return fn

    orch = _orch()
    run = orch.create_run("q", [OrchestratorTask(id="a", description="A", task_fn=worker(0.05)),
                                OrchestratorTask(id="b", description="B", task_fn=worker(0.05))])
    await orch.execute_run(run)
    solo = orch.create_run("q", [OrchestratorTask(id="s", description="S", task_fn=worker(0.05))])
    await orch.execute_run(solo)
    assert flags == [False, False, False]


async def test_worker_context_carries_prefetch_urls_to_the_loop(monkeypatch):
    captured = {}

    async def fake_loop(**kw):
        captured.update(kw)
        return A.AgentLoopResult("### Findings\n- x", {"timing": {"llm_roundtrips_ms": [900.0]}, "tool_call_count": 0, "tool_traces": []})
    monkeypatch.setattr(A, "execute_agent_loop", fake_loop)
    ctx = MagicMock(worker_id="w1", target_tab_id="t1", lease=MagicMock(lease_token="tok"), deadline_mono=123.0,
                    metadata={"prefetch_urls": ["https://a.example/s"], "soft_stop": asyncio.Event(), "report_progress": None})
    res = await A.make_worker_task_fn("brief")(ctx, MagicMock())
    assert res.success and captured["prefetch_urls"] == ["https://a.example/s"] and isinstance(captured["soft_stop"], asyncio.Event)


async def test_real_loop_puts_prefetched_pages_in_the_first_model_message():
    """Drives the real execute_agent_loop (fake model) so the message assembly line itself is exercised."""
    from unittest.mock import patch
    from langchain_core.messages import AIMessage
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="### Findings\n- done", tool_calls=[]))
    llm.bind_tools = MagicMock(return_value=llm)
    block = "\n\n[UNTRUSTED DATA START: pages already read]\nPage 1: Results (https://a.example/s)\nPaper One\n[UNTRUSTED DATA END]"
    fake = AsyncMock(return_value=(block, {"urls": ["https://a.example/s"], "pages_read": 1, "ms": 7.0, "notes": []}))
    with patch.object(A, "ChatOpenAI", return_value=llm), patch.object(A, "_make_agent_loop_context", return_value=MagicMock()), \
         patch.object(A, "_build_browser_tools", return_value=[]), patch.object(A, "_prefetch_pages", fake):
        res = await A.execute_agent_loop(task="BRIEF", default_cdp_url="http://x", use_graph=False, trusted_app_context=True,
                                         tool_service=MagicMock(), prefetch_urls=["https://a.example/s"])
    sent = llm.ainvoke.await_args.args[0]
    human = [m for m in sent if getattr(m, "type", "") == "human"][-1].content
    assert human.startswith("BRIEF") and "Page 1: Results" in human and human.rstrip().endswith("[UNTRUSTED DATA END]")
    assert res.metadata["prefetch"]["pages_read"] == 1 and res.metadata["timing"]["prefetch_ms"] == 7.0
    fake.assert_awaited_once()
    assert fake.await_args.args[2] == ["https://a.example/s"]


async def test_real_loop_without_prefetch_is_unchanged():
    from unittest.mock import patch
    from langchain_core.messages import AIMessage
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="ok", tool_calls=[]))
    llm.bind_tools = MagicMock(return_value=llm)
    pre = AsyncMock()
    with patch.object(A, "ChatOpenAI", return_value=llm), patch.object(A, "_make_agent_loop_context", return_value=MagicMock()), \
         patch.object(A, "_build_browser_tools", return_value=[]), patch.object(A, "_prefetch_pages", pre):
        res = await A.execute_agent_loop(task="hello there", default_cdp_url="http://x", use_graph=False, trusted_app_context=True,
                                         tool_service=MagicMock())
    pre.assert_not_awaited()
    assert "prefetch" not in res.metadata


async def test_soft_stop_makes_the_loop_answer_from_what_it_has_without_more_browsing():
    from unittest.mock import patch
    from langchain_core.messages import AIMessage
    stop = asyncio.Event()
    stop.set()
    calls = []

    @A.tool
    async def browser_extract(selector: str = "") -> str:
        """Read the page."""
        calls.append(selector)
        return "text"

    llm = MagicMock()
    # the soft stop is already set, so the very first (and only) model turn must be the tool-less final answer
    llm.ainvoke = AsyncMock(side_effect=[AIMessage(content="### Findings\n- partial", tool_calls=[])])
    llm.bind_tools = MagicMock(return_value=llm)
    with patch.object(A, "ChatOpenAI", return_value=llm), patch.object(A, "_make_agent_loop_context", return_value=MagicMock()), \
         patch.object(A, "_build_browser_tools", side_effect=lambda **kw: [browser_extract]):
        res = await A.execute_agent_loop(task="research", default_cdp_url="http://x", use_graph=False, trusted_app_context=True,
                                         tool_service=MagicMock(), soft_stop=stop)
    assert calls == [], "no browser action may run once the soft stop is set"
    assert "other agents have finished" in res.metadata["stopped_early"] and "partial" in str(res)


class _SlowSvc(_FakeSvc):
    current = "https://start.example/s"  # the tab was opened on this page

    async def navigate(self, ctx, url):
        self.calls.append(("navigate", url))
        if "slow" in url:
            await asyncio.sleep(30)
        self.current = url
        return ToolResult.ok(data={})

    async def extract(self, ctx, selector, max_chars):
        return ToolResult.ok(data=self.pages[self.current])


async def test_prefetch_gives_each_page_a_hard_budget_and_never_renavigates_the_start_page(monkeypatch):
    monkeypatch.setattr(A, "PREFETCH_PAGE_BUDGET_S", 0.4)
    pages = {"https://start.example/s": {"title": "S", "url": "https://start.example/s", "text": "start page", "links": []},
             "https://slow.example/s": {"title": "slow", "url": "https://slow.example/s", "text": "SLOWPAGE", "links": []},
             "https://fast.example/s": {"title": "F", "url": "https://fast.example/s", "text": "fast page", "links": []}}
    svc = _SlowSvc(pages)
    t0 = asyncio.get_running_loop().time()
    text, meta = await A._prefetch_pages(svc, object(), list(pages), AsyncMock(), start_url="https://start.example/s#x")
    took = asyncio.get_running_loop().time() - t0
    assert took < 5, "a slow site must not hold the worker up"
    navs = [c[1] for c in svc.calls if c[0] == "navigate"]
    assert "https://start.example/s" not in navs, "the tab is already loading its start page: do not navigate to it again"
    assert meta["pages_read"] == 2 and "start page" in text and "fast page" in text and "SLOWPAGE" not in text
    assert any("slow.example" in n and "no response within" in n for n in meta["notes"])
    assert [st.get("skipped") for st in meta["steps"]] == [None, "timeout", None]

