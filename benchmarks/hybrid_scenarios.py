"""
End-to-end browser scenarios with the real agent and the real model, judged from the page's own state.

    python benchmarks/hybrid_scenarios.py --label after --trials 5
    python benchmarks/hybrid_scenarios.py --label before --trials 5 --backend-dir "../Comex copy 19 - baseline-02edc0b"

Isolation: each run starts its own headless Chrome (fixtures from tests/fixtures/browser) and its own backend
on port 8091 with a throwaway graph database. It never touches the Comex app, its tabs or the real graph.

Success is read from the page after the agent finishes (the board is in checkmate, the game says "won", the scene
holds a circle inside a rectangle, the cart holds the right product, every table row is in the answer). What the
agent claims is recorded but never counts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nervous.cdp_session import WebSocketCDPClient  # noqa: E402
from tests.browser_lab import BrowserLab, Page  # noqa: E402

PORT = 8091
GRADES = json.loads((ROOT / "tests/fixtures/browser/grades.expected.json").read_text())

PROMPTS = {
    "chess": ("chess.html",
              "There is a chess game open in this tab. It is White's turn. Play the move that checkmates Black by making it on "
              "the board in the page. Then tell me the move you played and whether the game is over."),
    "wordle": ("wordle.html?seed={seed}",
               "There is a five-letter word guessing game open in this tab. Solve it: guess the hidden word using the game's own "
               "keyboard input, in at most 6 guesses. Tell me the word and how many guesses you used."),
    "draw": ("draw.html",
             "This tab has a drawing app. Draw a rectangle on the canvas, then draw a circle (an ellipse) completely inside that "
             "rectangle. Tell me when it is done."),
    "table": ("grades.html",
              "This tab shows a student's grade history. List every course with its code, title, credits and grade as a table, "
              "and give the total number of courses and the total credits. Do not skip any rows."),
    "excalidraw": ("https://excalidraw.com/",
                   "This tab has a whiteboard drawing app. Draw a rectangle on the canvas, then draw an ellipse completely inside "
                   "that rectangle. Tell me when it is done."),
    "shop": ("shop.html",
             "Search this shop for headphones, pick the cheapest one and add it to the cart. Tell me which one you added and its price."),
    "sheet": ("sheet.html",
              "This tab has a spreadsheet. Starting at its top-left cell, write the 3 times table from 1 to 20: for each N from 1 to 20 "
              "one row, with '3 x N' in the first column and the result in the second column (so the first row is '3 x 1' and '3'). "
              "Make sure every value really is in its cell, then tell me when it is done."),
}
SHEET_EXPECTED = [[f"3 x {n}", str(3 * n)] for n in range(1, 21)]

# How the agent may work: typed tools only (programs switched off), its own choice, or asked to write a program.
MODES = {
    "typed": ({"COMEX_PROGRAMS": "0"}, ""),
    "hybrid": ({}, ""),
    "program": ({}, " Do the work with one browser_program call (a Python program that drives the page) and read the result back."),
}


def _token() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("COMEX_INTERNAL_APP_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("COMEX_INTERNAL_APP_TOKEN not found in .env")


async def _page_js(page, expr):
    cdp = WebSocketCDPClient(page.ws_url)
    await cdp.connect()
    try:
        r = await cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r["result"].get("value")
    finally:
        await cdp.close()


# ── success checks: read the page, not the agent's words ───────────────────────────────────────

async def check_chess(page, answer, _seed):
    g = await _page_js(page, "({s: __game.status, h: __game.history, ill: __game.illegal})")
    return {"success": g["s"] == "checkmate" and g["h"] == ["Ra1-a8#"], "state": g}


async def check_wordle(page, answer, _seed):
    g = await _page_js(page, "({s: document.querySelector('#game').dataset.status, "
                             "rows: [...document.querySelectorAll('.row')].filter(r => r.children[0].dataset.state !== 'empty').length})")
    return {"success": g["s"] == "won", "state": g}


async def check_draw(page, answer, _seed):
    scene = await _page_js(page, "window.__scene.map(s => ({t: s.type, x1: s.x1, y1: s.y1, x2: s.x2, y2: s.y2}))") or []
    rect = next((s for s in scene if s["t"] == "rectangle"), None)
    ell = next((s for s in scene if s["t"] == "ellipse"), None)
    ok = False
    if rect and ell:
        rx1, rx2 = sorted((rect["x1"], rect["x2"])); ry1, ry2 = sorted((rect["y1"], rect["y2"]))
        ex1, ex2 = sorted((ell["x1"], ell["x2"])); ey1, ey2 = sorted((ell["y1"], ell["y2"]))
        ok = (rx2 - rx1 > 40 and ry2 - ry1 > 40 and ex2 - ex1 > 20 and ey2 - ey1 > 20
              and rx1 < ex1 and ex2 < rx2 and ry1 < ey1 and ey2 < ry2)
    return {"success": ok, "state": {"shapes": [s["t"] for s in scene]}}


async def check_table(page, answer, _seed):
    # synthetic fixture data, so verifying row by row is fine; real student data is never written to artifacts
    data = json.loads((ROOT / "tests/fixtures/browser/grades.data.json").read_text())
    lines = (answer or "").splitlines()
    good = 0
    for row in data:
        code = row[1]
        line = next((l for l in lines if code in l), "")
        if line and re.search(rf"(?<!\d){row[4]}(?!\d)", line) and re.search(rf"(?<![A-Za-z]){row[5]}(?![A-Za-z])", line):
            good += 1
    total_ok = re.search(r"(?<!\d)131(?!\d)", answer or "") is not None and re.search(r"(?<!\d)57(?!\d)", answer or "") is not None
    return {"success": good == len(data) and total_ok, "state": {"rows_correct": good, "rows_expected": len(data), "totals_stated": total_ok}}


async def check_shop(page, answer, _seed):
    cart = await _page_js(page, "window.__cart")
    return {"success": cart == ["tune"], "state": {"cart": cart}}


async def check_excalidraw(page, answer, _seed):
    # the app's own saved scene (it persists elements to localStorage a moment after each change)
    await asyncio.sleep(2.0)
    raw = await _page_js(page, "localStorage.getItem('excalidraw')")
    els = [e for e in (json.loads(raw) if raw else []) if not e.get("isDeleted")]
    box = lambda e: (min(e["x"], e["x"] + e["width"]), min(e["y"], e["y"] + e["height"]),
                     max(e["x"], e["x"] + e["width"]), max(e["y"], e["y"] + e["height"]))
    rects = [e for e in els if e["type"] == "rectangle" and abs(e["width"]) > 40 and abs(e["height"]) > 40]
    ells = [e for e in els if e["type"] == "ellipse" and abs(e["width"]) > 20 and abs(e["height"]) > 20]
    ok = any(box(r)[0] < box(e)[0] and box(e)[2] < box(r)[2] and box(r)[1] < box(e)[1] and box(e)[3] < box(r)[3]
             for r in rects for e in ells)
    return {"success": ok, "state": {"elements": [e["type"] for e in els]}}


async def check_sheet(page, answer, _seed):
    got = await _page_js(page, "sheetValues(20, 2)") or []
    correct = sum(1 for r, row in enumerate(SHEET_EXPECTED) for c, v in enumerate(row)
                  if r < len(got) and c < len(got[r]) and str(got[r][c]).strip() == v)
    return {"success": correct == 40, "quality": round(correct / 40, 3), "state": {"cells_correct": correct, "cells_expected": 40}}


CHECKS = {"sheet": check_sheet, "excalidraw": check_excalidraw, "chess": check_chess, "wordle": check_wordle, "draw": check_draw, "table": check_table, "shop": check_shop}


# ── backend and streaming ──────────────────────────────────────────────────────────────────────

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_backend(backend_dir: Path, cdp_http: str, db_dir: str, log_path: Path, extra_env: dict | None = None):
    env = {**os.environ, "COMEX_TRACE_TOOLS": "1", "PORT": str(PORT), "CDP_URL": cdp_http, "GRAPH_DB_PATH": os.path.join(db_dir, "graph.db"),
           "COMEX_CHAT_DB_PATH": os.path.join(db_dir, "chats.db"), "VISUAL_CURSOR_ENABLED": "false",
           "COMEX_PROGRAM_WORKSPACE": os.path.join(db_dir, "workspace"), **(extra_env or {})}
    py = ROOT / ".venv/bin/python"
    log = open(log_path, "w")
    proc = subprocess.Popen([str(py), "agent_service.py"], cwd=str(backend_dir), env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise RuntimeError(f"isolated backend did not start; see {log_path}")


async def run_agent(client, task, timeout_s):
    t0 = time.monotonic()
    events, ev, final = [], "message", None
    done_at = [None]
    body = {"task": task, "taskId": f"hyb-{int(t0)}", "tabId": "active_tab", "url": ""}
    try:
        async with client.stream("POST", f"http://127.0.0.1:{PORT}/agent/run/stream", json=body,
                                 headers={"x-comex-internal-token": _token()}, timeout=None) as resp:
            resp.raise_for_status()

            async def consume():
                nonlocal ev, final
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:"):
                        try:
                            d = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        events.append((round(time.monotonic() - t0, 2), ev, d))
                        if final is None and (ev in ("completed", "done") or d.get("done")):
                            final = d
                            done_at[0] = round(time.monotonic() - t0, 2)
            await asyncio.wait_for(consume(), timeout=timeout_s)
    except asyncio.TimeoutError:
        try:
            await client.post(f"http://127.0.0.1:{PORT}/agent/stop", json={"taskId": body["taskId"]},
                              headers={"x-comex-internal-token": _token()}, timeout=10)
        except Exception:
            pass
        return events, round(time.monotonic() - t0, 2), None, "timeout"
    # wall = until the answer was delivered; anything the backend does afterwards (memory, reflection) is not the user's wait
    return events, done_at[0] or round(time.monotonic() - t0, 2), final, None


def summarise(events, wall, final):
    steps = [d for _, e, d in events if e == "step"]
    tools = [d.get("tool") for d in steps]
    loop_steps = {d.get("step") for d in steps}
    stats = (final or {}).get("stats") or {}
    return {
        "wall_s": wall,
        "tool_calls": len(steps),
        "tools": tools,
        "llm_calls_derived": len(loop_steps) + 1,   # one per step that called tools, plus the final answer
        "llm_calls_measured": stats.get("llm_calls"),
        "failed_tool_calls": stats.get("failed_tool_calls"),
        "llm_ms": stats.get("llm_ms"), "tool_ms": stats.get("tool_ms"),
        "screenshots": tools.count("browser_screenshot"),
        "used_vision": "browser_screenshot" in tools,
        "used_input_tools": sorted({t for t in tools if t in ("browser_keys", "browser_pointer", "browser_scroll", "browser_select")}),
        "program_calls": tools.count("browser_program"),
    }


async def _reset_excalidraw(page):
    """Excalidraw keeps the last scene in localStorage, and one profile serves the whole series: start every trial from an empty canvas."""
    await asyncio.sleep(3.0)
    await _page_js(page, "(() => { localStorage.removeItem('excalidraw'); localStorage.removeItem('excalidraw-state'); location.reload(); return 1; })()")
    await asyncio.sleep(4.0)
    left = await _page_js(page, "localStorage.getItem('excalidraw')")
    if left not in (None, "", "[]"):
        raise RuntimeError(f"excalidraw canvas was not empty at the start of the trial: {str(left)[:80]}")


def _open(lab, rel):
    if not rel.startswith("http"):
        return lab.open(rel)
    req = urllib.request.Request(f"{lab.cdp_http}/json/new?{rel}", method="PUT")
    info = json.load(urllib.request.urlopen(req, timeout=10))
    return Page(info["id"], info["webSocketDebuggerUrl"], rel)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--scenarios", default="chess,wordle,draw,table,shop")
    ap.add_argument("--backend-dir", default=str(ROOT))
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--mode", choices=sorted(MODES), default="hybrid", help="typed tools only, the agent's choice, or a program")
    a = ap.parse_args()
    out = ROOT / "benchmarks/hybrid" / a.label
    out.mkdir(parents=True, exist_ok=True)
    lab = BrowserLab.start()
    if lab is None:
        sys.exit("no Chrome found")
    db_dir = tempfile.mkdtemp(prefix="comex-hybrid-db-")
    mode_env, mode_suffix = MODES[a.mode]
    proc = start_backend(Path(a.backend_dir).resolve(), lab.cdp_http, db_dir, out / "backend.log", mode_env)
    summary = {}
    try:
        async with httpx.AsyncClient() as client:
            for name in a.scenarios.split(","):
                rel, task = PROMPTS[name]
                runs = []
                for i in range(a.trials):
                    seed = i + 1
                    page = _open(lab, rel.format(seed=seed))
                    await asyncio.sleep(1.0)
                    if name == "excalidraw":
                        await _reset_excalidraw(page)
                    lab.only(page)
                    events, wall, final, err = await run_agent(client, task + mode_suffix, a.timeout)
                    answer = (final or {}).get("content") or (final or {}).get("text") or ""
                    verdict = await CHECKS[name](page, answer, seed)
                    row = {"scenario": name, "mode": a.mode, "trial": i + 1, "seed": seed, "error": err, **summarise(events, wall, final),
                           **verdict, "claimed_in_answer": answer[:400]}
                    row.setdefault("quality", 1.0 if row["success"] else 0.0)
                    # recovered: something failed along the way, and the task still ended right
                    row["recovered"] = bool(row["success"] and (row.get("failed_tool_calls") or 0) > 0)
                    runs.append(row)
                    (out / f"{name}_{i + 1:02d}.json").write_text(json.dumps({**row, "answer": answer, "trace": (final or {}).get("stats", {}).get("trace"), "steps": [
                        {"t": t, "tool": d.get("tool"), "label": d.get("label")} for t, e, d in events if e == "step"]}, indent=2))
                    print(f"{name:7} trial {i + 1}/{a.trials}: {'PASS' if row['success'] else 'FAIL'} {wall:6.1f}s  "
                          f"tools={row['tool_calls']:2}  llm~{row['llm_calls_derived']:2}  {row['state']}", flush=True)
                    lab.close_page(page)
                walls = [r["wall_s"] for r in runs]
                med = lambda key: statistics.median([r[key] for r in runs if r.get(key) is not None] or [0])
                summary[name] = {
                    "mode": a.mode, "trials": a.trials, "success": sum(r["success"] for r in runs),
                    "quality_median": med("quality"),
                    "wall_median_s": statistics.median(walls), "wall_min_s": min(walls), "wall_max_s": max(walls),
                    "tool_calls_median": med("tool_calls"),
                    "llm_calls_measured_median": med("llm_calls_measured"),
                    "llm_calls_derived_median": med("llm_calls_derived"),
                    "llm_ms_median": med("llm_ms"), "browser_tool_ms_median": med("tool_ms"),
                    "failed_tool_calls_total": sum(r.get("failed_tool_calls") or 0 for r in runs),
                    "recovered_runs": sum(r["recovered"] for r in runs),
                    "program_calls_total": sum(r["program_calls"] for r in runs),
                    "timeouts": sum(1 for r in runs if r["error"] == "timeout"),
                    "failures": [{"trial": r["trial"], "state": r["state"], "error": r["error"]} for r in runs if not r["success"]],
                    "vision_used_in": sum(r["used_vision"] for r in runs),
                }
                (out / "summary.json").write_text(json.dumps(summary, indent=2))
    finally:
        proc.terminate()
        lab.stop()
        shutil.rmtree(db_dir, ignore_errors=True)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
