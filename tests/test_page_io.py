"""
Page I/O primitives (nervous/page_io.py, nervous/viewport.py).

Pure maths and parsing first, then each primitive against a real headless Chrome and fixture pages that
reproduce the tasks the old semantic-only tools could not do. A tool returning is never the pass
condition: every real-browser test checks the state the page ended up in.
"""

from __future__ import annotations

import base64
import json

import pytest

from nervous import page_io as pio
from nervous.cdp_session import WebSocketCDPClient
from nervous.viewport import (
    build_viewport_info,
    drift_reason,
    in_viewport,
    scale_for,
    screenshot_to_viewport,
    viewport_to_screenshot,
)
from tests.browser_lab import BrowserLab, find_chrome

# ──────────────────────────────────────────────────────────────────────
#  Pure logic
# ──────────────────────────────────────────────────────────────────────


def test_scale_fits_image_budget():
    assert scale_for(800, 600) == 1.0
    s = scale_for(2560, 1440)
    assert s < 1.0 and 2560 * s <= 1280 + 1 and 2560 * s * 1440 * s <= 1_150_000 + 1
    assert scale_for(0, 0) == 1.0


def test_coordinate_round_trip_is_exact_within_a_pixel():
    info = build_viewport_info("a", 1920, 1080)
    assert info.screenshot_width <= 1280
    for x, y in [(0, 0), (960, 540), (1919, 1079), (333, 777)]:
        sx, sy = viewport_to_screenshot(x, y, info)
        bx, by = screenshot_to_viewport(sx, sy, info)
        assert abs(bx - x) < 1e-6 and abs(by - y) < 1e-6


def test_screenshot_point_lands_on_the_same_element_in_viewport_space():
    # model points at the centre of an element at css (960, 540) in a 1920x1080 viewport
    info = build_viewport_info("a", 1920, 1080)
    sx, sy = viewport_to_screenshot(960, 540, info)
    # model answers with whole pixels; the error must stay under one screenshot pixel
    bx, by = screenshot_to_viewport(round(sx), round(sy), info)
    assert abs(bx - 960) <= 1 / info.scale and abs(by - 540) <= 1 / info.scale


def test_drift_detects_resize_navigation_and_scroll():
    info = build_viewport_info("a", 1000, 700, scroll_x=0, scroll_y=0, document_generation=3)
    assert drift_reason(info, 1000, 700, 3, (0, 0)) is None
    assert "viewport changed" in drift_reason(info, 1001, 700, 3, (0, 0))
    assert "navigated" in drift_reason(info, 1000, 700, 4, (0, 0))
    assert "scrolled" in drift_reason(info, 1000, 700, 3, (0, 120))
    assert "no screenshot" in drift_reason(None, 1000, 700, 3)


def test_in_viewport_bounds():
    assert in_viewport(10, 10, 100, 100) and not in_viewport(-1, 10, 100, 100) and not in_viewport(10, 101, 100, 100)


def test_key_tokens_parse_exactly():
    k = pio.parse_key_token("Enter")
    assert (k["key"], k["code"], k["vk"]) == ("Enter", "Enter", 13)
    a = pio.parse_key_token("a")
    assert (a["key"], a["code"], a["vk"], a["text"], a["modifiers"]) == ("a", "KeyA", 65, "a", 0)
    A = pio.parse_key_token("A")
    assert A["modifiers"] & 8 and A["code"] == "KeyA"
    chord = pio.parse_key_token("Control+Shift+z")
    assert chord["modifiers"] == 2 | 8 and chord["code"] == "KeyZ"
    assert pio.parse_key_token("ControlOrMeta+a")["modifiers"] in (2, 4)
    assert pio.parse_key_token("5")["code"] == "Digit5"
    assert pio.parse_key_token("!")["modifiers"] & 8
    with pytest.raises(pio.PageIOError):
        pio.parse_key_token("Hyper+a")
    with pytest.raises(pio.PageIOError):
        pio.parse_key_token("notakey")


def test_key_plan_is_bounded_and_text_expands():
    plan = pio.plan_keys(["Enter"], "hi")
    assert [p["token"] for p in plan] == ["h", "i", "Enter"]
    with pytest.raises(pio.PageIOError):
        pio.plan_keys([], None)
    with pytest.raises(pio.PageIOError):
        pio.plan_keys(["a"] * (pio.MAX_KEYS_PER_CALL + 1), None)


def test_image_size_reads_png_and_jpeg_headers():
    import struct
    import zlib
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", 321, 123, 8, 2, 0, 0, 0)
    png += struct.pack(">I", zlib.crc32(b"IHDR" + struct.pack(">IIBBBBB", 321, 123, 8, 2, 0, 0, 0)))
    assert pio.image_size(png) == (321, 123)
    # JPEG: SOI, an APP0 segment to skip, then a baseline SOF0 carrying height then width
    jpeg = b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 6) + b"abcd" + b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, 123, 321, 3) + b"\x00" * 12
    assert pio.image_size(jpeg) == (321, 123)
    with pytest.raises(pio.PageIOError):
        pio.image_size(b"not an image at all")


