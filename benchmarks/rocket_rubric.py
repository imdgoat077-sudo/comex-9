"""
Scores the detailed Excalidraw rocket from the scene Excalidraw itself saved (the page's own state), never from what the agent says.

Defined BEFORE any measured run. Nine components, each true or false; the score is how many hold. A run is "complete" at 9 of 9.

    sky       a large dark filled rectangle
    body      a white filled shape, taller than wide, inside the sky
    nose      a red filled shape centred over the body and sitting on top of it
    stripes   two or more red filled shapes lying across the body
    porthole  two or more ellipses sharing a centre inside the body, at least one blue
    fins      a red filled shape on each side of the body, in its lower part
    engine    three or more grey or dark filled shapes below the body (engine base and nozzles)
    flames    an orange and a yellow filled shape below the body
    stars     five or more yellow filled shapes in the sky, outside the rocket

"Filled" means a non-transparent background colour (any fill style); `solid_ratio` also reports how many of the filled shapes use a solid fill.
"""

from __future__ import annotations

import colorsys
from typing import Any, Dict, List, Optional

# Version 2 (after the first Original runs showed two false negatives in version 1, both checked against screenshots):
#   - a line, arrow or freehand shape is measured by its real points, not by x + width (Excalidraw draws a triangle as a line whose
#     points may lie left of or above its starting point)
#   - "grey" now includes low-saturation, not-light colours such as slate (#8d99ae), which version 1 called blue
# Every saved trial is re-scored under both versions in benchmarks/rescore_rockets.py; version-1 scores are kept in each trial file.
RUBRIC_VERSION = 2

COMPONENTS = ["sky", "body", "nose", "stripes", "porthole", "fins", "engine", "flames", "stars"]


def _rgb(hexcol: Optional[str]):
    if not hexcol or not isinstance(hexcol, str) or not hexcol.startswith("#"):
        return None
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None


def color_class(hexcol: Optional[str]) -> str:
    rgb = _rgb(hexcol)
    if rgb is None:
        return "none"
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    hue = h * 360
    if v < 0.35:
        return "dark"
    if s < 0.18:
        if v > 0.88:
            return "white"
        return "grey" if v > 0.3 else "dark"
    if hue < 15 or hue >= 340:
        return "red"
    if hue < 42:
        return "orange"
    if hue < 70:
        return "yellow"
    if hue < 170:
        return "green"
    if hue < 262:
        return "blue"
    return "purple"


def _box(e: Dict[str, Any]):
    x, y, w, h = float(e.get("x", 0)), float(e.get("y", 0)), float(e.get("width", 0)), float(e.get("height", 0))
    pts = e.get("points")
    if e.get("type") in ("line", "arrow", "freedraw") and isinstance(pts, list) and pts:
        try:
            xs = [x + float(p[0]) for p in pts]
            ys = [y + float(p[1]) for p in pts]
            return min(xs), min(ys), max(xs), max(ys)
        except (TypeError, ValueError, IndexError):
            pass
    return min(x, x + w), min(y, y + h), max(x, x + w), max(y, y + h)


def greyish(hexcol: Optional[str]) -> bool:
    """Grey or dark, or a low-saturation colour that is not light (slate, steel): what an engine nozzle is drawn with."""
    c = color_class(hexcol)
    if c in ("grey", "dark"):
        return True
    rgb = _rgb(hexcol)
    if rgb is None:
        return False
    _, sat, val = colorsys.rgb_to_hsv(*rgb)
    return sat < 0.25 and val <= 0.8


def _filled(e: Dict[str, Any]) -> bool:
    return color_class(e.get("backgroundColor")) != "none"


def _fill(e: Dict[str, Any]) -> str:
    return color_class(e.get("backgroundColor"))


def _cx(b):
    return (b[0] + b[2]) / 2


def _cy(b):
    return (b[1] + b[3]) / 2


