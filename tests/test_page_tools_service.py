"""
The new hybrid tools through ComexToolService, with real execution contexts and a real headless Chrome.

These tests exercise the production authorization path (context claims, lease, canonical target, per-tab
lock, deadline and cancellation) and check outcomes in the page, not just that a call returned.
"""

from __future__ import annotations

import asyncio
import base64

import pytest

from nervous.cdp_session import _GLOBAL_SESSIONS
from services.tool_service import (
    DEFAULT_PERMITTED_OPERATIONS,
    ComexToolService,
    ToolErrorCode,
    create_tool_execution_context,
)
from tests.browser_lab import BrowserLab, find_chrome

pytestmark = pytest.mark.skipif(find_chrome() is None, reason="no Chrome/Chromium installed")


@pytest.fixture(scope="module")
def lab():
    lab = BrowserLab.start()
    yield lab
    if lab:
        lab.stop()


class Rig:
    """One service whose 'active_tab' resolves to whichever fixture page is currently open."""

    def __init__(self, lab):
        self.lab = lab
        self.page = None
        self.service = ComexToolService(
            target_resolver=self._resolve,
            allowed_cdp_hosts=["127.0.0.1", "localhost"],
        )

    def _resolve(self, lease, target_tab, trusted):
        return self.page.target_id, self.page.ws_url, None

    async def open(self, name):
        _GLOBAL_SESSIONS.clear()
        self.page = self.lab.open(name)
        await asyncio.sleep(0.8)  # let the fixture finish loading

    def ctx(self, **kw):
        return create_tool_execution_context(task_id="t-" + str(id(self)), trusted_server_context=True,
                                             target_tab="active_tab", timeout_seconds=30, **kw)

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


def test_new_operations_are_permitted_by_default():
    for op in ("observe", "screenshot", "evaluate", "read_table", "wait_for", "press_keys", "scroll", "pointer"):
        assert op in DEFAULT_PERMITTED_OPERATIONS


async def test_screenshot_then_click_by_screenshot_pixels(rig):
    await rig.open("draw.html")
    ctx = rig.ctx()
    shot = await rig.service.screenshot(ctx)
    assert shot.success, shot.error_message
    d = shot.data
    assert base64.b64decode(d["image_base64"])[:2] == b"\xff\xd8"  # JPEG
    # find where the Ellipse button is, as the model would read it off the image
    rect = await rig.js(ctx, "(() => { const r = document.querySelector('[data-tool=ellipse]').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; })()")
    scale = d["width"] / d["viewport"]["width"]
    res = await rig.service.pointer(ctx, "click", round(rect[0] * scale), round(rect[1] * scale), screenshot_id=d["screenshot_id"])
    assert res.success, res.error_message
    assert res.data["target"]["tag"] == "button"
    assert await rig.js(ctx, "window.__tool") == "ellipse"


async def test_stale_screenshot_is_refused_and_nothing_is_clicked(rig):
    await rig.open("draw.html")
    ctx = rig.ctx()
    d = (await rig.service.screenshot(ctx)).data
    rect = await rig.js(ctx, "(() => { const r = document.querySelector('[data-tool=line]').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; })()")
    # the page navigates after the screenshot was taken
    await rig.open("draw.html")
    ctx = rig.ctx()
    res = await rig.service.pointer(ctx, "click", rect[0], rect[1], screenshot_id=d["screenshot_id"])
    assert not res.success and res.error_code == ToolErrorCode.ACTION_BLOCKED.value
    assert "new screenshot" in res.error_message
    assert await rig.js(ctx, "window.__tool") == "select", "a refused click must not click"
    # a point outside the viewport is refused too
    far = await rig.service.pointer(ctx, "click", 99999, 10)
    assert not far.success and "outside" in far.error_message


async def test_keys_play_the_game_and_report_page_change(rig):
    await rig.open("wordle.html?seed=1")  # secret: slate
    ctx = rig.ctx()
    r = await rig.service.press_keys(ctx, keys=["Enter"], text="crane")
    assert r.success and r.data["page_changed"] is True and r.data["count"] == 6
    w = await rig.service.wait_for(ctx, {"type": "js", "expression": "document.querySelectorAll('.row')[0].children[0].dataset.state !== 'tbd'"}, 3000)
    assert w.success and w.data["met"]
    assert await rig.js(ctx, "[...document.querySelectorAll('.row')[0].children].map(t => t.dataset.state).join(',')") == \
        "absent,absent,correct,absent,correct"
    bad = await rig.service.press_keys(ctx, keys=["Hyper+q"])
    assert not bad.success and bad.error_code == ToolErrorCode.VALIDATION_ERROR.value


async def test_evaluate_through_the_service_cannot_change_the_page(rig):
    await rig.open("shop.html")
    ctx = rig.ctx()
    ok = await rig.service.evaluate(ctx, "document.querySelectorAll('input').length")
    assert ok.success and ok.data["value"] == 1
    before = await rig.js(ctx, "document.body.innerHTML.length")
    bad = await rig.service.evaluate(ctx, "document.body.innerHTML = '<p>pwned</p>'")
    assert not bad.success and bad.evidence["page_io_code"] == "side_effect"
    assert await rig.js(ctx, "document.body.innerHTML.length") == before


