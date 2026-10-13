"""
Comex Browser Nervous System: page I/O primitives.

The small set of things an agent needs beyond "click this selector" and "type into that field":

    observation (never changes the page)
        evaluate_readonly   run a JavaScript expression under V8's side-effect-free mode
        read_table          every row of a table, with explicit completeness information
        capture_screenshot  a scaled image plus the geometry needed to point at it
    input (changes the page, so callers must hold the tab lock and the authority checks)
        press_keys          single keys and chords
        scroll_wheel / scroll_into_view
        pointer             move, click, drag at coordinates (screenshot or viewport space)
    waiting
        wait_for            poll a typed condition instead of sleeping

Everything takes a `cdp` object with `async send(method, params)`. Authorization, per-tab locking,
deadlines and cancellation are the caller's job (`ComexToolService`); this module never decides who
may act, only how a permitted action is performed correctly.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import struct
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .viewport import (
    ViewportInfo,
    build_viewport_info,
    drift_reason,
    in_viewport,
    screenshot_to_viewport,
    viewport_to_screenshot,
)

logger = logging.getLogger("comex.nervous.page_io")

MAX_EVAL_CHARS = 8000          # length of an expression the model may send
MAX_EVAL_OUTPUT_CHARS = 20000  # serialized result returned to the model
DEFAULT_EVAL_TIMEOUT_MS = 1500
MAX_KEYS_PER_CALL = 60
MAX_DRAG_STEPS = 60
MAX_TABLE_ROWS = 2000
MAX_TABLE_OUTPUT_CHARS = 60000


# V8's side-effect-free mode refuses getElementById (but allows the equivalent querySelector). Models reach for it constantly,
# so a literal id is rewritten; anything dynamic is left alone and refused with an explanation.
_GET_BY_ID = re.compile(r"""\.getElementById\(\s*(['"])([A-Za-z0-9_:\-\.]{1,120})\1\s*\)""")


def _rewrite_get_element_by_id(expression: str) -> str:
    return _GET_BY_ID.sub(lambda m: f".querySelector('[id=\"{m.group(2)}\"]')", expression)


class PageIOError(RuntimeError):
    """A failure the model can act on. `code` is stable; the message says what to do next."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail


# ──────────────────────────────────────────────────────────────────────
#  Read-only evaluation
# ──────────────────────────────────────────────────────────────────────

async def evaluate_readonly(
    cdp: Any,
    expression: str,
    *,
    timeout_ms: int = DEFAULT_EVAL_TIMEOUT_MS,
    max_chars: int = MAX_EVAL_OUTPUT_CHARS,
) -> Dict[str, Any]:
    """
    Evaluate JavaScript in the page with `throwOnSideEffect`: V8 refuses anything that could change
    state (DOM writes, events, storage, network, timers) and the call fails instead of running it.
    This is an engine guarantee, not a pattern match on the source. `timeout` stops runaway loops.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise PageIOError("validation", "expression must be a non-empty string.")
    if len(expression) > MAX_EVAL_CHARS:
        raise PageIOError("validation", f"expression is {len(expression)} chars; the limit is {MAX_EVAL_CHARS}.")
    timeout_ms = max(50, min(int(timeout_ms), 10000))
    max_chars = max(200, min(int(max_chars), MAX_EVAL_OUTPUT_CHARS * 3))
    expression = _rewrite_get_element_by_id(expression)

    try:
        res = await cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "throwOnSideEffect": True,
            "timeout": timeout_ms,
            "awaitPromise": False,
            "silent": True,
            "generatePreview": False,
        })
    except asyncio.CancelledError:
        raise
    except Exception as e:  # the CDP client raises on protocol errors such as "Execution was terminated"
        msg = str(e)
        if "terminated" in msg.lower():
            raise PageIOError("timeout", f"The expression ran longer than {timeout_ms} ms and was stopped.") from e
        raise PageIOError("protocol", msg[:300]) from e
    details = res.get("exceptionDetails")
    if details:
        exc = details.get("exception") or {}
        desc = str(exc.get("description") or details.get("text") or "JavaScript error")
        if "side-effect" in desc.lower() or "side effect" in desc.lower():
            raise PageIOError(
                "side_effect",
                "That expression could change the page, so it was not run. Only read operations are allowed "
                "(querySelector/querySelectorAll, attributes, text, rects, computed style). To change the page use "
                "the click, type, key, scroll or pointer tools; to fill an editor inside an iframe, click into it with browser_pointer "
                "and call browser_keys(text=...). Note: use querySelector (getElementById is only accepted with a literal id).",
            )
        raise PageIOError("js_error", desc.split("\n")[0][:300])
    if "error" in res:  # protocol level (for example "Execution was terminated" on timeout)
        msg = str(res["error"].get("message", res["error"]))
        if "terminated" in msg.lower():
            raise PageIOError("timeout", f"The expression ran longer than {timeout_ms} ms and was stopped.")
        raise PageIOError("protocol", msg[:300])

    remote = res.get("result", {})
    value = remote.get("value") if remote.get("type") != "undefined" else None
    if remote.get("subtype") == "error":
        raise PageIOError("js_error", str(remote.get("description", "error"))[:300])
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = json.dumps(str(value), ensure_ascii=False)
    truncated = len(text) > max_chars
    if truncated:
        # A cut-off JSON document is not valid JSON, so hand back text and say so.
        return {"value": text[:max_chars], "truncated": True, "chars": len(text), "type": remote.get("type")}
    return {"value": value, "truncated": False, "chars": len(text), "type": remote.get("type")}


# ──────────────────────────────────────────────────────────────────────
#  Programs: page scripts that may change the page, and raw CDP on a safe list
# ──────────────────────────────────────────────────────────────────────

MAX_SCRIPT_CHARS = 60_000

# Raw CDP methods a program may call on its own tab. Input, DOM reading and focus, evaluation, layout and screenshots.
# Deliberately absent: Target.* (open or attach other tabs), Browser.*, Storage.*, Network.* (cookies), Page.navigate
# (use goto so the URL policy applies), Emulation.* (changes the viewport behind the screenshot gate), file chooser and download control.
CDP_ALLOWED: frozenset = frozenset({
    "Input.dispatchMouseEvent", "Input.dispatchKeyEvent", "Input.insertText", "Input.dispatchTouchEvent",
    "DOM.getDocument", "DOM.querySelector", "DOM.querySelectorAll", "DOM.getBoxModel", "DOM.resolveNode", "DOM.describeNode",
    "DOM.getNodeForLocation", "DOM.scrollIntoViewIfNeeded", "DOM.focus",
    "Runtime.evaluate", "Runtime.callFunctionOn", "Runtime.getProperties",
    "Page.getLayoutMetrics", "Page.captureScreenshot",
    "Accessibility.getFullAXTree", "DOMSnapshot.captureSnapshot",
})


def _package_value(remote: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    value = remote.get("value") if remote.get("type") != "undefined" else None
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = json.dumps(str(value), ensure_ascii=False)
    if len(text) > max_chars:
        return {"value": text[:max_chars], "truncated": True, "chars": len(text), "type": remote.get("type")}
    return {"value": value, "truncated": False, "chars": len(text), "type": remote.get("type")}


async def evaluate_script(
    cdp: Any,
    expression: str,
    *,
    timeout_ms: int = 15000,
    max_chars: int = MAX_EVAL_OUTPUT_CHARS,
) -> Dict[str, Any]:
    """
    Run JavaScript in the page and let it change the page (DOM writes, events, timers, fetch), with a user gesture,
    promises awaited, a time limit and an output cap. Unlike evaluate_readonly this is NOT side-effect free: it is the
    page-side half of a program. The caller (ComexToolService.page_script) authorizes it under its own operation name.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise PageIOError("validation", "expression must be a non-empty string.")
    if len(expression) > MAX_SCRIPT_CHARS:
        raise PageIOError("validation", f"script is {len(expression)} chars; the limit is {MAX_SCRIPT_CHARS}.")
    timeout_ms = max(100, min(int(timeout_ms), 60000))
    max_chars = max(200, min(int(max_chars), MAX_EVAL_OUTPUT_CHARS * 3))
    try:
        res = await cdp.send("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True, "userGesture": True,
            "timeout": timeout_ms, "silent": True, "generatePreview": False,
        })
    except asyncio.CancelledError:
        raise
    except Exception as e:
        msg = str(e)
        if "terminated" in msg.lower():
            raise PageIOError("timeout", f"The script ran longer than {timeout_ms} ms and was stopped.") from e
        raise PageIOError("protocol", msg[:300]) from e
    details = res.get("exceptionDetails")
    if details:
        exc = details.get("exception") or {}
        desc = str(exc.get("description") or details.get("text") or "JavaScript error")
        raise PageIOError("js_error", desc.split("\n")[0][:300])
    if "error" in res:
        msg = str(res["error"].get("message", res["error"]))
        if "terminated" in msg.lower():
            raise PageIOError("timeout", f"The script ran longer than {timeout_ms} ms and was stopped.")
        raise PageIOError("protocol", msg[:300])
    remote = res.get("result", {})
    if remote.get("subtype") == "error":
        raise PageIOError("js_error", str(remote.get("description", "error"))[:300])
    return _package_value(remote, max_chars)


async def cdp_call(cdp: Any, method: str, params: Optional[Dict[str, Any]] = None, *, timeout_s: float = 20.0) -> Any:
    """One raw CDP call on the program's own tab, refused unless the method is on CDP_ALLOWED."""
    if method not in CDP_ALLOWED:
        raise PageIOError("blocked", f"CDP method {method!r} is not available to programs. Allowed: {', '.join(sorted(CDP_ALLOWED))}.")
    try:
        return await asyncio.wait_for(cdp.send(method, params or {}), timeout=timeout_s)
    except asyncio.TimeoutError as e:
        raise PageIOError("timeout", f"{method} did not answer within {timeout_s:.0f} s.") from e
    except asyncio.CancelledError:
        raise
    except Exception as e:
        raise PageIOError("protocol", f"{method}: {str(e)[:300]}") from e


# ──────────────────────────────────────────────────────────────────────
#  Complete table extraction
# ──────────────────────────────────────────────────────────────────────

# Runs under evaluate_readonly, so reading a table can never change the page. It deliberately avoids
# getElementById / closest / matches, which V8's side-effect-free mode rejects.
_TABLE_JS = r"""
(() => {
  const P = __PARAMS__;
  const clean = (s) => (s == null ? '' : String(s)).replace(/\s+/g, ' ').trim();
  const txt = (el) => clean(el.innerText != null && el.innerText !== '' ? el.innerText : el.textContent);
  const shown = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const roots = P.selector
    ? Array.from(document.querySelectorAll(P.selector))
    : Array.from(document.querySelectorAll('table, [role=table], [role=grid], [role=treegrid]'));
  const out = [];
  let skipped_hidden = 0;
  for (const root of roots) {
    if (out.length >= P.max_tables) break;
    const isTable = root.tagName === 'TABLE';
    if (!P.selector && !shown(root)) { skipped_hidden++; continue; }
    let rowEls, headerRowCount = 0;
    if (isTable) {
      rowEls = Array.from(root.rows);
    } else {
      rowEls = Array.from(root.querySelectorAll('[role=row]'));
    }
    if (rowEls.length === 0) continue;
    const cellsOf = (r) => isTable
      ? Array.from(r.cells)
      : Array.from(r.querySelectorAll('[role=columnheader],[role=rowheader],[role=cell],[role=gridcell]'));
    // Expand colspan/rowspan so every row has the same number of columns.
    const grid = [], pending = [];
    const isHeaderCell = (c) => c.tagName === 'TH' || c.getAttribute('role') === 'columnheader';
    const rowIsHeader = [];
    for (const r of rowEls) {
      const cells = cellsOf(r);
      const row = [];
      let col = 0;
      const flushPending = () => { while (pending[col] && pending[col].left > 0) { row[col] = pending[col].text; pending[col].left--; col++; } };
      flushPending();
      for (const c of cells) {
        flushPending();
        const text = txt(c);
        const cs = Math.max(1, parseInt(c.getAttribute('colspan') || '1', 10) || 1);
        const rs = Math.max(1, parseInt(c.getAttribute('rowspan') || '1', 10) || 1);
        for (let k = 0; k < cs; k++) {
          row[col] = text;
          if (rs > 1) pending[col] = { text, left: rs - 1 };
          col++;
        }
      }
      flushPending();
      for (let i = 0; i < row.length; i++) if (row[i] === undefined) row[i] = '';
      grid.push(row);
      rowIsHeader.push(cells.length > 0 && cells.every(isHeaderCell));
    }
    // Header = leading rows made only of header cells (or the thead rows).
    let h = 0;
    while (h < rowIsHeader.length && rowIsHeader[h]) h++;
    if (h === 0 && isTable && root.tHead && root.tHead.rows.length) h = root.tHead.rows.length;
    const headers = h > 0 ? grid[h - 1] : [];
    const body = grid.slice(h);
    const columns = grid.reduce((m, r) => Math.max(m, r.length), 0);
    const sc = root.scrollHeight > root.clientHeight + 4 && getComputedStyle(root).overflowY !== 'visible';
    const ariaRows = parseInt(root.getAttribute('aria-rowcount') || '', 10);
    let caption = '';
    if (isTable && root.caption) caption = txt(root.caption);
    if (!caption) caption = clean(root.getAttribute('aria-label') || '');
    if (!caption) {
      let prev = root.previousElementSibling, n = 0;
      while (prev && n < 3 && !caption) {
        if (/^H[1-6]$/.test(prev.tagName) || prev.tagName === 'CAPTION' || prev.tagName === 'LEGEND') caption = txt(prev);
        prev = prev.previousElementSibling; n++;
      }
    }
    const total = body.length;
    const start = Math.min(P.start_row, total);
    const end = Math.min(total, start + P.max_rows);
    out.push({
      index: out.length,
      id: root.id || '',
      caption: caption.slice(0, 160),
      kind: isTable ? 'table' : 'aria-grid',
      visible: shown(root),
      headers,
      header_rows: h,
      columns,
      total_rows: total,
      start_row: start,
      rows: body.slice(start, end),
      aria_rowcount: Number.isFinite(ariaRows) ? ariaRows : null,
      inner_scroll: !!sc,
    });
  }
  // Pagination and "showing X of Y" hints, used to say whether what we read is everything.
  const hintRe = /^(next|next page|older|more|load more|show more|›|»|>)$|^page\s*\d+$/i;
  const controls = [];
  for (const el of document.querySelectorAll('a,button,[role=button],[role=link],li')) {
    const label = clean(el.getAttribute('aria-label') || el.innerText || '').slice(0, 40);
    if (label && hintRe.test(label)) {
      const disabled = el.disabled === true || el.getAttribute('aria-disabled') === 'true' ||
        /disabled/i.test(String(el.className || ''));
      controls.push({ label, disabled });
      if (controls.length >= 8) break;
    }
  }
  let showing = null;
  const showRe = /(?:showing|displaying)?\s*([\d,]+)\s*(?:to|-|–)\s*([\d,]+)\s*of\s*([\d,]+)/i;
  for (const el of document.querySelectorAll('div,span,p,td,li')) {
    if (el.children.length > 2) continue;
    const t = clean(el.innerText);
    if (t.length > 4 && t.length < 120) {
      const m = showRe.exec(t);
      if (m) { showing = { from: +m[1].replace(/,/g, ''), to: +m[2].replace(/,/g, ''), of: +m[3].replace(/,/g, ''), text: t }; break; }
    }
  }
  const sizeSel = document.querySelector('select[name*=length],select[name*=size],select[aria-label*=entries i],select[aria-label*=rows i]');
  return {
    url: location.href,
    title: document.title,
    tables: out,
    candidates: roots.length,
    skipped_hidden,
    pagination: { controls, showing, page_size_control: !!sizeSel },
  };
})()
"""


def _table_completeness(table: Dict[str, Any], pagination: Dict[str, Any], truncated_by_size: bool) -> Dict[str, Any]:
    """Decide, from evidence, whether the rows returned are the whole table."""
    notes: List[str] = []
    total = int(table["total_rows"])
    returned = len(table["rows"])
    start = int(table["start_row"])
    complete = True
    if start + returned < total or truncated_by_size:
        complete = False
        notes.append(f"Returned rows {start + 1}-{start + returned} of {total} present in the page; "
                     f"call again with start_row={start + returned} for the rest.")
    aria = table.get("aria_rowcount")
    if isinstance(aria, int) and aria > 0 and aria > total + table["header_rows"]:
        complete = False
        notes.append(f"The table declares {aria} rows but only {total + table['header_rows']} are in the page "
                     "(rows are probably rendered on demand). Scroll the table and read again, or page through it.")
    next_enabled = [c for c in pagination.get("controls", []) if not c.get("disabled")]
    if next_enabled:
        complete = False
        notes.append("The page has more pages or a 'load more' control "
                     f"({', '.join(sorted({c['label'] for c in next_enabled}))}); the rows above are one page only.")
    showing = pagination.get("showing")
    if showing and showing.get("of", 0) > total:
        complete = False
        notes.append(f"The page says it is showing {showing['from']} to {showing['to']} of {showing['of']}; "
                     f"only {total} rows are in the page.")
    if pagination.get("page_size_control") and not next_enabled and not (showing and showing.get("of", 0) > total):
        notes.append("A page-size control exists; no sign of further pages was found.")
    return {"complete": complete, "notes": notes}


async def read_table(
    cdp: Any,
    *,
    selector: Optional[str] = None,
    table_index: Optional[int] = None,
    start_row: int = 0,
    max_rows: int = 500,
    max_chars: int = MAX_TABLE_OUTPUT_CHARS,
) -> Dict[str, Any]:
    """Read table(s) in full (not a text excerpt) and state plainly whether the result is complete."""
    if selector is not None and (not isinstance(selector, str) or not selector.strip() or len(selector) > 500):
        raise PageIOError("validation", "selector must be a non-empty string up to 500 characters.")
    start_row = max(0, int(start_row))
    max_rows = max(1, min(int(max_rows), MAX_TABLE_ROWS))
    max_chars = max(1000, min(int(max_chars), MAX_TABLE_OUTPUT_CHARS))
    params = {
        "selector": selector.strip() if selector else None,
        "start_row": start_row,
        "max_rows": max_rows,
        "max_tables": 12,
    }
    expr = _TABLE_JS.replace("__PARAMS__", json.dumps(params))
    res = await evaluate_readonly(cdp, expr, timeout_ms=4000, max_chars=MAX_TABLE_OUTPUT_CHARS * 8)
    if res["truncated"]:
        raise PageIOError("too_large", "The page's tables are too large to read in one call; pass a selector for one "
                                       "table and use start_row/max_rows to read it in parts.")
    data = res["value"] or {}
    tables = data.get("tables", [])
    if table_index is not None:
        tables = [t for t in tables if t["index"] == int(table_index)]
    if not tables:
        hint = "No visible table was found."
        if data.get("skipped_hidden"):
            hint += f" {data['skipped_hidden']} hidden table(s) were skipped; pass a selector to read one anyway."
        hint += " If the data is drawn in a canvas or built from divs without table roles, use browser_screenshot or browser_evaluate."
        return {"url": data.get("url"), "title": data.get("title"), "tables": [], "count": 0, "message": hint}

    # Fit the character budget: trim trailing rows (never silently) and say where to continue.
    budget = max_chars
    shaped = []
    for t in tables:
        rows = t["rows"]
        used = len(json.dumps(t["headers"], ensure_ascii=False))
        keep = 0
        for r in rows:
            used += len(json.dumps(r, ensure_ascii=False)) + 1
            if used > budget and keep > 0:
                break
            keep += 1
        trimmed = keep < len(rows)
        t["rows"] = rows[:keep]
        t["completeness"] = _table_completeness(t, data.get("pagination", {}), trimmed)
        if trimmed:
            t["next_start_row"] = t["start_row"] + keep
        elif t["start_row"] + keep < t["total_rows"]:
            t["next_start_row"] = t["start_row"] + keep
        shaped.append(t)
        budget = max(0, budget - used)
    return {
        "url": data.get("url"),
        "title": data.get("title"),
        "count": len(shaped),
        "tables": shaped,
        "pagination": data.get("pagination", {}),
        "complete": all(t["completeness"]["complete"] for t in shaped),
    }


# ──────────────────────────────────────────────────────────────────────
#  Viewport and screenshots
# ──────────────────────────────────────────────────────────────────────

async def measure_viewport(cdp: Any) -> Dict[str, float]:
    """CSS-pixel viewport, scroll offset and DPR (Page.getLayoutMetrics already includes browser zoom)."""
    metrics, dpr_res = await asyncio.gather(
        cdp.send("Page.getLayoutMetrics", {}),
        cdp.send("Runtime.evaluate", {"expression": "window.devicePixelRatio || 1", "returnByValue": True}),
    )
    vv = metrics.get("cssVisualViewport") or metrics.get("visualViewport") or {}
    lv = metrics.get("cssLayoutViewport") or metrics.get("layoutViewport") or {}
    width = vv.get("clientWidth") or lv.get("clientWidth") or 0
    height = vv.get("clientHeight") or lv.get("clientHeight") or 0
    return {
        "width": float(width),
        "height": float(height),
        "scroll_x": float(vv.get("pageX", 0.0)),
        "scroll_y": float(vv.get("pageY", 0.0)),
        "dpr": float(dpr_res.get("result", {}).get("value", 1.0) or 1.0),
    }


def image_size(data: bytes) -> Tuple[int, int]:
    """Pixel size of a JPEG or PNG without a dependency."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return int(w), int(h)
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
    raise PageIOError("screenshot", "Could not read the size of the captured image.")


async def capture_screenshot(
    cdp: Any,
    *,
    document_generation: int = 0,
    max_dim: int = 1280,
    quality: int = 72,
) -> Tuple[ViewportInfo, str]:
    """
    Capture the visible viewport as a JPEG no larger than the image budget.
    Returns (ViewportInfo, base64). The ViewportInfo is built from the pixels actually produced, so
    coordinate conversion stays correct even when the display scale factor changes the image size.
    """
    vp = await measure_viewport(cdp)
    if vp["width"] <= 0 or vp["height"] <= 0:
        raise PageIOError("screenshot", "The page has no visible viewport (is the tab hidden or still loading?).")
    probe = build_viewport_info("probe", vp["width"], vp["height"], max_dim=max_dim)
    target_scale = probe.scale / max(vp["dpr"], 1.0)  # clip.scale multiplies the device-pixel size

    async def shoot(scale: float) -> bytes:
        res = await cdp.send("Page.captureScreenshot", {
            "format": "jpeg",
            "quality": int(quality),
            "fromSurface": True,
            "captureBeyondViewport": False,
            "clip": {"x": vp["scroll_x"], "y": vp["scroll_y"], "width": vp["width"], "height": vp["height"], "scale": scale},
        })
        return base64.b64decode(res["data"])

    raw = await shoot(target_scale)
    w, h = image_size(raw)
    if max(w, h) > max_dim * 1.1:  # the display scale factor made it larger than asked: shrink once
        raw = await shoot(target_scale * max_dim / max(w, h))
        w, h = image_size(raw)
    info = ViewportInfo(
        screenshot_id=uuid.uuid4().hex[:8],
        viewport_width=int(round(vp["width"])),
        viewport_height=int(round(vp["height"])),
        screenshot_width=w,
        screenshot_height=h,
        device_pixel_ratio=vp["dpr"],
        scroll_x=vp["scroll_x"],
        scroll_y=vp["scroll_y"],
        document_generation=document_generation,
    )
    return info, base64.b64encode(raw).decode("ascii")


# ──────────────────────────────────────────────────────────────────────
#  Keyboard
# ──────────────────────────────────────────────────────────────────────

_MODIFIER_BITS = {"alt": 1, "option": 1, "control": 2, "ctrl": 2, "meta": 4, "cmd": 4, "command": 4, "shift": 8}
_MODIFIER_KEYS = {  # (key, code, windowsVirtualKeyCode)
    1: ("Alt", "AltLeft", 18), 2: ("Control", "ControlLeft", 17), 4: ("Meta", "MetaLeft", 91), 8: ("Shift", "ShiftLeft", 16),
}
_NAMED_KEYS = {
    "enter": ("Enter", "Enter", 13, "\r"), "return": ("Enter", "Enter", 13, "\r"),
    "tab": ("Tab", "Tab", 9, None), "escape": ("Escape", "Escape", 27, None), "esc": ("Escape", "Escape", 27, None),
    "backspace": ("Backspace", "Backspace", 8, None), "delete": ("Delete", "Delete", 46, None),
    "space": (" ", "Space", 32, " "), "insert": ("Insert", "Insert", 45, None),
    "arrowleft": ("ArrowLeft", "ArrowLeft", 37, None), "arrowup": ("ArrowUp", "ArrowUp", 38, None),
    "arrowright": ("ArrowRight", "ArrowRight", 39, None), "arrowdown": ("ArrowDown", "ArrowDown", 40, None),
    "left": ("ArrowLeft", "ArrowLeft", 37, None), "up": ("ArrowUp", "ArrowUp", 38, None),
    "right": ("ArrowRight", "ArrowRight", 39, None), "down": ("ArrowDown", "ArrowDown", 40, None),
    "home": ("Home", "Home", 36, None), "end": ("End", "End", 35, None),
    "pageup": ("PageUp", "PageUp", 33, None), "pagedown": ("PageDown", "PageDown", 34, None),
}
for _n in range(1, 13):
    _NAMED_KEYS[f"f{_n}"] = (f"F{_n}", f"F{_n}", 111 + _n, None)
_PUNCT = {  # char -> (code, windowsVirtualKeyCode, needs_shift, unshifted char)
    ",": ("Comma", 188, False, ","), ".": ("Period", 190, False, "."), "/": ("Slash", 191, False, "/"),
    ";": ("Semicolon", 186, False, ";"), "'": ("Quote", 222, False, "'"), "[": ("BracketLeft", 219, False, "["),
    "]": ("BracketRight", 221, False, "]"), "\\": ("Backslash", 220, False, "\\"), "-": ("Minus", 189, False, "-"),
    "=": ("Equal", 187, False, "="), "`": ("Backquote", 192, False, "`"),
    "<": ("Comma", 188, True, ","), ">": ("Period", 190, True, "."), "?": ("Slash", 191, True, "/"),
    ":": ("Semicolon", 186, True, ";"), '"': ("Quote", 222, True, "'"), "_": ("Minus", 189, True, "-"),
    "+": ("Equal", 187, True, "="), "!": ("Digit1", 49, True, "1"), "@": ("Digit2", 50, True, "2"),
    "#": ("Digit3", 51, True, "3"), "$": ("Digit4", 52, True, "4"), "%": ("Digit5", 53, True, "5"),
    "^": ("Digit6", 54, True, "6"), "&": ("Digit7", 55, True, "7"), "*": ("Digit8", 56, True, "8"),
    "(": ("Digit9", 57, True, "9"), ")": ("Digit0", 48, True, "0"),
}
_EDIT_COMMANDS = {"a": "selectAll", "c": "copy", "x": "cut", "v": "paste", "z": "undo", "y": "redo"}


def _platform_modifier() -> int:
    return 4 if sys.platform == "darwin" else 2


def parse_key_token(token: str) -> Dict[str, Any]:
    """
    'Enter', 'a', 'A', 'ArrowLeft', 'Control+a', 'Shift+Tab', 'ControlOrMeta+Enter' ->
    {modifiers: bitmask, key, code, vk, text}. Raises PageIOError for anything it cannot map exactly.
    """
    raw = token if token == " " else (token or "").strip()   # a lone space is the Space key, not an empty token
    if not raw:
        raise PageIOError("validation", "empty key.")
    parts = raw.split("+") if len(raw) > 1 else [raw]
    # a literal plus key is written "Shift++" or "+" ; rejoin trailing empty part
    if raw.endswith("+") and len(raw) > 1:
        parts = raw[:-1].split("+")
        parts[-1] = "+" if parts[-1] == "" else parts[-1] + "+"
        parts = [p for p in parts if p != ""] or ["+"]
    modifiers = 0
    for p in parts[:-1]:
        low = p.strip().lower()
        if low in ("controlormeta", "ctrlormeta", "cmdorctrl"):
            modifiers |= _platform_modifier()
        elif low in _MODIFIER_BITS:
            modifiers |= _MODIFIER_BITS[low]
        else:
            raise PageIOError("validation", f"unknown modifier '{p}' in '{raw}'. Use Control, Shift, Alt, Meta or ControlOrMeta.")
    main = parts[-1] if parts[-1] == " " else parts[-1].strip()
    low = main.lower()
    if low in _NAMED_KEYS:
        key, code, vk, text = _NAMED_KEYS[low]
        return {"modifiers": modifiers, "key": key, "code": code, "vk": vk, "text": text, "token": raw}
    if len(main) == 1:
        ch = main
        if ch.isalpha() and ch.isascii():
            shift = ch.isupper()
            return {"modifiers": modifiers | (8 if shift else 0), "key": ch, "code": f"Key{ch.upper()}",
                    "vk": ord(ch.upper()), "text": ch, "token": raw, "char": ch}
        if ch.isdigit():
            return {"modifiers": modifiers, "key": ch, "code": f"Digit{ch}", "vk": ord(ch), "text": ch, "token": raw, "char": ch}
        if ch in _PUNCT:
            code, vk, needs_shift, _base = _PUNCT[ch]
            return {"modifiers": modifiers | (8 if needs_shift else 0), "key": ch, "code": code, "vk": vk, "text": ch,
                    "token": raw, "char": ch}
        if ch == " ":
            return {"modifiers": modifiers, "key": " ", "code": "Space", "vk": 32, "text": " ", "token": raw, "char": " "}
    raise PageIOError(
        "validation",
        f"'{main}' is not a key I can press. Use a single character, or one of: Enter, Tab, Escape, Backspace, Delete, "
        "Space, ArrowLeft/Right/Up/Down, Home, End, PageUp, PageDown, F1-F12, optionally with modifiers like Control+a.",
    )


MAX_KEY_TEXT = 50  # longer text is prose, not game input
MAX_TEXT_ENTRIES_PER_CALL = 2000  # a block of text: inserted pieces plus Enter/Tab presses (a 200 x 5 table fits)


def plan_keys(keys: Sequence[str], text: Optional[str]) -> List[Dict[str, Any]]:
    """
    Turn a keys list (and optional text) into validated key specs.
    Short text is typed as individual key presses, for games and editors that react to key events. Text that is long,
    or characters with no key (rupee sign, accents, curly quotes), is inserted as text instead, a line at a time with
    Enter between the lines: that is how a paragraph gets into an editor such as a rich-text box inside an iframe.
    A tab character becomes a real Tab press, so rows of tab-separated cells fill a spreadsheet: Tab moves to the next
    cell, Enter to the next row.
    """
    plan: List[Dict[str, Any]] = []
    if text and len(text) > MAX_KEY_TEXT:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            cells = line.split("\t")
            for j, cell in enumerate(cells):
                if cell:
                    plan.append({"insert": cell, "token": f"<{len(cell)} characters>"})
                if j < len(cells) - 1:
                    plan.append(parse_key_token("Tab"))
            if i < len(lines) - 1:
                plan.append(parse_key_token("Enter"))
        if len(plan) > MAX_TEXT_ENTRIES_PER_CALL:
            raise PageIOError("validation", f"this text needs {len(plan)} entries; the limit is {MAX_TEXT_ENTRIES_PER_CALL} per call. "
                                            "Send it in parts.")
    elif text:
        for ch in text:
            try:
                plan.append(parse_key_token({"\n": "Enter", "\t": "Tab"}.get(ch, ch)))
            except PageIOError:
                plan.append({"insert": ch, "token": ch})
    long_text = bool(text and len(text) > MAX_KEY_TEXT)
    for k in keys or []:
        plan.append(parse_key_token(k))
    if not plan:
        raise PageIOError("validation", "give at least one key, or text to type as key presses.")
    if not long_text and len(plan) > MAX_KEYS_PER_CALL:
        raise PageIOError("validation", f"{len(plan)} key presses requested; the limit is {MAX_KEYS_PER_CALL} per call.")
    return plan


async def press_keys(cdp: Any, plan: Sequence[Dict[str, Any]], *, delay_ms: int = 25) -> Dict[str, Any]:
    """Dispatch key presses to whatever has focus in the page."""
    delay = max(0, min(int(delay_ms), 1000)) / 1000.0
    pressed: List[str] = []
    for spec in plan:
        if "insert" in spec:
            await cdp.send("Input.insertText", {"text": spec["insert"]})
            pressed.append(spec["token"])
            if delay:
                await asyncio.sleep(delay)
            continue
        mods = spec["modifiers"]
        down_mods = [m for m in (2, 4, 1, 8) if mods & m]
        acc = 0
        for m in down_mods:  # modifiers go down first, in order
            acc |= m
            key, code, vk = _MODIFIER_KEYS[m]
            await cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "modifiers": acc, "key": key, "code": code,
                                                      "windowsVirtualKeyCode": vk})
        text = spec.get("text")
        chord = bool(mods & (1 | 2 | 4))  # alt/ctrl/meta chords do not produce text
        down: Dict[str, Any] = {
            "type": "keyDown" if (text and not chord) else "rawKeyDown",
            "modifiers": mods, "key": spec["key"], "code": spec["code"],
            "windowsVirtualKeyCode": spec["vk"],
        }
        if text and not chord:
            down["text"] = text
            down["unmodifiedText"] = text if not (mods & 8) else text.lower()
        if chord and spec.get("char"):
            cmd = _EDIT_COMMANDS.get(str(spec["char"]).lower())
            if cmd and (mods & 6):
                down["commands"] = [cmd]
        await cdp.send("Input.dispatchKeyEvent", down)
        await cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": mods, "key": spec["key"], "code": spec["code"],
                                                  "windowsVirtualKeyCode": spec["vk"]})
        for m in reversed(down_mods):
            key, code, vk = _MODIFIER_KEYS[m]
            acc &= ~m
            await cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": acc, "key": key, "code": code,
                                                      "windowsVirtualKeyCode": vk})
        pressed.append(spec["token"])
        if delay:
            await asyncio.sleep(delay)
    return {"pressed": pressed, "count": len(pressed)}


# ──────────────────────────────────────────────────────────────────────
#  Scrolling and pointer
# ──────────────────────────────────────────────────────────────────────

async def scroll_wheel(cdp: Any, x: float, y: float, delta_x: float, delta_y: float) -> Dict[str, Any]:
    before = await measure_viewport(cdp)
    await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    await cdp.send("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y,
                                                "deltaX": delta_x, "deltaY": delta_y, "pointerType": "mouse"})
    await asyncio.sleep(0.18)  # let smooth scrolling settle
    after = await measure_viewport(cdp)
    moved_y = after["scroll_y"] - before["scroll_y"]
    moved_x = after["scroll_x"] - before["scroll_x"]
    return {"scrolled_x": moved_x, "scrolled_y": moved_y, "scroll_x": after["scroll_x"], "scroll_y": after["scroll_y"],
            "moved": abs(moved_x) > 0.5 or abs(moved_y) > 0.5}


async def scroll_into_view(cdp: Any, selector: str) -> Dict[str, Any]:
    doc = await cdp.send("DOM.getDocument", {"depth": 0})
    root = doc.get("root", {}).get("nodeId")
    found = await cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})
    node_id = found.get("nodeId")
    if not node_id:
        raise PageIOError("not_found", f"No element matches {selector!r}; it may have changed since it was inspected.")
    await cdp.send("DOM.scrollIntoViewIfNeeded", {"nodeId": node_id})
    vp = await measure_viewport(cdp)
    return {"scroll_x": vp["scroll_x"], "scroll_y": vp["scroll_y"]}


async def describe_point(cdp: Any, x: float, y: float) -> Dict[str, Any]:
    """What is under a viewport point: used to report (and verify) what a coordinate action will hit."""
    try:
        hit = await cdp.send("DOM.getNodeForLocation", {"x": int(round(x)), "y": int(round(y)),
                                                        "includeUserAgentShadowDOM": False})
        bid = hit.get("backendNodeId")
        if not bid:
            return {"found": False}
        node = (await cdp.send("DOM.describeNode", {"backendNodeId": bid})).get("node", {})
        attrs = node.get("attributes") or []
        amap = {attrs[i]: attrs[i + 1] for i in range(0, len(attrs) - 1, 2)}
        label = amap.get("aria-label") or amap.get("title") or amap.get("alt") or amap.get("value") or ""
        if not label:
            try:
                html = (await cdp.send("DOM.getOuterHTML", {"backendNodeId": bid})).get("outerHTML", "")
                import re as _re
                label = _re.sub(r"<[^>]+>", " ", html)
                label = " ".join(label.split())[:80]
            except Exception:
                label = ""
        return {"found": True, "tag": str(node.get("nodeName", "")).lower(), "id": amap.get("id", ""),
                "class": amap.get("class", "")[:80], "label": label[:80], "backend_node_id": bid}
    except Exception as e:  # a failed hit-test must not block the action itself
        return {"found": False, "error": str(e)[:120]}


async def pointer_action(
    cdp: Any,
    kind: str,
    x: float,
    y: float,
    *,
    to_x: Optional[float] = None,
    to_y: Optional[float] = None,
    button: str = "left",
    clicks: int = 1,
    steps: int = 14,
    cursor_hook: Any = None,
    tab_id: str = "",
) -> Dict[str, Any]:
    """click | double_click | right_click | move | drag, in CSS viewport pixels."""
    buttons_mask = {"left": 1, "right": 2, "middle": 4}.get(button, 1)
    result: Dict[str, Any] = {"kind": kind}
    if cursor_hook:
        try:
            cursor_hook(x, y, button, tab_id)
        except Exception:
            pass
    if kind == "move":
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        return result
    if kind in ("click", "double_click", "right_click"):
        n = 2 if kind == "double_click" else clicks
        b = "right" if kind == "right_click" else button
        mask = {"left": 1, "right": 2, "middle": 4}.get(b, 1)
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        for i in range(1, n + 1):
            await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": b,
                                                        "buttons": mask, "clickCount": i})
            await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": b,
                                                        "buttons": 0, "clickCount": i})
        return result
    if kind == "drag":
        if to_x is None or to_y is None:
            raise PageIOError("validation", "a drag needs both a start and an end point.")
        steps = max(2, min(int(steps), MAX_DRAG_STEPS))
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left",
                                                    "buttons": 1, "clickCount": 1})
        for i in range(1, steps + 1):
            t = i / steps
            await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x + (to_x - x) * t, "y": y + (to_y - y) * t,
                                                        "button": "left", "buttons": 1})
            await asyncio.sleep(0.006)
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": to_x, "y": to_y, "button": "left",
                                                    "buttons": 0, "clickCount": 1})
        result.update({"to_x": to_x, "to_y": to_y, "steps": steps})
        return result
    raise PageIOError("validation", f"unknown pointer action '{kind}'. Use click, double_click, right_click, move or drag.")


# ──────────────────────────────────────────────────────────────────────
#  Form controls
# ──────────────────────────────────────────────────────────────────────

# A fixed function (never model-authored) that chooses an option in a native <select> the way a user does and fires the
# events a page listens for. Native dropdown popups are not drawn in screenshots, so this is the only reliable path.
_SELECT_JS = r"""
((sel, want) => {
  const el = document.querySelector(sel);
  if (!el) return { error: 'not_found' };
  if (el.tagName !== 'SELECT') return { error: 'not_select', tag: el.tagName.toLowerCase() };
  if (el.disabled) return { error: 'disabled' };
  const norm = (t) => (t || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const opts = Array.from(el.options);
  let hit = opts.find(o => o.value === want) || opts.find(o => norm(o.text) === norm(want)) ||
            opts.find(o => norm(o.text).startsWith(norm(want)));
  if (!hit) return { error: 'no_such_option', options: opts.slice(0, 40).map(o => o.text.trim()) };
  if (hit.disabled) return { error: 'option_disabled' };
  el.value = hit.value;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return { selected: { value: hit.value, label: hit.text.trim() }, options: opts.length };
})
"""


async def select_option(cdp: Any, selector: str, value: str) -> Dict[str, Any]:
    if not isinstance(selector, str) or not selector.strip() or len(selector) > 500:
        raise PageIOError("validation", "selector must be a non-empty string up to 500 characters.")
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise PageIOError("validation", "value must be the option's value or visible text (up to 200 characters).")
    res = await cdp.send("Runtime.evaluate", {
        "expression": f"({_SELECT_JS.strip()})({json.dumps(selector.strip())}, {json.dumps(value.strip())})",
        "returnByValue": True, "timeout": 2000, "silent": True,
    })
    if res.get("exceptionDetails"):
        raise PageIOError("js_error", str(res["exceptionDetails"].get("text", "error"))[:200])
    out = res.get("result", {}).get("value") or {}
    err = out.get("error")
    if err == "not_found":
        raise PageIOError("not_found", f"No element matches {selector!r}; it may have changed since it was inspected.")
    if err == "not_select":
        raise PageIOError("validation", f"That element is a <{out.get('tag')}>, not a dropdown. Use click for it, or type for text fields.")
    if err == "no_such_option":
        raise PageIOError("validation", f"No option matches {value!r}. Options: {out.get('options')}")
    if err:
        raise PageIOError("blocked", f"The dropdown cannot be changed ({err}).")
    return out


# ──────────────────────────────────────────────────────────────────────
#  Waiting on state, not on time
# ──────────────────────────────────────────────────────────────────────

_FINGERPRINT_JS = ("(() => { const b = document.body; return [document.readyState, b ? b.innerText.length : 0, "
                   "document.documentElement.scrollHeight, document.querySelectorAll('*').length, location.href]; })()")


_WAIT_TYPES = ("idle", "text", "text_gone", "selector", "js", "url_contains")


def normalize_wait_condition(condition: Any) -> Dict[str, Any]:
    """
    Accept the shapes a model naturally writes and return a condition with a 'type':
        {"text": "Added to cart"}  {"selector": "#done"}  {"url": "/checkout"}  {"expected": "Done"}  {"reason": "settle"}
    A condition that already has a type is returned unchanged.
    """
    if not isinstance(condition, dict):
        raise PageIOError("validation", "condition must be an object, for example {\"type\": \"text\", \"expected\": \"Added to cart\"}.")
    if condition.get("type"):
        return condition
    c = dict(condition)
    for key, ctype, field in (("text_gone", "text_gone", "expected"), ("text", "text", "expected"),
                              ("url_contains", "url_contains", "expected"), ("url", "url_contains", "expected"),
                              ("selector", "selector", "selector"), ("js", "js", "expression"), ("expression", "js", "expression")):
        if c.get(key):
            c["type"] = ctype
            c.setdefault(field, c[key])
            return c
    if c.get("expected"):
        c["type"] = "text"
        return c
    if not (set(c) - {"reason", "quiet_ms"}):
        c["type"] = "idle"   # nothing named to wait for: wait for the page to settle
        return c
    raise PageIOError("validation", f"condition needs a 'type' ({', '.join(_WAIT_TYPES)}).")


async def wait_for(
    cdp: Any,
    state: Any,
    condition: Dict[str, Any],
    *,
    timeout_ms: int = 5000,
    poll_ms: int = 100,
) -> Dict[str, Any]:
    """
    Wait until a typed condition holds. Returns {met, waited_ms, detail}; never raises on timeout, so a
    caller can decide what a missed condition means.
        {"type": "idle"}                                  page stopped loading and stopped changing
        {"type": "text", "expected": "..."}               visible text contains the string
        {"type": "text_gone", "expected": "..."}
        {"type": "selector", "selector": "...", "state": "visible|hidden|exists"}
        {"type": "js", "expression": "..."}               read-only expression becomes truthy
        {"type": "url_contains", "expected": "..."}
    """
    condition = normalize_wait_condition(condition)
    ctype = str(condition.get("type", ""))
    timeout_ms = max(100, min(int(timeout_ms), 30000))
    poll = max(50, min(int(poll_ms), 1000)) / 1000.0
    t0 = time.monotonic()
    deadline = t0 + timeout_ms / 1000.0

    async def check() -> Tuple[bool, str]:
        if ctype == "text" or ctype == "text_gone":
            exp = json.dumps(str(condition.get("expected", "")))
            r = await evaluate_readonly(cdp, f"(document.body ? document.body.innerText : '').includes({exp})", timeout_ms=800)
            present = bool(r["value"])
            return (present if ctype == "text" else not present), f"text {'present' if present else 'absent'}"
        if ctype == "selector":
            sel = json.dumps(str(condition.get("selector", "")))
            want = str(condition.get("state", "visible"))
            js = (f"(() => {{ const e = document.querySelector({sel}); if (!e) return 'missing'; "
                  f"const r = e.getBoundingClientRect(); return (r.width > 0 && r.height > 0) ? 'visible' : 'hidden'; }})()")
            r = (await evaluate_readonly(cdp, js, timeout_ms=800))["value"]
            ok = (want == "exists" and r != "missing") or (want == "visible" and r == "visible") or \
                 (want == "hidden" and r in ("hidden", "missing"))
            return ok, f"element is {r}"
        if ctype == "js":
            r = await evaluate_readonly(cdp, str(condition.get("expression", "false")), timeout_ms=800)
            return bool(r["value"]), f"expression -> {str(r['value'])[:60]}"
        if ctype == "url_contains":
            r = await evaluate_readonly(cdp, "location.href", timeout_ms=800)
            return str(condition.get("expected", "")) in str(r["value"]), f"url {r['value']}"
        if ctype == "idle":
            return False, "idle"  # handled below
        raise PageIOError("validation", f"unknown wait condition '{ctype}'.")

    if ctype != "idle":
        last = ""
        while True:
            ok, last = await check()
            if ok:
                return {"met": True, "waited_ms": int((time.monotonic() - t0) * 1000), "detail": last}
            if time.monotonic() >= deadline:
                return {"met": False, "waited_ms": int((time.monotonic() - t0) * 1000), "detail": f"timed out; last: {last}"}
            await asyncio.sleep(poll)

    # idle: not navigating, no in-flight requests, DOM quiet and a stable fingerprint
    quiet = max(0.15, float(condition.get("quiet_ms", 300)) / 1000.0)
    prev, stable_since = None, None
    while True:
        busy = False
        if state is not None:
            busy = bool(getattr(state, "is_navigating", False)) or bool(getattr(state, "active_requests", None))
        fp = None
        if not busy:
            try:
                fp = (await evaluate_readonly(cdp, _FINGERPRINT_JS, timeout_ms=800))["value"]
            except PageIOError:
                fp = None  # mid-navigation: keep waiting
        now = time.monotonic()
        if fp is not None and fp == prev and fp[0] in ("complete", "interactive"):
            stable_since = stable_since or now
            if now - stable_since >= quiet:
                return {"met": True, "waited_ms": int((now - t0) * 1000), "detail": "page is idle"}
        else:
            stable_since = None
        prev = fp
        if now >= deadline:
            return {"met": False, "waited_ms": int((now - t0) * 1000), "detail": "page was still changing at the deadline"}
        await asyncio.sleep(poll)