def score(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    els = [e for e in elements if not e.get("isDeleted") and e.get("type") not in ("text",)]
    res = {c: False for c in COMPONENTS}
    detail: Dict[str, Any] = {}

    skies = [e for e in els if e["type"] == "rectangle" and _filled(e) and _fill(e) == "dark"
             and (_box(e)[2] - _box(e)[0]) * (_box(e)[3] - _box(e)[1]) >= 400 * 300]
    sky_b = _box(max(skies, key=lambda e: (_box(e)[2] - _box(e)[0]) * (_box(e)[3] - _box(e)[1]))) if skies else None
    res["sky"] = bool(skies)

    def in_sky(b):
        return sky_b is None or (b[0] >= sky_b[0] - 5 and b[2] <= sky_b[2] + 5 and b[1] >= sky_b[1] - 5 and b[3] <= sky_b[3] + 5)

    bodies = [e for e in els if _filled(e) and _fill(e) == "white" and (_box(e)[3] - _box(e)[1]) >= 100
              and (_box(e)[3] - _box(e)[1]) > (_box(e)[2] - _box(e)[0]) and in_sky(_box(e))]
    body_b = _box(max(bodies, key=lambda e: _box(e)[3] - _box(e)[1])) if bodies else None
    res["body"] = bool(bodies)
    if body_b is None:
        return _result(res, els, detail)
    bw, bh = body_b[2] - body_b[0], body_b[3] - body_b[1]

    reds = [e for e in els if _filled(e) and _fill(e) == "red"]
    res["nose"] = any(body_b[0] <= _cx(_box(e)) <= body_b[2] and _box(e)[1] < body_b[1] and _box(e)[3] <= body_b[1] + 40 for e in reds)
    res["stripes"] = sum(1 for e in reds if _box(e)[0] >= body_b[0] - 30 and _box(e)[2] <= body_b[2] + 30
                         and _box(e)[1] >= body_b[1] and _box(e)[3] <= body_b[3] and (_box(e)[3] - _box(e)[1]) < bh * 0.4) >= 2

    ells = [e for e in els if e["type"] == "ellipse" and _filled(e) or e["type"] == "ellipse"]
    inside = [e for e in ells if _box(e)[0] >= body_b[0] and _box(e)[2] <= body_b[2] and _box(e)[1] >= body_b[1] and _box(e)[3] <= body_b[3]]
    for a in inside:
        group = [b for b in inside if abs(_cx(_box(a)) - _cx(_box(b))) <= 20 and abs(_cy(_box(a)) - _cy(_box(b))) <= 20]
        if len(group) >= 2 and any(_fill(b) == "blue" or color_class(b.get("strokeColor")) == "blue" for b in group):
            res["porthole"] = True
            break

    left = [e for e in reds if _cx(_box(e)) < body_b[0] + bw * 0.2 and body_b[1] + bh * 0.4 <= _cy(_box(e)) <= body_b[3] + bh * 0.3]
    right = [e for e in reds if _cx(_box(e)) > body_b[2] - bw * 0.2 and body_b[1] + bh * 0.4 <= _cy(_box(e)) <= body_b[3] + bh * 0.3]
    res["fins"] = bool(left) and bool(right)

    below = [e for e in els if _filled(e) and _box(e)[1] >= body_b[3] - 20 and _box(e)[2] >= body_b[0] and _box(e)[0] <= body_b[2] and e not in skies]
    res["engine"] = sum(1 for e in below if greyish(e.get("backgroundColor"))) >= 3
    res["flames"] = any(_fill(e) == "orange" for e in below) and any(_fill(e) == "yellow" for e in below)

    rocket_zone = (body_b[0] - 30, body_b[1] - 80, body_b[2] + 30, body_b[3] + 160)
    stars = [e for e in els if _filled(e) and _fill(e) == "yellow" and in_sky(_box(e))
             and not (_box(e)[0] < rocket_zone[2] and _box(e)[2] > rocket_zone[0] and _box(e)[1] < rocket_zone[3] and _box(e)[3] > rocket_zone[1])]
    res["stars"] = len(stars) >= 5
    return _result(res, els, detail)


def _result(res, els, detail):
    filled = [e for e in els if _filled(e)]
    solid = [e for e in filled if e.get("fillStyle") == "solid"]
    return {"components": res, "score": sum(res.values()), "of": len(COMPONENTS), "complete": all(res.values()),
            "rubric_version": RUBRIC_VERSION, "elements": len(els), "filled": len(filled), "solid_ratio": round(len(solid) / len(filled), 2) if filled else 0.0, **detail}
