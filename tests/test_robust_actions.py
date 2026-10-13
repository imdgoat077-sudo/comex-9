"""
Actions that used to report success while doing nothing, and tools that made the model waste a step.

Found in a real Amazon run: the agent clicked "Add to cart, shift, option, K", a label shops park off-screen at
left:-10000px for assistive technology. The click was dispatched at x=-9787, landed on nothing, and was reported as done.
"""

from __future__ import annotations

import asyncio

import pytest

from nervous.cdp_session import _GLOBAL_SESSIONS, TabSessionContext
from nervous.executor import SelectorClickExecutor
from nervous.page_io import MAX_KEYS_PER_CALL, PageIOError, normalize_wait_condition, parse_key_token, plan_keys, press_keys
from services.tool_service import ComexToolService, create_tool_execution_context
from tests.browser_lab import BrowserLab, find_chrome


# ── wait conditions: accept what models naturally write ───────────────────────────────────────────

@pytest.mark.parametrize("given, expected", [
    ({"type": "text", "expected": "Added"}, {"type": "text", "expected": "Added"}),
    ({"text": "Added to cart", "reason": "confirm"}, {"type": "text", "expected": "Added to cart"}),
    ({"text_gone": "Loading"}, {"type": "text_gone", "expected": "Loading"}),
    ({"selector": "#done"}, {"type": "selector", "selector": "#done"}),
    ({"url": "/checkout"}, {"type": "url_contains", "expected": "/checkout"}),
    ({"url_contains": "/cart"}, {"type": "url_contains", "expected": "/cart"}),
    ({"js": "window.ready"}, {"type": "js", "expression": "window.ready"}),
    ({"expected": "Done"}, {"type": "text", "expected": "Done"}),
])
def test_a_wait_condition_without_a_type_is_understood(given, expected):
    out = normalize_wait_condition(given)
    assert {k: out[k] for k in expected} == expected


def test_a_wait_with_nothing_to_wait_for_means_wait_until_the_page_settles():
    assert normalize_wait_condition({})["type"] == "idle"
    assert normalize_wait_condition({"reason": "let it settle"})["type"] == "idle"


@pytest.mark.parametrize("bad", ["Added to cart", None, 5, {"colour": "red"}])
def test_a_wait_condition_that_cannot_be_understood_is_refused_with_guidance(bad):
    with pytest.raises(PageIOError) as e:
        normalize_wait_condition(bad)
    assert e.value.code == "validation"


# ── typing text with browser_keys ─────────────────────────────────────────────────────────────────
# Found in a real run: browser_keys(text="1. Indian freedom fighters ...") failed with "empty key" on the first space,
# so the agent gave up on the site and tried five others.

def test_a_space_is_the_space_key_not_an_empty_key():
    spec = parse_key_token(" ")
    assert spec["key"] == " " and spec["code"] == "Space"


def test_short_text_with_spaces_and_newlines_is_typed_as_key_presses():
    plan = plan_keys([], "go left\nnow")
    assert [p["token"] for p in plan][:3] == ["g", "o", " "] and "Enter" in [p["token"] for p in plan]
    assert all("insert" not in p for p in plan)


def test_characters_with_no_key_are_inserted_instead_of_refused():
    plan = plan_keys([], "cost ₹173")
    assert [p["insert"] for p in plan if "insert" in p] == ["₹"]


def test_long_text_is_inserted_a_line_at_a_time_and_fits_in_one_call():
    paragraph = "\n".join(f"{i}. " + "Indian freedom fighters waged a long struggle. " * 3 for i in range(1, 6))
    plan = plan_keys([], paragraph)
    inserts = [p["insert"] for p in plan if "insert" in p]
    assert len(inserts) == 5 and inserts[0].startswith("1. Indian") and len(plan) <= MAX_KEYS_PER_CALL
    assert [p["token"] for p in plan].count("Enter") == 4


async def test_inserted_text_goes_through_insert_text_and_keys_through_key_events():
    sent = []

    class Cdp:
        async def send(self, method, params=None):
            sent.append((method, params))
            return {}

    out = await press_keys(Cdp(), plan_keys(["Tab"], "x" * 60), delay_ms=0)
    methods = [m for m, _ in sent]
    assert methods.count("Input.insertText") == 1 and "Input.dispatchKeyEvent" in methods
    assert out["count"] == 2


# ── a page that is usable must not be refused as "navigating" just because `load` is slow ───────────

def test_the_document_being_ready_clears_the_navigating_block():
    from nervous.world_state import WorldStateTracker
    tracker = WorldStateTracker(tab_id="t")
    tracker.handle_frame_navigated("https://ads.example/", is_main_frame=True)
    assert tracker.state.is_navigating
    tracker.handle_dom_content_loaded()
    assert not tracker.state.is_navigating


async def test_the_dom_content_event_reaches_the_tracker():
    session = TabSessionContext(tab_id="t", target_id="x", cdp_client=_Cdp({}))
    session.on_cdp_notification("Page.frameNavigated", {"frame": {"id": "f", "url": "https://slow.example/"}})
    session._apply_event_to_tracker("Page.frameNavigated", {"frame": {"id": "f", "url": "https://slow.example/"}})
    assert session.tracker.state.is_navigating
    session._apply_event_to_tracker("Page.domContentEventFired", {"timestamp": 1})
    assert not session.tracker.state.is_navigating


# ── the executor never fires a mouse event outside the visible page ───────────────────────────────

class _Cdp:
    def __init__(self, metrics):
        self.metrics = metrics

    async def send(self, method, params=None):
        if method == "Page.getLayoutMetrics":
            if isinstance(self.metrics, Exception):
                raise self.metrics
            return self.metrics
        return {}


