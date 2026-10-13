"""New sequence steps (keys, pointer, drag, select, wait, evaluate) and conditions, against real pages."""

from __future__ import annotations

import asyncio

import pytest

from nervous.cdp_session import _GLOBAL_SESSIONS
from services.tool_service import ToolErrorCode, _parse_and_validate_sequence
from tests.browser_lab import BrowserLab, find_chrome
from tests.test_page_tools_service import Rig, rig, lab  # noqa: F401  (fixtures)

pytestmark = pytest.mark.skipif(find_chrome() is None, reason="no Chrome/Chromium installed")


def test_new_steps_validate_strictly():
    ok, err = _parse_and_validate_sequence([
        {"action": "keys", "keys": ["Enter"], "text": "abc"},
        {"action": "click_at", "x": 10, "y": 20, "postconditions": [{"type": "js_true", "expected": "1 === 1"}]},
        {"action": "drag", "x": 1, "y": 2, "to_x": 30, "to_y": 40},
        {"action": "select", "selector": "select", "value": "100"},
        {"action": "wait", "condition": {"type": "idle"}, "timeout_ms": 2000},
        {"action": "evaluate", "expression": "document.title"},
        {"action": "scroll", "to": "bottom"},
    ])
    assert err is None and len(ok) == 7 and ok[0].keys == ("Enter",) and ok[2].to_x == 30.0
    bad = [
        ([{"action": "click_at", "x": 10}], "finite number 'y'"),
        ([{"action": "click_at", "x": float("nan"), "y": 1}], "finite number 'x'"),
        ([{"action": "drag", "x": 1, "y": 2}], "'to_x'"),
        ([{"action": "keys", "keys": ["Hyper+q"]}], "unknown modifier"),
        ([{"action": "keys"}], "at least one key"),
        ([{"action": "scroll"}], "needs delta_y"),
        ([{"action": "scroll", "to": "middle"}], "'top' or 'bottom'"),
        ([{"action": "select", "value": "1"}], "requires 'selector'"),
        ([{"action": "wait", "condition": {"type": "sleep"}}], "must be an object with type"),
        ([{"action": "wait", "condition": {"type": "idle"}, "timeout_ms": 5}], "between 100 and 30000"),
        ([{"action": "evaluate"}], "requires 'expression'"),
        ([{"action": "click_at", "x": 1, "y": 1, "selector": "#a"}], "unknown fields"),
        ([{"action": "click_at", "x": 1, "y": 1, "postconditions": [{"type": "js_true"}]}], "requires 'expected'"),
        ([{"action": "click_at", "x": 1, "y": 1, "postconditions": [{"type": "element_hidden"}]}], "requires 'selector'"),
    ]
    for steps, needle in bad:
        _, e = _parse_and_validate_sequence(steps)
        assert e and needle in e, (steps, e)


async def _centres(rig, ctx, expr):
    return await rig.js(ctx, expr)


async def test_chess_mate_is_one_call_with_a_verified_outcome(rig):
    await rig.open("chess.html")
    ctx = rig.ctx()
    left, top = await rig.js(ctx, "(() => { const r = document.querySelector('#board').getBoundingClientRect(); return [r.left, r.top]; })()")
    res = await rig.service.perform_sequence(ctx, [
        {"action": "click_at", "x": left + 30, "y": top + 7 * 60 + 30},
        {"action": "click_at", "x": left + 30, "y": top + 30, "postconditions": [{"type": "text_contains", "expected": "Checkmate"}]},
    ])
    assert res.success, (res.error_message, res.evidence)
    assert res.data["step_count"] == 2 and res.data["completed_steps"][1]["data"]["target"]["id"] == "board"
    assert await rig.js(ctx, "__game.status") == "checkmate"


async def test_failed_postcondition_stops_the_batch_and_reports_what_ran(rig):
    await rig.open("chess.html")
    ctx = rig.ctx()
    left, top = await rig.js(ctx, "(() => { const r = document.querySelector('#board').getBoundingClientRect(); return [r.left, r.top]; })()")
    res = await rig.service.perform_sequence(ctx, [
        {"action": "click_at", "x": left + 30, "y": top + 7 * 60 + 30},                 # select the rook
        {"action": "click_at", "x": left + 4 * 60 + 30, "y": top + 30,                   # e8: not a rook move, nothing happens
         "postconditions": [{"type": "text_contains", "expected": "Checkmate"}]},
        {"action": "click_at", "x": left + 30, "y": top + 30},                          # must NOT run
    ])
    assert not res.success and res.error_code == ToolErrorCode.OPERATION_FAILED.value
    ev = res.evidence
    assert ev["failed_step_index"] == 1 and ev["condition_stage"] == "postcondition" and ev["side_effect_possible"] is True
    assert [c["step_index"] for c in ev["completed_steps"]] == [0, 1]
    assert await rig.js(ctx, "__game.history.length") == 0, "the third step must not have run"


