"""
Browser programs in a real headless Chrome, through the real ComexToolService authorization path.

The point of the design is that a program is free Python but reaches the browser only through the service. These tests
check both halves: it can do real work on the page, and the service's rules still apply to every call it makes.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from nervous.cdp_session import _GLOBAL_SESSIONS
from services.program_runtime import ProgramRunner, child_env, programs_enabled
from services.tool_service import (
    DEFAULT_PERMITTED_OPERATIONS,
    ComexToolService,
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

    def ctx(self, **kw):
        return create_tool_execution_context(task_id="p-" + str(id(self)), trusted_server_context=True, target_tab="active_tab",
                                             timeout_seconds=60, **kw)

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


DRAW = """
x, y = center_of("[data-tool=rectangle]"); click_at_xy(x, y)
c = js("(() => { const r = document.querySelector('canvas').getBoundingClientRect(); return [r.x, r.y]; })()")
drag(c[0] + 80, c[1] + 80, c[0] + 380, c[1] + 280)
x, y = center_of("[data-tool=ellipse]"); click_at_xy(x, y)
drag(c[0] + 160, c[1] + 130, c[0] + 300, c[1] + 230)
print(js("window.__scene.map(s => s.type)"))
"""


def test_programs_are_on_by_default_and_can_be_switched_off(monkeypatch):
    assert programs_enabled()
    monkeypatch.setenv("COMEX_PROGRAMS", "0")
    assert not programs_enabled()
    assert "program" in DEFAULT_PERMITTED_OPERATIONS and "page_script" in DEFAULT_PERMITTED_OPERATIONS


async def test_a_program_draws_a_real_scene_in_one_call(rig):
    await rig.open("draw.html")
    ctx = rig.ctx()
    res = await ProgramRunner(rig.service, ctx).run(DRAW, timeout_s=30)
    assert res.ok, res.to_text()
    assert "rectangle" in res.stdout and "ellipse" in res.stdout
    scene = await rig.js(ctx, "window.__scene.map(s => ({t: s.type, x1: s.x1, y1: s.y1, x2: s.x2, y2: s.y2}))")
    rect = next(s for s in scene if s["t"] == "rectangle")
    ell = next(s for s in scene if s["t"] == "ellipse")
    assert rect["x1"] < ell["x1"] < ell["x2"] < rect["x2"] and rect["y1"] < ell["y1"] < ell["y2"] < rect["y2"], "the ellipse is inside the rectangle on the page itself"
    assert res.rpc_calls >= 8 and res.ops["pointer"] >= 4 and res.ops["js"] >= 2


async def test_the_service_rules_still_apply_to_every_call_a_program_makes(rig):
    await rig.open("draw.html")
    no_pointer = rig.ctx(permitted_operations=set(DEFAULT_PERMITTED_OPERATIONS) - {"pointer"})
    code = """
try:
    click_at_xy(100, 100)
    print("clicked")
except ComexError as e:
    print("refused:", e)
print(js("window.__tool"))
"""
    res = await ProgramRunner(rig.service, no_pointer).run(code, timeout_s=20)
    assert res.ok and "refused:" in res.stdout and "not permitted" in res.stdout and "clicked" not in res.stdout
    assert res.failed_ops and res.failed_ops[0].startswith("pointer")
    # a context that does not permit programs at all cannot start one, and nothing runs
    no_program = rig.ctx(permitted_operations=set(DEFAULT_PERMITTED_OPERATIONS) - {"program"})
    refused = await ProgramRunner(rig.service, no_program).run("print('hi')", timeout_s=5)
    assert not refused.ok and "not permitted" in (refused.error or "") and refused.rpc_calls == 0 and refused.stdout == ""


async def test_page_script_can_change_the_page_but_the_read_only_path_still_cannot(rig):
    await rig.open("shop.html")
    ctx = rig.ctx()
    code = """
js("document.title = 'changed by program'")
print(read_js("document.title"))
try:
    read_js("document.title = 'sneaky'")
except ComexError as e:
    print("read-only refused")
print(read_js("document.title"))
"""
    res = await ProgramRunner(rig.service, ctx).run(code, timeout_s=20)
    assert res.ok, res.to_text()
    assert res.stdout.split("\n")[:3] == ["changed by program", "read-only refused", "changed by program"]


async def test_raw_cdp_is_limited_to_the_allow_list_and_cannot_reach_other_tabs(rig):
    await rig.open("shop.html")
    before = len(rig.lab.pages())
    code = """
