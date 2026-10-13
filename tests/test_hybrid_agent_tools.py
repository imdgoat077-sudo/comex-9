"""Agent-side wiring of the hybrid tools: tool lists, screenshot delivery, result text, labels."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

import agent_service as A
from services.tool_service import ToolErrorCode, ToolResult

FULL = {"browser_click", "browser_type", "browser_navigate", "browser_extract", "browser_inspect", "browser_find", "browser_sequence",
        "browser_observe", "browser_screenshot", "browser_evaluate", "browser_read_table", "browser_select", "browser_wait",
        "browser_scroll", "browser_keys", "browser_pointer"}
RESEARCH = {"browser_click", "browser_type", "browser_navigate", "browser_extract", "browser_inspect", "browser_find", "browser_sequence",
            "browser_read_table", "browser_evaluate", "browser_select", "browser_scroll", "browser_wait"}


def _tools(svc, sink=None, profile="full"):
    return {t.name: t for t in A._build_browser_tools(
        _svc=svc, _svc_ctx=MagicMock(), image_sink=sink, profile=profile, tab_id="active_tab", step_ref={"value": 0})}


def test_tool_lists_per_profile():
    assert set(_tools(MagicMock())) == FULL | {"run_browser_harness"}
    research = set(_tools(MagicMock(), profile="research"))
    assert research == RESEARCH | {"run_browser_harness"}, "every agent gets the harness, research workers included"
    assert not research & {"browser_pointer", "browser_keys", "browser_screenshot"}, "workers read pages; they do not play games"


async def test_screenshot_tool_queues_the_image_and_returns_text_only():
    svc = MagicMock()
    svc.screenshot = AsyncMock(return_value=ToolResult.ok(data={
        "image_base64": "QUJD", "mime": "image/jpeg", "screenshot_id": "ab12cd34", "width": 1000, "height": 600,
        "viewport": {"width": 1280, "height": 768, "scroll_x": 0, "scroll_y": 40, "dpr": 1.0}}))
    sink: list = []
    out = await _tools(svc, sink)["browser_screenshot"].ainvoke({})
    assert "ab12cd34" in out and "QUJD" not in out, "base64 must never be put into the model's text"
    assert sink == [{"id": "ab12cd34", "b64": "QUJD", "mime": "image/jpeg", "width": 1000, "height": 600}]


def test_screenshots_become_images_and_only_the_newest_stays_one():
    messages = [HumanMessage(content="task")]
    sink = [{"id": "s1", "b64": "AAA", "mime": "image/jpeg", "width": 10, "height": 10}]
    A._attach_screenshots(messages, sink)
    assert sink == [] and messages[-1].content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,AAA")
    messages.append(ToolMessage(content="clicked", tool_call_id="x"))
    sink.append({"id": "s2", "b64": "BBB", "mime": "image/jpeg", "width": 10, "height": 10})
    A._attach_screenshots(messages, sink)
    shots = [m for m in messages if (m.additional_kwargs or {}).get("comex_screenshot")]
    assert [m.additional_kwargs["comex_screenshot"] for m in shots] == ["dropped", "live"]
    assert isinstance(shots[0].content, str) and "omitted" in shots[0].content and "AAA" not in shots[0].content
    assert shots[1].content[1]["image_url"]["url"].endswith("BBB")


async def test_pointer_result_names_what_was_hit_and_failures_pass_through():
    svc = MagicMock()
    svc.pointer = AsyncMock(return_value=ToolResult.ok(data={
        "kind": "click", "x": 120.0, "y": 80.0, "page_changed": True,
        "target": {"found": True, "tag": "button", "id": "add", "class": "btn primary", "label": "Add to cart"}}))
    out = await _tools(svc)["browser_pointer"].ainvoke({"action": "click", "x": 120, "y": 80})
    assert "button#add.btn" in out and "'Add to cart'" in out and "Page changed: yes" in out
    svc.pointer = AsyncMock(return_value=ToolResult.fail(ToolErrorCode.ACTION_BLOCKED, "Nothing was clicked because the page scrolled"))
    out = await _tools(svc)["browser_pointer"].ainvoke({"action": "click", "x": 1, "y": 1, "screenshot_id": "old"})
    assert out.startswith("[ACTION_BLOCKED]") and A.classify_tool_result(out)[0] is True


async def test_read_table_tool_says_when_the_table_is_not_complete():
    svc = MagicMock()
    svc.read_table = AsyncMock(return_value=ToolResult.ok(data={"count": 1, "complete": False, "tables": [{
        "index": 0, "caption": "Grades", "headers": ["Code", "Grade"], "rows": [["A1", "S"], ["B2", "A"]], "total_rows": 10,
        "columns": 2, "start_row": 0, "next_start_row": 2,
        "completeness": {"complete": False, "notes": ["The page says it is showing 1 to 10 of 57."]}}]}))
    out = await _tools(svc)["browser_read_table"].ainvoke({})
    assert "| Code | Grade |" in out and "| A1 | S |" in out
    assert "COMPLETE: NO" in out and "1 to 10 of 57" in out and "start_row=2" in out


async def test_evaluate_tool_formats_values_and_reports_cut_output():
    svc = MagicMock()
    svc.evaluate = AsyncMock(return_value=ToolResult.ok(data={"value": [1, "a"], "truncated": False, "chars": 6}))
    assert await _tools(svc)["browser_evaluate"].ainvoke({"expression": "x"}) == '[1, "a"]'
    svc.evaluate = AsyncMock(return_value=ToolResult.ok(data={"value": "xxxx", "truncated": True, "chars": 90000}))
    out = await _tools(svc)["browser_evaluate"].ainvoke({"expression": "x", "max_chars": 4})
    assert "output cut" in out and "90000" in out


async def test_tools_fail_closed_without_a_service():
    out = await _tools(None)["browser_keys"].ainvoke({"keys": ["a"]}) if False else None
    tools = {t.name: t for t in A._build_browser_tools(_svc=None, _svc_ctx=None, legacy_mode=True, tab_id="t")}
    assert (await tools["browser_pointer"].ainvoke({"action": "click", "x": 1, "y": 1})).startswith("Error:")


def test_step_labels_are_plain_language():
    assert A.describe_step("browser_screenshot", {}) == "Taking a screenshot"
    assert A.describe_step("browser_keys", {"text": "crane", "keys": ["Enter"]}) == "Pressing “crane”"
    assert A.describe_step("browser_pointer", {"action": "drag"}) == "Dragging on the page"
    assert A.describe_step("browser_scroll", {"to": "bottom"}) == "Scrolling to the bottom"
    assert A.describe_step("browser_read_table", {}) == "Reading the table"


def test_prompt_teaches_when_to_use_which_path():
    p = A.SYSTEM_PROMPT
    for needle in ("browser_read_table", "COMPLETE: NO", "browser_evaluate", "browser_pointer", "screenshot_id", "postcondition"):
        assert needle in p, needle


def test_grid_inference_maps_pieces_to_cells():
    from nervous.page_strategy import describe_grid
    surface = {"tag": "div", "id": "board", "x": 24, "y": 24, "w": 480, "h": 480, "children_total": 3, "children": [
        {"c": "piece black king", "x": 384, "y": 24, "w": 60, "h": 60},
        {"c": "piece white rook", "x": 24, "y": 444, "w": 60, "h": 60},
        {"c": "piece white king", "x": 384, "y": 444, "w": 60, "h": 60}]}
    g = describe_grid(surface)
    assert (g["cell"], g["cols"], g["rows"], g["complete"]) == (60, 8, 8, True)
    assert {(i["c"], i["col"], i["row"]) for i in g["items"]} == {("piece black king", 6, 0), ("piece white rook", 0, 7), ("piece white king", 6, 7)}
    # not a grid: irregular children, or a surface that is not a whole number of cells
    assert describe_grid({**surface, "children": [{"c": "a", "x": 30, "y": 30, "w": 17, "h": 90}, {"c": "b", "x": 99, "y": 40, "w": 33, "h": 12}]}) is None
    assert describe_grid({**surface, "w": 470}) is None
    assert describe_grid(None) is None and describe_grid({"children": []}) is None


async def test_harness_runs_pinned_to_the_agents_own_tab_with_secrets_removed(tmp_path, monkeypatch):
    stub = tmp_path / "browser-harness"
    stub.write_text("#!/bin/sh\ncat\necho \"ROUTER_API_KEY=${ROUTER_API_KEY:-unset} BU_CDP_URL=$BU_CDP_URL\"\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    monkeypatch.setenv("ROUTER_API_KEY", "sk-secret")
    svc, ctx = MagicMock(), MagicMock(deadline_mono=None)
    harness = lambda: {t.name: t for t in A._build_browser_tools(
        _svc=svc, _svc_ctx=ctx, tab_id="active_tab", step_ref={"value": 0})}["run_browser_harness"]
    svc.tab_target = AsyncMock(return_value=ToolResult.ok(data={"target_id": "TAB123"}))
    out = await harness().ainvoke({"code": "print(page_info())"})
    assert "TAB123" in out and "print(page_info())" in out, "the code runs attached to the agent's own tab"
    assert "ROUTER_API_KEY=unset" in out and "sk-secret" not in out
    stub.write_text("#!/bin/sh\necho boom; exit 3\n")
    failed = await harness().ainvoke({"code": "raise SystemExit"})
    assert failed.startswith("Error:") and "boom" in failed, "a crashed program must count as a failed tool call"
    svc.tab_target = AsyncMock(return_value=ToolResult.fail(ToolErrorCode.OPERATION_FAILED, "no tab", retryable=False))
    assert "no tab" in await harness().ainvoke({"code": "print(1)"}), "no tab, no harness"


async def test_harness_calls_from_different_agents_run_side_by_side_on_separate_connections(tmp_path, monkeypatch):
    import asyncio, time
    stub = tmp_path / "browser-harness"
    stub.write_text("#!/bin/sh\ncat >/dev/null\nsleep 0.8\necho $BH_RUNTIME_DIR\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    svc, ctx = MagicMock(), MagicMock(deadline_mono=None)
    svc.tab_target = AsyncMock(return_value=ToolResult.ok(data={"target_id": "TAB"}))
    harness = {t.name: t for t in A._build_browser_tools(_svc=svc, _svc_ctx=ctx, tab_id="active_tab", step_ref={"value": 0})}["run_browser_harness"]
    t0 = time.monotonic()
    a, b = await asyncio.gather(harness.ainvoke({"code": "print(1)"}), harness.ainvoke({"code": "print(2)"}))
    assert time.monotonic() - t0 < 1.4, "two agents' calls must not wait for each other"
    assert a.strip() != b.strip() and "slot" in a and "slot" in b, "each call gets its own harness connection"
    compile(A._HARNESS_HELPERS, "<helpers>", "exec")
