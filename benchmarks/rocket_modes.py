"""
Detailed Excalidraw rocket, measured the same way for every approach.

    python benchmarks/rocket_modes.py --label typed_300 --trials 3 --env COMEX_PROGRAMS=0
    python benchmarks/rocket_modes.py --label typed_900 --trials 3 --env COMEX_PROGRAMS=0 --lease 900
    python benchmarks/rocket_modes.py --label original --trials 3 --backend-dir <copy of the Original>
    python benchmarks/rocket_modes.py --label hybrid --trials 3

Each trial: a fresh, empty Excalidraw canvas in its own headless Chrome, the same prompt, the agent run through the real
/agent/run/stream, then the drawing is read from Excalidraw's own saved scene and scored by benchmarks/rocket_rubric.py
(nine components). A final screenshot of the page is saved so the drawing can be looked at. What the agent says is stored
but never scored. Isolation: own Chrome profile, own backend on port 8091 with a throwaway graph database.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import hybrid_scenarios as H  # noqa: E402
import rocket_rubric  # noqa: E402
from nervous.cdp_session import WebSocketCDPClient  # noqa: E402
from tests.browser_lab import BrowserLab  # noqa: E402

PROMPT = ("This tab has a whiteboard drawing app (Excalidraw). Draw a colourful, detailed rocket on the canvas, using the colour and fill "
          "controls so every important shape has a solid fill. First draw one large dark navy rectangle, solid fill, covering most of the "
          "canvas as the night sky. On top of it draw: a red pointed nose cone; a white rounded rocket body; two red stripes across the body; "
          "a round porthole window with a dark blue rim and light blue glass; two red fins, one on each side, as filled triangles; a dark grey "
          "engine base with two grey nozzles; flames below the nozzles with an orange outer flame and a smaller yellow inner flame; and about "
          "six small yellow stars in the sky around the rocket. Take a screenshot to check the result, and fix anything that is missing, "
          "unfilled or in the wrong place. When you are done, tell me what you drew and anything you could not do.")


async def read_scene_and_shot(page, out_png: Path):
    cdp = WebSocketCDPClient(page.ws_url)
    await cdp.connect()
    try:
        await asyncio.sleep(2.5)  # Excalidraw saves a moment after the last change
        r = await cdp.send("Runtime.evaluate", {"expression": "localStorage.getItem('excalidraw')", "returnByValue": True})
        raw = r["result"].get("value")
        shot = await cdp.send("Page.captureScreenshot", {"format": "png"})
        out_png.write_bytes(base64.b64decode(shot["data"]))
    finally:
        await cdp.close()
    return json.loads(raw) if raw else []


def timeline(events):
    out = []
    for t, e, d in events:
        if e in ("step", "step_done"):
            out.append({"t": round(t, 1), "e": e, "tool": d.get("tool"), "label": d.get("label"), "ok": d.get("success")})
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--backend-dir", default=str(ROOT))
    ap.add_argument("--timeout", type=float, default=700, help="harness limit per trial, seconds")
    ap.add_argument("--lease", type=float, default=None, help="COMEX_LEASE_TTL_S for the backend")
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE for the backend (repeatable)")
    ap.add_argument("--visible", action="store_true")
    a = ap.parse_args()
    out = ROOT / "benchmarks/rocket" / a.label
    out.mkdir(parents=True, exist_ok=True)
    for kv in a.env:
        k, v = kv.split("=", 1)
        os.environ[k] = v
    if a.lease:
        os.environ["COMEX_LEASE_TTL_S"] = str(a.lease)
    if a.visible:
        os.environ["COMEX_LAB_VISIBLE"] = "1"
    lease_s = float(os.environ.get("COMEX_LEASE_TTL_S", "300"))
    lab = BrowserLab.start()
    db = tempfile.mkdtemp(prefix="comex-rocket-db-")
    proc = H.start_backend(Path(a.backend_dir).resolve(), lab.cdp_http, db, out / "backend.log")
    rows = []
    try:
        async with httpx.AsyncClient() as client:
            for i in range(a.trials):
                page = H._open(lab, "https://excalidraw.com/")
                await H._reset_excalidraw(page)
                lab.only(page)
                events, wall, final, err = await H.run_agent(client, PROMPT, a.timeout)
                answer = (final or {}).get("content") or (final or {}).get("text") or ""
                elements = await read_scene_and_shot(page, out / f"trial_{i + 1:02d}.png")
                sc = rocket_rubric.score(elements)
                summ = H.summarise(events, wall, final)
                stats = (final or {}).get("stats") or {}
                llm_ms, tool_ms = stats.get("llm_ms"), stats.get("tool_ms")
                row = {"label": a.label, "trial": i + 1, "error": err, "wall_s": round(wall, 1), "lease_s": lease_s,
                       "lease_likely_expired": bool(wall >= lease_s - 20 or any(w in answer.lower() for w in ("time limit", "deadline", "lease", "timed out", "time expired"))),
                       "score": sc["score"], "complete": sc["complete"], "components": sc["components"], "elements": sc["elements"],
                       "solid_ratio": sc["solid_ratio"], "tool_calls": summ["tool_calls"], "llm_calls": summ["llm_calls_measured"] or summ["llm_calls_derived"],
                       "llm_s": round(llm_ms / 1000, 1) if llm_ms else None, "tool_s": round(tool_ms / 1000, 1) if tool_ms else None,
                       "other_s": round(wall - (llm_ms or 0) / 1000 - (tool_ms or 0) / 1000, 1) if llm_ms else None,
                       "failed_tool_calls": summ["failed_tool_calls"], "tools_used": {t: summ["tools"].count(t) for t in sorted(set(summ["tools"]))}}
                rows.append(row)
                (out / f"trial_{i + 1:02d}.json").write_text(json.dumps({**row, "answer": answer, "trace": stats.get("trace"), "timeline": timeline(events),
                                                                         "scene": elements}, indent=2))
                print(f"{a.label} trial {i + 1}/{a.trials}: score {sc['score']}/9{' COMPLETE' if sc['complete'] else ''}  {wall:6.1f}s  "
                      f"tools={row['tool_calls']} llm={row['llm_calls']}  lease_expired~{row['lease_likely_expired']}  parts={[k for k, v in sc['components'].items() if not v]} missing",
                      flush=True)
                lab.close_page(page)
        walls = [r["wall_s"] for r in rows]
        summary = {"label": a.label, "trials": len(rows), "complete": sum(r["complete"] for r in rows),
                   "score_median": statistics.median(r["score"] for r in rows), "scores": [r["score"] for r in rows],
                   "wall_median_s": statistics.median(walls), "walls": walls,
                   "tool_calls_median": statistics.median(r["tool_calls"] for r in rows), "llm_calls_median": statistics.median(r["llm_calls"] for r in rows),
                   "lease_expired_in": sum(r["lease_likely_expired"] for r in rows)}
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
    finally:
        proc.terminate()
        lab.stop()
        shutil.rmtree(db, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