print(cdp("Page.getLayoutMetrics")["cssVisualViewport"]["clientWidth"] > 0)
for m in ("Target.createTarget", "Browser.close", "Network.getAllCookies", "Page.navigate"):
    try:
        cdp(m, url="about:blank")
        print("ALLOWED", m)
    except ComexError as e:
        print("blocked", m)
"""
    res = await ProgramRunner(rig.service, rig.ctx()).run(code, timeout_s=20)
    assert res.ok, res.to_text()
    lines = res.stdout.split("\n")
    assert lines[0] == "True" and lines[1:5] == ["blocked Target.createTarget", "blocked Browser.close", "blocked Network.getAllCookies", "blocked Page.navigate"]
    assert len(rig.lab.pages()) == before, "a program must not be able to open tabs"


async def test_comex_ui_and_internal_pages_refuse_program_input(rig):
    await rig.open("chess.html")
    ctx = rig.ctx()
    assert (await rig.service.observe(ctx)).success
    session = next(iter(_GLOBAL_SESSIONS.values()))
    session.tracker.state.current_url = "http://localhost:5173/"
    res = await ProgramRunner(rig.service, ctx).run("""
for f in (lambda: click_at_xy(10, 10), lambda: js("1"), lambda: press_key("a")):
    try:
        f(); print("ran")
    except ComexError as e:
        print("refused")
""", timeout_s=20)
    assert res.stdout.split() == ["refused"] * 3, res.to_text()


async def test_environment_has_no_secrets_and_no_direct_browser_connection(rig, monkeypatch):
    monkeypatch.setenv("ROUTER_API_KEY", "secret-should-not-pass")
    monkeypatch.setenv("COMEX_INTERNAL_APP_TOKEN", "token-should-not-pass")
    monkeypatch.setenv("CDP_URL", "http://127.0.0.1:9222")
    env = child_env("/tmp/x")
    assert "ROUTER_API_KEY" not in env and "COMEX_INTERNAL_APP_TOKEN" not in env and "CDP_URL" not in env
    await rig.open("shop.html")
    res = await ProgramRunner(rig.service, rig.ctx()).run(
        "import os\nprint(sorted(k for k in os.environ if any(w in k.upper() for w in ('KEY', 'TOKEN', 'CDP', 'ROUTER', 'OPENAI', 'SECRET'))))\nprint(os.getcwd())",
        timeout_s=20)
    assert res.ok and res.stdout.split("\n")[0] == "[]", res.to_text()
    assert "/run-" in res.stdout.split("\n")[1]  # each run works in its own folder inside the workspace


async def test_a_runaway_program_is_stopped_at_the_timeout_and_work_done_stays_done(rig):
    await rig.open("shop.html")
    ctx = rig.ctx()
    t0 = time.monotonic()
    res = await ProgramRunner(rig.service, ctx).run("js(\"document.title = 'half done'\")\nwhile True:\n    wait(0.1)\n", timeout_s=2)
    assert res.timed_out and not res.ok and time.monotonic() - t0 < 6
    assert "ran out of time" in res.to_text()
    assert await rig.js(ctx, "document.title") == "half done"


async def test_cancelling_the_task_stops_the_program_promptly(rig):
    await rig.open("shop.html")
    ev = asyncio.Event()
    ctx = rig.ctx(cancellation_event=ev)
    task = asyncio.create_task(ProgramRunner(rig.service, ctx).run("while True:\n    wait(0.1)\n", timeout_s=30))
    await asyncio.sleep(1.0)
    ev.set()
    t0 = time.monotonic()
    res = await asyncio.wait_for(task, timeout=5)
    assert res.cancelled and not res.ok and time.monotonic() - t0 < 3


async def test_call_cap_errors_and_output_cap_and_clean_tracebacks(rig):
    await rig.open("shop.html")
    ctx = rig.ctx()
    capped = await ProgramRunner(rig.service, ctx, max_calls=5).run("n = 0\nfor i in range(20):\n    js('1')\n    n += 1\nprint('never')", timeout_s=20)
    assert not capped.ok and "browser operations" in capped.stderr and capped.rpc_calls == 6
    big = await ProgramRunner(rig.service, ctx).run("print('x' * 100000)", timeout_s=10)
    assert big.ok and len(big.stdout) < 9000 and "[output cut]" in big.stdout
    bad = await ProgramRunner(rig.service, ctx).run("a = 1\nraise ValueError('boom')\n", timeout_s=10)
    assert not bad.ok and "line 2" in bad.stderr and "ValueError: boom" in bad.stderr and "program_child" not in bad.stderr