async def test_word_game_in_one_call_with_js_postcondition(rig):
    await rig.open("wordle.html?seed=1")  # secret: slate
    ctx = rig.ctx()
    res = await rig.service.perform_sequence(ctx, [
        {"action": "keys", "text": "slate", "keys": ["Enter"],
         "postconditions": [{"type": "js_true", "expected": "document.querySelector('#game').dataset.status === 'won'"}]},
    ])
    assert res.success, (res.error_message, res.evidence)
    assert await rig.js(ctx, "document.querySelector('#message').textContent") == "You won in 1"


async def test_drawing_with_keys_and_drags_in_one_call(rig):
    await rig.open("draw.html")
    ctx = rig.ctx()
    cx, cy = await rig.js(ctx, "(() => { const r = document.querySelector('#c').getBoundingClientRect(); return [r.left, r.top]; })()")
    res = await rig.service.perform_sequence(ctx, [
        {"action": "keys", "keys": ["r"]},
        {"action": "drag", "x": cx + 200, "y": cy + 120, "to_x": cx + 600, "to_y": cy + 420},
        {"action": "keys", "keys": ["o"]},
        {"action": "drag", "x": cx + 300, "y": cy + 200, "to_x": cx + 500, "to_y": cy + 340,
         "postconditions": [{"type": "js_true", "expected": "window.__scene.length === 2"}]},
    ])
    assert res.success, (res.error_message, res.evidence)
    assert await rig.js(ctx, "window.__scene.map(s => s.type).join(',')") == "rectangle,ellipse"


async def test_select_then_wait_then_evaluate_reads_the_table_state(rig):
    await rig.open("grades.html")
    ctx = rig.ctx()
    res = await rig.service.perform_sequence(ctx, [
        {"action": "select", "selector": "select[name=gradeTable_length]", "value": "100",
         "postconditions": [{"type": "text_contains", "expected": "Showing 1 to 57 of 57"}]},
        {"action": "wait", "condition": {"type": "idle", "quiet_ms": 150}},
        {"action": "evaluate", "expression": "document.querySelectorAll('#gradeTable tbody tr').length"},
    ])
    assert res.success, (res.error_message, res.evidence)
    assert res.data["completed_steps"][2]["data"]["value"] == 57


async def test_hidden_and_absent_conditions(rig):
    await rig.open("wordle.html?seed=1")
    ctx = rig.ctx()
    res = await rig.service.perform_sequence(ctx, [
        {"action": "keys", "text": "zzzzz", "keys": ["Enter"],
         "postconditions": [{"type": "text_contains", "expected": "Not in word list"}, {"type": "text_absent", "expected": "You won"},
                            {"type": "element_hidden", "selector": "#no-such-element"}]},
    ])
    assert res.success, (res.error_message, res.evidence)


async def test_each_new_step_is_authorized_under_its_own_operation(rig):
    await rig.open("wordle.html")
    limited = rig.ctx(permitted_operations={"perform_sequence", "inspect", "extract", "click", "type", "navigate"})
    res = await rig.service.perform_sequence(limited, [{"action": "keys", "keys": ["a"]}])
    assert not res.success and res.error_code == ToolErrorCode.UNAUTHORIZED.value
    assert "press_keys" in res.error_message or "not permitted" in res.error_message.lower() or res.evidence["condition_stage"] == "authorization"
    assert res.evidence["action_dispatched"] is False
    live = rig.ctx()
    assert await rig.js(live, "document.querySelectorAll('.tile')[0].textContent") == ""


async def test_pointer_step_outside_the_viewport_is_refused_before_dispatch(rig):
    await rig.open("chess.html")
    ctx = rig.ctx()
    res = await rig.service.perform_sequence(ctx, [{"action": "click_at", "x": 99999, "y": 5}])
    assert not res.success and "outside" in res.error_message
    assert res.evidence["action_dispatched"] is False