async def test_read_table_reports_incomplete_then_complete(rig):
    await rig.open("grades.html")
    ctx = rig.ctx()
    r = await rig.service.read_table(ctx, selector="#gradeTable")
    assert r.success and r.data["complete"] is False and r.data["tables"][0]["total_rows"] == 10
    # the page-size control is a native dropdown: operate it like a user would
    sel = await rig.service.select_option(ctx, "select[name=gradeTable_length]", "100")
    assert sel.success and sel.data["selected"]["value"] == "100" and sel.data["page_changed"] is True
    full = await rig.service.read_table(ctx, selector="#gradeTable")
    assert full.data["complete"] is True and full.data["tables"][0]["total_rows"] == 57
    # wrong element, unknown option and missing element are explained, not swallowed
    bad = await rig.service.select_option(ctx, "#summary", "100")
    assert not bad.success and "not a dropdown" in bad.error_message
    nope = await rig.service.select_option(ctx, "select[name=gradeTable_length]", "7")
    assert not nope.success and "Options:" in nope.error_message
    gone = await rig.service.select_option(ctx, "#does-not-exist", "1")
    assert not gone.success and "No element matches" in gone.error_message


async def test_observe_classifies_pages_deterministically(rig):
    await rig.open("draw.html")
    ctx = rig.ctx()
    o = await rig.service.observe(ctx)
    assert o.success and o.data["strategy"]["path"] in ("visual", "mixed")
    assert o.data["canvases"] and o.data["state_version"]["document_generation"] >= 0
    await rig.open("shop.html")
    ctx = rig.ctx()
    assert (await rig.service.observe(ctx)).data["strategy"]["path"] == "semantic"
    await rig.open("grades.html")
    ctx = rig.ctx()
    assert (await rig.service.observe(ctx)).data["strategy"]["path"] == "table"
    await rig.open("chess.html")
    ctx = rig.ctx()
    chess = (await rig.service.observe(ctx)).data["strategy"]
    assert chess["path"] == "visual" and "board" in " ".join(chess["reasons"]) and "browser_evaluate" in chess["reasons"][0]
    await rig.open("wordle.html")
    ctx = rig.ctx()
    assert (await rig.service.observe(ctx)).data["strategy"]["path"] in ("semantic", "visual")  # keyboard-only page: hint is advisory


async def test_authorization_boundaries_hold_for_the_new_operations(rig):
    await rig.open("wordle.html")
    # a context that does not list the operation cannot use it
    limited = rig.ctx(permitted_operations={"inspect", "extract"})
    for call in (rig.service.press_keys(limited, keys=["a"]), rig.service.pointer(limited, "click", 5, 5),
                 rig.service.evaluate(limited, "1"), rig.service.screenshot(limited)):
        r = await call
        assert not r.success and r.error_code == ToolErrorCode.UNAUTHORIZED.value
    # a single-agent context without server authority is refused
    with pytest.raises(Exception):
        create_tool_execution_context(task_id="x", trusted_server_context=False, target_tab="active_tab")
    # cancellation before the call is honoured and nothing is sent
    ev = asyncio.Event()
    ev.set()
    cancelled = rig.ctx(cancellation_event=ev)
    r = await rig.service.press_keys(cancelled, keys=["a"])
    assert not r.success and r.error_code == ToolErrorCode.CANCELLED.value
    live = rig.ctx()
    assert await rig.js(live, "document.querySelectorAll('.tile')[0].textContent") == ""


async def test_browser_internal_pages_and_the_comex_ui_refuse_input(rig):
    await rig.open("chess.html")
    ctx = rig.ctx()
    assert (await rig.service.observe(ctx)).success  # creates the tab session
    session = next(iter(_GLOBAL_SESSIONS.values()))
    session.tracker.state.current_url = "chrome://settings"
    r = await rig.service.press_keys(ctx, keys=["a"])
    assert not r.success and r.error_code == ToolErrorCode.ACTION_BLOCKED.value and "browser-internal" in r.error_message
    session.tracker.state.current_url = "http://localhost:5173/"
    r = await rig.service.pointer(ctx, "click", 10, 10)
    assert not r.success and "Comex interface" in r.error_message
    session.tracker.state.current_url = "about:blank"
    session.tracker.state.is_navigating = True
    r = await rig.service.scroll(ctx, delta_y=100)
    assert not r.success and r.retryable and "browser_wait" in r.error_message


async def test_prefetch_reads_real_pages_through_the_authorized_service(rig):
    import agent_service as A
    await rig.open("shop.html")
    ctx = rig.ctx()
    urls = [f"{rig.lab.base}/grades.html", f"{rig.lab.base}/shop.html#/search/headphones"]
    text, meta = await A._prefetch_pages(rig.service, ctx, urls, lambda *_a, **_k: asyncio.sleep(0))
    assert meta["pages_read"] == 2, meta
    assert "Grade History (synthetic test data)" in text and "Showing 1 to 10 of 57 entries" in text
    assert "JBL Tune 770NC headphones" in text, "the single-page app's results must be read after it has settled"
    assert text.count("[UNTRUSTED DATA START") == 1 and meta["ms"] < 8000
