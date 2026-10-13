"""
Runs INSIDE a browser program's own Python process (standard library only). It has no direct browser connection:
every helper below sends one request over a local Unix socket to the Comex backend, which performs it through
ComexToolService, so tab identity, leases, deadlines and cancellation stay enforced. The program text is executed with
these helpers already defined. Its printed output (stdout) is what the agent gets back.

Coordinates are CSS viewport pixels (the same space as getBoundingClientRect).
"""

import json
import os
import socket
import sys
import time
import traceback
import base64


class ComexError(Exception):
    """A browser operation was refused or failed. The message says why; programs may catch it and carry on."""


_sock = None
_rf = None
_n = 0
_shots = 0


def _call(op, **args):
    global _n
    _n += 1
    _sock.sendall((json.dumps({"id": _n, "op": op, "args": args}) + "\n").encode())
    line = _rf.readline()
    if not line:
        raise ComexError("the Comex backend closed the connection: the program was stopped or its time ran out")
    r = json.loads(line)
    if not r.get("ok"):
        raise ComexError(str(r.get("error") or "operation failed"))
    return r.get("data")


# ── page JavaScript ──────────────────────────────────────────────────────────────────────────────
def js(expression, timeout_ms=15000):
    """Run JavaScript in the page (may change it; promises are awaited) and return its JSON value.
    A body with `return` is wrapped in a function automatically."""
    try:
        d = _call("js", expression=expression, timeout_ms=timeout_ms)
    except ComexError as e:
        if "Illegal return" in str(e):
            d = _call("js", expression="(async () => {\n" + expression + "\n})()", timeout_ms=timeout_ms)
        else:
            raise
    return d.get("value") if isinstance(d, dict) else d


def read_js(expression):
    """Like js() but the browser engine refuses anything that could change the page."""
    d = _call("read_js", expression=expression)
    return d.get("value") if isinstance(d, dict) else d


def page_info():
    return js("({url: location.href, title: document.title, w: innerWidth, h: innerHeight, "
              "scrollX: scrollX, scrollY: scrollY, dpr: devicePixelRatio, ready: document.readyState})")


def viewport():
    i = page_info()
    return {"width": i["w"], "height": i["h"]}


def center_of(selector):
    """Centre point (x, y) of the first element matching a CSS selector, or None."""
    r = js("(() => { const e = document.querySelector(%s); if (!e) return null; const b = e.getBoundingClientRect(); "
           "return [b.x + b.width / 2, b.y + b.height / 2]; })()" % json.dumps(selector))
    return tuple(r) if r else None


# ── mouse and keyboard ───────────────────────────────────────────────────────────────────────────
def click_at_xy(x, y, button="left", clicks=1):
    kind = "right_click" if button == "right" else ("double_click" if clicks == 2 else "click")
    return _call("pointer", action=kind, x=x, y=y, button=button if button != "right" else "left")


def mouse_move(x, y):
    return _call("pointer", action="move", x=x, y=y)


def drag(x1, y1, x2, y2):
    """Press at (x1, y1), move to (x2, y2) in small steps, release."""
    return _call("pointer", action="drag", x=x1, y=y1, to_x=x2, to_y=y2)


def press_key(key):
    """A key or chord such as 'Enter', 'Escape', 'Control+a', 'Shift+ArrowLeft'."""
    return _call("keys", keys=[key])


def type_keys(text):
    """Type text as individual key presses (for games and key handlers)."""
    return _call("keys", text=text)


def type_text(text):
    """Insert text into the focused element in one step (for form fields)."""
    return _call("cdp", method="Input.insertText", params={"text": text})


def type_table(rows):
    """Type a block of cells into a spreadsheet at the selected cell, in one browser operation: cells are separated by
    Tab and rows by Enter, as a person would type them. rows: a list of rows (lists of values) or of strings."""
    lines = ["\t".join(str(c) for c in r) if isinstance(r, (list, tuple)) else str(r) for r in rows]
    return _call("keys", text="\n".join(lines) + "\n")  # the final Enter commits the last cell, as in Sheets


# ── Google Sheets ────────────────────────────────────────────────────────────────────────────────
def sheets_read(gid=None, tries=6):
    """Google Sheets only: the current sheet's cells as a list of rows of strings, read from the sheet's own data
    (Google's CSV view of the saved document, fetched from inside the page with your session), not from the screen.
    Sheets saves a moment after typing, so it retries briefly while the data is still empty."""
    expr = ("(async () => { const m = location.pathname.match(/\\/spreadsheets\\/d\\/([^/]+)/);"
            " if (!m) return {error: 'this tab is not a Google Sheets document'};"
            " const gid = %s || new URLSearchParams(location.hash.slice(1)).get('gid') || '0';"
            " const r = await fetch('/spreadsheets/d/' + m[1] + '/gviz/tq?tqx=out:csv&headers=0&gid=' + gid, {credentials: 'include'});"
            " return {status: r.status, text: await r.text()}; })()") % (json.dumps(str(gid)) if gid is not None else "null")
    import csv
    import io
    rows = []
    for attempt in range(max(1, int(tries))):
        d = js(expr, timeout_ms=15000)
        if not isinstance(d, dict) or d.get("error"):
            raise ComexError((d or {}).get("error") or "could not read the sheet")
        if d.get("status") != 200:
            raise ComexError("the sheet's data could not be read (HTTP %s)" % d.get("status"))
        rows = [r for r in csv.reader(io.StringIO(d.get("text") or ""))]
        if any(any(c.strip() for c in r) for r in rows):
            break
        time.sleep(1.0)
    return rows


