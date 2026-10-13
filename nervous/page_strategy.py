"""
Comex Browser Nervous System: which way to perceive and act on this page.

A cheap, local, deterministic classification of a page from facts gathered in one read-only call.
No model call is involved: the agent gets the verdict and the reasons with the page state, so it can
start on the right path instead of discovering the wrong one by failing.

    semantic  ordinary page: inspect / find / click / type by text or ref (the fast default)
    table     dense tabular data: read it whole with read_table, then check its completeness flag
    visual    meaning is drawn (canvas, almost no DOM): screenshot, then keys and coordinate pointer
    mixed     both a drawing surface and many ordinary controls: use controls for chrome, vision for the surface
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

# Runs under evaluate_readonly (engine-enforced read-only). Avoids getElementById/closest/matches.
_PERCEPTION_JS = r"""
(() => {
  const vw = innerWidth, vh = innerHeight, va = Math.max(1, vw * vh);
  const INTERACTIVE = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], ' +
    '[role=tab], [role=menuitem], [role=checkbox], [role=radio], [role=option], [role=switch], [role=combobox], ' +
    '[role=searchbox], [role=textbox], [contenteditable=true], [tabindex="0"]';
  const shown = (r) => r.width > 1 && r.height > 1 && r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw;
  let interactive = 0;
  for (const el of document.querySelectorAll(INTERACTIVE)) { if (shown(el.getBoundingClientRect())) interactive++; if (interactive >= 400) break; }
  const canvases = [];
  for (const c of document.querySelectorAll('canvas')) {
    const r = c.getBoundingClientRect(); if (!shown(r)) continue;
    const w = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)), h = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
    canvases.push({ x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), share: +(w * h / va).toFixed(2) });
  }
  canvases.sort((a, b) => b.share - a.share);
  // Large gesture/board surfaces made of ordinary elements (chess boards, maps, sliders): no semantics inside them.
  const surfaces = [];
  let surfaceEl = null;
  let scanned = 0;
  for (const el of document.querySelectorAll('div,section,main,svg,figure')) {
    if (++scanned > 1500) break;
    const r = el.getBoundingClientRect();
    if (r.width * r.height < 0.12 * va || !shown(r)) continue;
    const cs = getComputedStyle(el);
    const why = cs.touchAction === 'none' ? 'touch-action:none' : (cs.userSelect === 'none' && cs.cursor === 'pointer' ? 'pointer cursor' : '');
    if (why) { surfaces.push({ share: +(Math.min(1, r.width * r.height / va)).toFixed(2), tag: el.tagName.toLowerCase(), why });
               if (!surfaceEl) surfaceEl = el; }
    if (surfaces.length >= 3) break;
  }
  // Geometry of the first board-like surface and of what is drawn inside it, in viewport pixels
  let surface = null;
  if (surfaceEl) {
    const r = surfaceEl.getBoundingClientRect();
    const kids = [];
    let total = 0;
    for (const k of surfaceEl.querySelectorAll('*')) {
      const kr = k.getBoundingClientRect();
      if (kr.width < 1 || kr.height < 1) continue;
      total++;
      if (kids.length < 48) kids.push({ c: String(k.getAttribute('class') || k.tagName.toLowerCase()).slice(0, 48),
        x: Math.round(kr.left), y: Math.round(kr.top), w: Math.round(kr.width), h: Math.round(kr.height) });
    }
    surface = { tag: surfaceEl.tagName.toLowerCase(), id: surfaceEl.id || '', x: Math.round(r.left), y: Math.round(r.top),
                w: Math.round(r.width), h: Math.round(r.height), children_total: total, children: kids };
  }
  let tables = 0, bigTables = 0;
  for (const t of document.querySelectorAll('table, [role=table], [role=grid]')) {
    const r = t.getBoundingClientRect(); if (r.width < 1) continue; tables++;
    const rows = t.tagName === 'TABLE' ? t.rows.length : t.querySelectorAll('[role=row]').length;
    if (rows >= 5) bigTables++;
  }
  const a = document.activeElement;
  return {
    url: location.href, title: document.title, ready_state: document.readyState,
    text_chars: document.body ? document.body.innerText.length : 0,
    interactive, canvases: canvases.slice(0, 3), surfaces, surface, tables, big_tables: bigTables,
    iframes: document.querySelectorAll('iframe').length,
    scroll_height: document.documentElement.scrollHeight,
    focused: a ? { tag: a.tagName.toLowerCase(), id: a.id || '', type: a.getAttribute('type') || '' } : null,
  };
})()
"""


def choose_strategy(facts: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    canvases = facts.get("canvases") or []
    big_canvas = bool(canvases) and canvases[0].get("share", 0) >= 0.30
    interactive = int(facts.get("interactive", 0))
    text_chars = int(facts.get("text_chars", 0))
    big_tables = int(facts.get("big_tables", 0))

    surfaces = facts.get("surfaces") or []
    if big_canvas and interactive >= 12:
        path = "mixed"
        reasons.append(f"a canvas covers {int(canvases[0]['share'] * 100)}% of the viewport and the page also has {interactive} ordinary controls")
    elif big_canvas:
        path = "visual"
        reasons.append(f"a canvas covers {int(canvases[0]['share'] * 100)}% of the viewport with only {interactive} interactive elements")
    elif surfaces:
        path = "mixed" if interactive >= 12 else "visual"
        reasons.append(f"a large {surfaces[0]['tag']} ({int(surfaces[0]['share'] * 100)}% of the viewport, {surfaces[0]['why']}) behaves like a board or "
                       "canvas: its parts are not separate controls, so read it with browser_evaluate and act by coordinates")
    elif text_chars < 20 and interactive == 0 and facts.get("ready_state") == "complete":
        path = "visual"
        reasons.append("the page has no text and no interactive elements: the content is probably drawn")
    elif big_tables:
        path = "table"
        reasons.append(f"{big_tables} table(s) with 5 or more rows")
    else:
        path = "semantic"
        reasons.append(f"{interactive} interactive elements and {text_chars} characters of text")

    suggest = {
        "semantic": ["browser_inspect", "browser_find", "browser_click", "browser_type"],
        "table": ["browser_read_table", "browser_inspect"],
        "visual": ["browser_screenshot", "browser_pointer", "browser_keys", "browser_evaluate"],
        "mixed": ["browser_inspect", "browser_screenshot", "browser_pointer", "browser_keys"],
    }[path]
    if facts.get("iframes"):
        reasons.append(f"{facts['iframes']} iframe(s): content inside them is only reachable by coordinates")
    return {"path": path, "reasons": reasons, "suggest": suggest}


def describe_grid(surface: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    If a board-like surface is a regular grid (chess, checkers, sudoku, minesweeper, 2048...), work out the cell size and
    which cell each child element sits in, so the model can act without spending calls reading geometry. Returns None when
    the surface is not a clean grid. Cells are counted from the top-left: col 0 is the left edge, row 0 the top edge.
    """
    if not surface or not surface.get("children"):
        return None
    kids = surface["children"]
    sizes = Counter((k["w"], k["h"]) for k in kids if k["w"] >= 8 and k["h"] >= 8)
    if not sizes:
        return None
    (cw, ch), count = sizes.most_common(1)[0]
    if count < 2 or abs(cw - ch) > 2:
        return None
    cols, rows = round(surface["w"] / cw), round(surface["h"] / ch)
    tol = max(6, cw * 0.1)
    if not (3 <= cols <= 24 and 3 <= rows <= 24) or abs(cols * cw - surface["w"]) > tol or abs(rows * ch - surface["h"]) > tol:
        return None
    items = []
    for k in kids:
        if abs(k["w"] - cw) > 2 or abs(k["h"] - ch) > 2:
            continue
        col, row = round((k["x"] - surface["x"]) / cw), round((k["y"] - surface["y"]) / ch)
        if 0 <= col < cols and 0 <= row < rows:
            items.append({"c": k["c"], "col": col, "row": row})
    if not items:
        return None
    return {"cell": cw, "cols": cols, "rows": rows, "x": surface["x"], "y": surface["y"], "items": items,
            "complete": len(kids) >= surface.get("children_total", len(kids))}