def _executor(metrics):
    return SelectorClickExecutor(_Cdp(metrics), state=None, tab_id="t", target_id="x")


VIEW = {"cssVisualViewport": {"clientWidth": 1280, "clientHeight": 800}}


async def test_a_point_off_the_visible_page_is_refused_with_a_useful_message():
    for x, y in [(-9787.8, 381.5), (1400, 300), (200, -40), (200, 900)]:
        with pytest.raises(RuntimeError, match="outside the visible page"):
            await _executor(VIEW)._require_on_screen(x, y)


async def test_points_on_the_page_are_allowed_including_the_edges():
    for x, y in [(0, 0), (640, 400), (1280, 800)]:
        await _executor(VIEW)._require_on_screen(x, y)


async def test_if_the_page_size_is_unknown_the_click_proceeds_as_before():
    await _executor({})._require_on_screen(-9999, -9999)
    await _executor(RuntimeError("no session"))._require_on_screen(-9999, -9999)


# ── in a real browser ─────────────────────────────────────────────────────────────────────────────

needs_chrome = pytest.mark.skipif(find_chrome() is None, reason="no Chrome/Chromium installed")


@pytest.fixture(scope="module")
def lab():
    lab = BrowserLab.start()
    yield lab
    if lab:
        lab.stop()


class Rig:
    def __init__(self, lab):
        self.lab = lab
        self.page = None
        self.service = ComexToolService(target_resolver=self._resolve, allowed_cdp_hosts=["127.0.0.1", "localhost"])

    def _resolve(self, lease, target_tab, trusted):
        return self.page.target_id, self.page.ws_url, None

    async def open(self, name):
        _GLOBAL_SESSIONS.clear()
        self.page = self.lab.open(name)
        await asyncio.sleep(0.8)

    def ctx(self):
        return create_tool_execution_context(task_id="t-" + str(id(self)), trusted_server_context=True,
                                             target_tab="active_tab", timeout_seconds=30)

    async def js(self, ctx, expr):
        r = await self.service.evaluate(ctx, expr)
        assert r.success, r.error_message
        return r.data["value"]


@pytest.fixture
async def rig(lab):
    r = Rig(lab)
    yield r
    for s in list(_GLOBAL_SESSIONS.values()):
        try:
            await s.stop()
            await s.cdp.close()
        except Exception:
            pass
    _GLOBAL_SESSIONS.clear()


@needs_chrome
async def test_an_offscreen_accessibility_label_is_not_offered_as_clickable(rig):
    await rig.open("storefront.html")
    ctx = rig.ctx()
    inspected = await rig.service.inspect(ctx)
    labels = [e["label"] for e in inspected.data["elements"]]
    assert "Add to Cart" in labels and not any("shift, option" in l for l in labels)
    found = await rig.service.find_by_text(ctx, "Add to cart")
    found_labels = [e["label"] for e in found.data["elements"]]
    assert found_labels[0] == "Add to Cart" and not any("shift, option" in l for l in found_labels)


@needs_chrome
async def test_clicking_an_offscreen_element_fails_loudly_and_does_nothing(rig):
    await rig.open("storefront.html")
    ctx = rig.ctx()
    res = await rig.service.click(ctx, "#shortcut")
    assert not res.success
    assert "outside the visible page" in (res.error_message or "")
    assert await rig.js(ctx, "window.hiddenClicks || 0") == 0


@needs_chrome
async def test_a_click_says_whether_the_page_changed(rig):
    await rig.open("storefront.html")
    ctx = rig.ctx()
    done = await rig.service.click(ctx, "#add")
    assert done.success and done.data["page_changed"] is True
    assert await rig.js(ctx, "window.adds") == 1
    nothing = await rig.service.click(ctx, "#noop")
    assert nothing.success and nothing.data["page_changed"] is False


@needs_chrome
async def test_a_click_that_navigates_reports_where_the_page_now_is(rig):
    await rig.open("storefront.html")
    ctx = rig.ctx()
    res = await rig.service.click(ctx, "#next")
    assert res.success and res.data["page_changed"] is True
    assert "page=2" in res.data["page"]["url"]


@needs_chrome
async def test_waiting_for_text_works_with_the_shorthand_the_model_wrote(rig):
    await rig.open("storefront.html")
    ctx = rig.ctx()
    await rig.service.click(ctx, "#add")
    res = await rig.service.wait_for(ctx, {"text": "Added to cart", "reason": "confirmation"}, timeout_ms=3000)
    assert res.success and res.data["met"] is True


@needs_chrome
async def test_a_paragraph_can_be_typed_into_an_editor_inside_an_iframe(rig):
    await rig.open("editor.html")
    ctx = rig.ctx()
    rect = await rig.js(ctx, "(() => { const r = document.getElementById('ed').getBoundingClientRect(); return [r.x + 60, r.y + 40]; })()")
    clicked = await rig.service.pointer(ctx, "click", rect[0], rect[1])
    assert clicked.success, clicked.error_message
    note = "Indian freedom fighters: Bhagat Singh \u2013 a revolutionary.\nMahatma Gandhi led non-violent protest, 1930 \u20b9 salt tax.\nRani Lakshmibai of Jhansi fought in 1857; she is remembered widely."
    res = await rig.service.press_keys(ctx, keys=[], text=note)
    assert res.success, res.error_message
    typed = await rig.js(ctx, "document.getElementById('ed').contentDocument.body.innerText")
    for line in note.split("\n"):
        assert line in typed