# ── ported from browser-harness (https://github.com/browser-use/browser-harness), adapted to Comex ───────────────
# MIT License. Copyright (c) 2026 Browser Use. Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
# following conditions: The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# Changes: every operation goes through the Comex service (keys, page script) instead of a direct CDP connection.
_KC = {"Enter": 13, "Tab": 9, "Escape": 27, "Backspace": 8, " ": 32, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39,
       "ArrowDown": 40}


def fill_input(selector, text, clear_first=True, timeout=0.0):
    """Fill a framework-managed input (React controlled, Vue v-model): focus it, clear it, type with real key events,
    then fire input and change events so the framework sees the new value."""
    if timeout > 0 and not wait_for_element(selector, timeout=timeout):
        raise ComexError("fill_input: element not found: %r" % selector)
    if not js("(()=>{const e=document.querySelector(%s); if(!e) return false; e.focus(); return true;})()" % json.dumps(selector)):
        raise ComexError("fill_input: element not found: %r" % selector)
    if clear_first:
        press_key("ControlOrMeta+a")
        press_key("Backspace")
    if text:
        type_keys(text)
    js("(()=>{const e=document.querySelector(%s); if(!e) return; e.dispatchEvent(new Event('input',{bubbles:true}));"
       " e.dispatchEvent(new Event('change',{bubbles:true}));})()" % json.dumps(selector))


def dispatch_key(selector, key="Enter", event="keypress"):
    """Dispatch a DOM KeyboardEvent on the matched element, for sites that react to synthetic key events on an
    element more reliably than to real key input."""
    kc = _KC.get(key, ord(key) if len(key) == 1 else 0)
    js("(()=>{const e=document.querySelector(%s); if(e){e.focus(); e.dispatchEvent(new KeyboardEvent(%s,{key:%s,code:%s,"
       "keyCode:%d,which:%d,bubbles:true}));}})()" % (json.dumps(selector), json.dumps(event), json.dumps(key), json.dumps(key), kc, kc))
# ── end of the browser-harness port ───────────────────────────────────────────────────────────────────────────


def scroll(x=None, y=None, dy=300, dx=0):
    """Mouse-wheel scroll at a point. Positive dy scrolls down."""
    return _call("scroll", x=x, y=y, delta_y=dy, delta_x=dx)


def select_option(selector, value):
    return _call("select", selector=selector, value=value)


# ── navigation and waiting ───────────────────────────────────────────────────────────────────────
def goto_url(url):
    return _call("navigate", url=url)


def wait(seconds=1.0):
    time.sleep(max(0.0, min(float(seconds), 30.0)))


def wait_for_load(timeout=15.0):
    return _call("wait", condition={"type": "idle"}, timeout_ms=int(timeout * 1000)).get("met")


def wait_for_element(selector, timeout=10.0, visible=True):
    return _call("wait", condition={"type": "selector", "selector": selector, "state": "visible" if visible else "exists"},
                 timeout_ms=int(timeout * 1000)).get("met")


def wait_for_text(text, timeout=10.0):
    return _call("wait", condition={"type": "text", "expected": text}, timeout_ms=int(timeout * 1000)).get("met")


# ── seeing the page ──────────────────────────────────────────────────────────────────────────────
def capture_screenshot(path=None):
    """Save a JPEG of the visible viewport; returns the file path."""
    global _shots
    d = _call("screenshot")
    _shots += 1
    path = path or "shot_%d.jpg" % _shots
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["image_base64"]))
    return os.path.abspath(path)


# ── raw CDP (allow-listed methods on this tab only) ──────────────────────────────────────────────
def cdp(method, **params):
    return _call("cdp", method=method, params=params)


_EXPORTS = ["ComexError", "js", "read_js", "page_info", "viewport", "center_of", "click_at_xy", "mouse_move", "drag", "press_key",
            "type_keys", "type_text", "type_table", "sheets_read", "fill_input", "dispatch_key", "scroll", "select_option",
            "goto_url", "wait", "wait_for_load", "wait_for_element", "wait_for_text", "capture_screenshot", "cdp", "json",
            "time", "os"]


def main():
    global _sock, _rf
    path = os.environ.get("COMEX_PROGRAM_SOCKET")
    if not path or len(sys.argv) < 2:
        sys.stderr.write("program_child: missing socket or program file\n")
        sys.exit(2)
    _sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    _sock.connect(path)
    _rf = _sock.makefile("r", encoding="utf-8")
    ns = {k: globals()[k] for k in _EXPORTS}
    ns["__name__"] = "__main__"
    code = open(sys.argv[1], encoding="utf-8").read()
    try:
        exec(compile(code, "<program>", "exec"), ns)
    except SystemExit:
        raise
    except BaseException as e:  # keep only the frames that belong to the program, so the model sees its own line numbers
        frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == "<program>"]
        lines = ["Traceback (most recent call last):"] + ["  line %s, in %s: %s" % (f.lineno, f.name, (f.line or "").strip()) for f in frames]
        lines.append("%s: %s" % (type(e).__name__, e))
        sys.stderr.write("\n".join(lines) + "\n")
        sys.exit(1)
    finally:
        try:
            sys.stdout.flush()
        except Exception:
            pass


if __name__ == "__main__":
    main()