# ──────────────────────────────────────────────────────────────────────
#  Real browser
# ──────────────────────────────────────────────────────────────────────

needs_chrome = pytest.mark.skipif(find_chrome() is None, reason="no Chrome/Chromium installed")


@pytest.fixture(scope="module")
def lab():
    lab = BrowserLab.start()
    yield lab
    if lab:
        lab.stop()


async def _client(lab, name):
    page = lab.open(name)
    cdp = WebSocketCDPClient(page.ws_url)
    await cdp.connect()
    for d in ("Page", "DOM", "Runtime"):
        await cdp.send(f"{d}.enable")
    await cdp.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
    # wait for load
    for _ in range(100):
        r = await cdp.send("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
        if r["result"]["value"] == "complete":
            break
        import asyncio
        await asyncio.sleep(0.05)
    return page, cdp


async def _js(cdp, expr):
    r = await cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    return r["result"].get("value")


@needs_chrome
async def test_evaluate_readonly_reads_and_refuses_every_mutation(lab):
    page, cdp = await _client(lab, "shop.html")
    ok = await pio.evaluate_readonly(cdp, "document.querySelector('#search input').getAttribute('aria-label')")
    assert ok["value"] == "Search products"
    before = await _js(cdp, "[document.title, document.body.children.length, document.querySelector('#cart-count').textContent]")
    for bad in [
        "document.title = 'hacked'",
        "document.querySelector('#cart-count').textContent = '99'",
        "document.body.innerHTML = ''",
        "document.querySelector('button').click()",
        "fetch('http://127.0.0.1:1/x')",
        "localStorage.setItem('a','b')",
        "document.cookie = 'a=b'",
        "location.href = 'about:blank'",
    ]:
        with pytest.raises(pio.PageIOError) as e:
            await pio.evaluate_readonly(cdp, bad)
        assert e.value.code == "side_effect", bad
    after = await _js(cdp, "[document.title, document.body.children.length, document.querySelector('#cart-count').textContent]")
    assert before == after, "a refused expression must leave the page exactly as it was"
    with pytest.raises(pio.PageIOError) as t:
        await pio.evaluate_readonly(cdp, "while(true){}", timeout_ms=200)
    assert t.value.code == "timeout"
    big = await pio.evaluate_readonly(cdp, "'x'.repeat(50000)", max_chars=1000)
    assert big["truncated"] and big["chars"] > 1000
    await cdp.close()
    lab.close_page(page)


@needs_chrome
async def test_read_table_is_complete_only_when_it_really_is(lab):
    page, cdp = await _client(lab, "grades.html")
    first = await pio.read_table(cdp, selector="#gradeTable")
    t = first["tables"][0]
    assert t["total_rows"] == 10 and not first["complete"], "page 1 of 6 must not be reported complete"
    assert any("1 to 10 of 57" in n for n in t["completeness"]["notes"])
    assert any("more pages" in n for n in t["completeness"]["notes"])
    assert t["headers"] == ["Sl.No.", "Code", "Title", "Type", "Credits", "Grade", "Month", "Declared on", "Distribution"], \
        "colspan/rowspan header cells must be expanded into one aligned header row"
    # act like a user: show 100 entries
    await _js(cdp, "(() => { const s = document.querySelector('select'); s.value = '100'; s.dispatchEvent(new Event('change', {bubbles: true})); })()")
    full = await pio.read_table(cdp, selector="#gradeTable")
    t = full["tables"][0]
    expected = json.load(open("tests/fixtures/browser/grades.expected.json"))
    assert t["total_rows"] == expected["rows"] == len(t["rows"])
    assert t["rows"][0][1] == expected["first"][1] and t["rows"][-1][1] == expected["last"][1]
    assert all(len(r) == len(t["headers"]) for r in t["rows"]), "every row must have one cell per header"
    assert sum(int(r[4]) for r in t["rows"]) == expected["credits"]
    assert full["complete"], t["completeness"]
    # reading in parts: nothing silently dropped, with an explicit continuation
    part = await pio.read_table(cdp, selector="#gradeTable", start_row=0, max_rows=20)
    pt = part["tables"][0]
    assert len(pt["rows"]) == 20 and pt["next_start_row"] == 20 and not part["complete"]
    rest = await pio.read_table(cdp, selector="#gradeTable", start_row=20, max_rows=500)
    assert len(rest["tables"][0]["rows"]) == 37 and rest["complete"]
    # both tables found without a selector
    both = await pio.read_table(cdp)
    assert both["count"] == 2
    await cdp.close()
    lab.close_page(page)


@needs_chrome
async def test_keys_play_the_keyboard_only_word_game(lab):
    page, cdp = await _client(lab, "wordle.html?seed=1")  # secret: slate
    plan = pio.plan_keys(["Enter"], "crane")
    await pio.press_keys(cdp, plan)
    scored = await pio.wait_for(cdp, None, {"type": "js", "expression": "document.querySelectorAll('.row')[0].children[0].dataset.state !== 'tbd'"}, timeout_ms=3000)
    assert scored["met"], "the server's feedback never reached the page"
    states = await _js(cdp, "[...document.querySelectorAll('.row')[0].children].map(t => t.dataset.state)")
    # crane vs slate: c absent, r absent, a correct, n absent, e correct
    assert states == ["absent", "absent", "correct", "absent", "correct"]
    assert (await _js(cdp, "document.querySelector('#game').dataset.status")) == "playing"
    await pio.press_keys(cdp, pio.plan_keys(["Enter"], "slate"))
    won = await pio.wait_for(cdp, None, {"type": "js", "expression": "document.querySelector('#game').dataset.status === 'won'"}, timeout_ms=3000)
    assert won["met"] and (await _js(cdp, "document.querySelector('#game').dataset.status")) == "won"
    # nothing about the answer exists in the page itself
    assert "slate" not in await _js(cdp, "document.documentElement.outerHTML + Object.keys(window).join(' ')")
    await cdp.close()
    lab.close_page(page)


@needs_chrome
async def test_pointer_plays_a_move_on_a_board_without_square_elements(lab):
    page, cdp = await _client(lab, "chess.html")
    # no per-square elements exist: the position must be read from geometry, like on real chess sites
    assert await _js(cdp, "document.querySelectorAll('[data-square],.square').length") == 0
    pieces = await pio.evaluate_readonly(cdp, """(() => {
      const b = document.querySelector('#board').getBoundingClientRect();
      return [...document.querySelectorAll('.piece')].map(p => { const r = p.getBoundingClientRect();
        return { cls: p.className, file: Math.floor((r.left + 30 - b.left) / 60), rank: 7 - Math.floor((r.top + 30 - b.top) / 60) }; }); })()""")
    rook = next(p for p in pieces["value"] if "white" in p["cls"] and "rook" in p["cls"])
    assert (rook["file"], rook["rank"]) == (0, 0)
    board = await pio.evaluate_readonly(cdp, "(() => { const r = document.querySelector('#board').getBoundingClientRect(); return [r.left, r.top]; })()")
    left, top = board["value"]
    sq = lambda f, r: (left + f * 60 + 30, top + (7 - r) * 60 + 30)
    # an illegal try first (rook cannot jump to b3): nothing must move
    await pio.pointer_action(cdp, "click", *sq(0, 0))
    await pio.pointer_action(cdp, "click", *sq(1, 2))
    assert (await _js(cdp, "window.__game.history.length")) == 0
    await pio.pointer_action(cdp, "click", *sq(0, 0))   # select the rook again
    await pio.pointer_action(cdp, "click", *sq(0, 7))   # Ra8#
    game = await _js(cdp, "({status: __game.status, winner: __game.winner, history: __game.history})")
    assert game == {"status": "checkmate", "winner": "w", "history": ["Ra1-a8#"]}
    assert "Checkmate" in await _js(cdp, "document.querySelector('#status').textContent")
    await cdp.close()
    lab.close_page(page)


@needs_chrome
async def test_pointer_drag_moves_a_piece_like_a_user(lab):
    page, cdp = await _client(lab, "chess.html")
    b = (await pio.evaluate_readonly(cdp, "(() => { const r = document.querySelector('#board').getBoundingClientRect(); return [r.left, r.top]; })()"))["value"]
    await pio.pointer_action(cdp, "drag", b[0] + 30, b[1] + 7 * 60 + 30, to_x=b[0] + 30, to_y=b[1] + 30)
    assert (await _js(cdp, "__game.status")) == "checkmate"
    await cdp.close()
    lab.close_page(page)


@needs_chrome
async def test_keys_and_drag_draw_on_a_canvas_with_no_dom_shapes(lab):
    page, cdp = await _client(lab, "draw.html")
    c = (await pio.evaluate_readonly(cdp, "(() => { const r = document.querySelector('#c').getBoundingClientRect(); return [r.left, r.top]; })()"))["value"]
    await pio.press_keys(cdp, pio.plan_keys(["r"], None))               # shortcut: rectangle tool
    assert await _js(cdp, "window.__tool") == "rectangle"
    await pio.pointer_action(cdp, "drag", c[0] + 200, c[1] + 120, to_x=c[0] + 600, to_y=c[1] + 420)
    await pio.press_keys(cdp, pio.plan_keys(["o"], None))
    await pio.pointer_action(cdp, "drag", c[0] + 300, c[1] + 200, to_x=c[0] + 500, to_y=c[1] + 340)
    scene = await _js(cdp, "window.__scene.map(s => ({type: s.type, x1: Math.round(s.x1), y1: Math.round(s.y1), x2: Math.round(s.x2), y2: Math.round(s.y2)}))")
    assert [s["type"] for s in scene] == ["rectangle", "ellipse"]
    rect, ell = scene
    assert abs(rect["x2"] - rect["x1"] - 400) <= 2 and abs(rect["y2"] - rect["y1"] - 300) <= 2
    assert rect["x1"] < ell["x1"] < ell["x2"] < rect["x2"] and rect["y1"] < ell["y1"] < ell["y2"] < rect["y2"], "ellipse must sit inside the rectangle"
    await cdp.close()
    lab.close_page(page)


@needs_chrome
@pytest.mark.parametrize("scale", [1.0, 2.0])
async def test_screenshot_coordinates_hit_the_element_the_model_sees(scale):
    lab2 = BrowserLab.start(scale=scale)
    try:
        page, cdp = await _client(lab2, "draw.html")
        info, b64 = await pio.capture_screenshot(cdp, document_generation=0)
        raw = base64.b64decode(b64)
        assert pio.image_size(raw) == (info.screenshot_width, info.screenshot_height)
        assert max(info.screenshot_width, info.screenshot_height) <= 1280 * 1.1
        # the model "sees" the Ellipse button at some screenshot pixel; find where the page really has it
        r = (await pio.evaluate_readonly(cdp, "(() => { const r = document.querySelector('[data-tool=ellipse]').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; })()"))["value"]
        shot_pt = viewport_to_screenshot(r[0], r[1], info)
        vx, vy = screenshot_to_viewport(round(shot_pt[0]), round(shot_pt[1]), info)
        await pio.pointer_action(cdp, "click", vx, vy)
        assert await _js(cdp, "window.__tool") == "ellipse"
        # the drift gate: after the viewport changes, the old screenshot id must be refused
        await cdp.send("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 600, "deviceScaleFactor": 1, "mobile": False})
        vp = await pio.measure_viewport(cdp)
        assert "viewport changed" in drift_reason(info, vp["width"], vp["height"], 0, (vp["scroll_x"], vp["scroll_y"]))
        await cdp.close()
        lab2.close_page(page)
    finally:
        lab2.stop()


@needs_chrome
async def test_wait_for_state_and_idle(lab):
    page, cdp = await _client(lab, "shop.html")
    miss = await pio.wait_for(cdp, None, {"type": "text", "expected": "Sony"}, timeout_ms=300)
    assert miss["met"] is False and "timed out" in miss["detail"]
    await _js(cdp, "setTimeout(() => { location.hash = '#/search/sony'; }, 250)")
    hit = await pio.wait_for(cdp, None, {"type": "text", "expected": "Sony WH-1000XM5"}, timeout_ms=3000)
    assert hit["met"] and 150 <= hit["waited_ms"] < 3000
    idle = await pio.wait_for(cdp, None, {"type": "idle", "quiet_ms": 200}, timeout_ms=3000)
    assert idle["met"]
    sel = await pio.wait_for(cdp, None, {"type": "selector", "selector": "#add", "state": "visible"}, timeout_ms=300)
    assert sel["met"] is False
    await cdp.close()
    lab.close_page(page)


def test_get_element_by_id_with_a_literal_is_rewritten_and_dynamic_ids_are_not():
    assert pio._rewrite_get_element_by_id("document.getElementById('board').id") == "document.querySelector('[id=\"board\"]').id"
    assert pio._rewrite_get_element_by_id('root.getElementById( "a-b_c" )') == "root.querySelector('[id=\"a-b_c\"]')"
    dyn = "document.getElementById(name)"
    assert pio._rewrite_get_element_by_id(dyn) == dyn
    # an id that could break out of the selector is not rewritten
    evil = "document.getElementById('x\"]; fetch(1);//')"
    assert pio._rewrite_get_element_by_id(evil) == evil


@needs_chrome
async def test_get_element_by_id_works_in_readonly_evaluate_without_losing_safety(lab):
    page, cdp = await _client(lab, "shop.html")
    ok = await pio.evaluate_readonly(cdp, "document.getElementById('cart-count').textContent")
    assert ok["value"] == "0"
    with pytest.raises(pio.PageIOError) as e:
        await pio.evaluate_readonly(cdp, "document.getElementById('cart-count').textContent = '5'")
    assert e.value.code == "side_effect"
    assert await _js(cdp, "document.querySelector('#cart-count').textContent") == "0"
    await cdp.close()
    lab.close_page(page)
