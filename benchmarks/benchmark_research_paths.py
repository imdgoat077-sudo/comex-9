"""
Single-agent vs multi-agent research benchmark (real endpoints, real browser, real model).

Runs the same research request through:
  - single agent: POST /agent/run/stream   (the chat's single-agent path, trusted internal token)
  - multi agent:  POST /agent/orchestrate/stream
in alternating order, and saves for every trial: raw final answer, event timeline, timing split,
tool/LLM call counts and link checks. Nothing is estimated: counts come from streamed events
(one `step` / `task_progress` event per tool call) and, when the backend reports them, its timing block.

Usage:
  .venv/bin/python benchmarks/benchmark_research_paths.py --phase before --trials 5
Results: benchmarks/research_paths/<phase>/  (one JSON per trial + summary.json)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parent.parent
MODES = ["single", "multi"]
BACKEND = "http://127.0.0.1:8000"   # --backend / --cdp point a run at an isolated stack instead
CDP = "http://127.0.0.1:9222"
REQUEST = "Find me the best research papers on multi agent orchestration."

PAPER_PATTERNS = {
    "arxiv": re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})"),
    "doi": re.compile(r"doi\.org/(10\.\d{4,9}/[^\s)\]]+)"),
    "semanticscholar": re.compile(r"semanticscholar\.org/paper/(?:[^/\s)]+/)?([0-9a-f]{40})"),
    "openreview": re.compile(r"openreview\.net/(?:forum|pdf)\?id=([A-Za-z0-9_-]+)"),
    "acl": re.compile(r"aclanthology\.org/([\w.-]+)"),
    "acm": re.compile(r"dl\.acm\.org/doi/(?:abs/|pdf/)?(10\.\d+/[^\s)\]]+)"),
}
LINK_RX = re.compile(r"\((https?://[^\s)]+)\)|(?<![(\[])(https?://[^\s)\]]+)")


def _internal_token() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("COMEX_INTERNAL_APP_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("COMEX_INTERNAL_APP_TOKEN not found in .env")


async def _stream(client: httpx.AsyncClient, url: str, body: dict, headers: dict) -> tuple[list, float]:
    """POST an SSE endpoint; return [(t_offset_s, event, data)] and total wall seconds."""
    t0 = time.monotonic()
    events, ev_type = [], "message"
    async with client.stream("POST", url, json=body, headers=headers, timeout=None) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                ev_type = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                events.append((round(time.monotonic() - t0, 2), ev_type, data))
    return events, round(time.monotonic() - t0, 2)


def _answer_time(events: list) -> float | None:
    """When the answer reached the user: first completed/done event (stream close can be later)."""
    return next((t for t, e, _ in events if e in ("completed", "done")), None)


def _quality(answer: str) -> dict:
    links = []
    for m in LINK_RX.finditer(answer or ""):
        url = (m.group(1) or m.group(2)).rstrip(".,;")
        if url not in links:
            links.append(url)
    papers = {}
    for kind, rx in PAPER_PATTERNS.items():
        for url in links:
            m = rx.search(url)
            if m:
                papers.setdefault(f"{kind}:{m.group(1).lower()}", url)
    paper_urls = set(papers.values())
    rows = [ln for ln in (answer or "").splitlines() if any(u in ln for u in paper_urls)]
    year_rx = re.compile(r"\b(19|20)\d{2}\b")
    with_year = sum(1 for ln in rows if year_rx.search(ln))
    return {"links": links, "paper_ids": sorted(papers), "paper_links": list(papers.values()),
            "rows_with_paper_link": len(rows), "rows_with_year": with_year}


async def _check_links(urls: list) -> dict:
    """HTTP status per paper link (GET, redirects followed). Reachability is a correctness proxy only."""
    async def one(c, u):
        try:
            r = await c.get(u, timeout=15, follow_redirects=True)
            return u, r.status_code
        except Exception as e:
            return u, f"error: {type(e).__name__}"
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Comex benchmark link check)"}) as c:
        return dict(await asyncio.gather(*(one(c, u) for u in urls)))


async def _close_finished_agent_tabs() -> int:
    """Close agent tabs left by previous trials through the tab bar (keeps trials comparable)."""
    targets = json.load(urllib.request.urlopen(f"{CDP}/json/list", timeout=3))
    ui = next((t for t in targets if t.get("type") == "page" and t.get("url", "").startswith("http://localhost:5173")), None)
    if not ui:
        return 0
    expr = ("(() => { const b = [...document.querySelectorAll('.browser-tab.agent-tab:not(.agent-working) .tab-close-btn')];"
            " b.forEach(x => x.click()); return b.length; })()")
    async with websockets.connect(ui["webSocketDebuggerUrl"], max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                return msg.get("result", {}).get("result", {}).get("value", 0)


def _summarise_single(events: list, wall: float) -> dict:
    done = next((d for _, e, d in reversed(events) if e in ("done", "completed")), {})
    meta = done.get("metadata") or {}
    timing = meta.get("timing") or {}
    steps = [d for _, e, d in events if e == "step"]
    return {
        "answer": done.get("result") or done.get("content") or "",
        "success": bool(done.get("success")),
        "wall_s": wall,
        "tool_calls": len(steps),
        "navigations": sum(1 for s in steps if s.get("tool") == "browser_navigate"),
        "llm_calls": len(timing.get("llm_roundtrips_ms") or []) or None,
        "avg_llm_ms": round(statistics.mean(timing["llm_roundtrips_ms"]), 0) if timing.get("llm_roundtrips_ms") else None,
        "step_labels": [s.get("label") for s in steps],
    }


def _summarise_multi(events: list, wall: float) -> dict:
    done = next((d for _, e, d in reversed(events) if e == "done"), {})
    t_run = next((t for t, e, _ in events if e == "run_started"), None)
    workers = {}
    for t, e, d in events:
        tid = d.get("task_id")
        if not tid:
            continue
        w = workers.setdefault(tid, {"description": d.get("description"), "tool_calls": 0, "navigate_labels": 0})
        if e == "task_started":
            w["start_s"] = t
        elif e == "task_progress":
            w["tool_calls"] += 1
            if str(d.get("label", "")).startswith("Opening "):
                w["navigate_labels"] += 1
        elif e in ("task_completed", "task_failed", "task_cancelled", "task_blocked"):
            w["end_s"], w["status"] = t, e[5:]
    for w in workers.values():
        if "start_s" in w and "end_s" in w:
            w["duration_s"] = round(w["end_s"] - w["start_s"], 2)
    last_worker_end = max((w.get("end_s", 0) for w in workers.values()), default=None)
    backend_timing = done.get("timing") or {}
    return {
        "answer": done.get("final_answer") or done.get("summary") or "",
        "success": bool(done.get("success")),
        "wall_s": wall,
        "planning_s": t_run,
        "after_workers_s": round(wall - last_worker_end, 2) if last_worker_end else None,
        "workers": workers,
        "slowest_worker_s": max((w.get("duration_s", 0) for w in workers.values()), default=None),
        "tool_calls": sum(w["tool_calls"] for w in workers.values()),
        "navigations": sum(w["navigate_labels"] for w in workers.values()),
        "backend_timing": backend_timing,
        "follow_up": done.get("follow_up"),
    }


async def run(phase: str, trials: int) -> None:
    out = ROOT / "benchmarks" / "research_paths" / phase
    out.mkdir(parents=True, exist_ok=True)
    token = _internal_token()
    order = []
    for i in range(trials):
        modes = [m for m in (["single", "multi"] if i % 2 == 0 else ["multi", "single"]) if m in MODES]
        order += modes
    async with httpx.AsyncClient() as client:
        for n, mode in enumerate(order, 1):
            closed = await _close_finished_agent_tabs()
            print(f"[{phase}] trial {n}/{len(order)} mode={mode} (closed {closed} old agent tabs)", flush=True)
            if mode == "single":
                body = {"task": REQUEST, "taskId": f"bench-{phase}-{n}", "tabId": "active_tab", "url": ""}
                events, wall = await _stream(client, f"{BACKEND}/agent/run/stream", body, {"x-comex-internal-token": token})
                rec = _summarise_single(events, wall)
            else:
                events, wall = await _stream(client, f"{BACKEND}/agent/orchestrate/stream", {"user_request": REQUEST}, {})
                rec = _summarise_multi(events, wall)
            rec["answer_s"] = _answer_time(events)
            q = _quality(rec["answer"])
            rec["quality"] = {**q, "paper_count": len(q["paper_ids"]), "link_status": await _check_links(q["paper_links"])}
            rec.update({"mode": mode, "trial": n, "phase": phase, "request": REQUEST,
                        "events": [{"t": t, "event": e, "data": d} for t, e, d in events]})
            (out / f"{n:02d}_{mode}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=str))
            (out / f"{n:02d}_{mode}_answer.md").write_text(rec["answer"])
            print(f"   wall={rec['wall_s']}s tool_calls={rec['tool_calls']} papers={rec['quality']['paper_count']} success={rec['success']}", flush=True)
            await asyncio.sleep(5)

    rows = [json.loads(p.read_text()) for p in sorted(out.glob("[0-9][0-9]_*.json"))]
    summary = {}
    for mode in ("single", "multi"):
        rs = [r for r in rows if r["mode"] == mode]
        if not rs:
            continue
        med = lambda k: statistics.median([r[k] for r in rs if r.get(k) is not None]) if any(r.get(k) is not None for r in rs) else None
        summary[mode] = {
            "trials": len(rs),
            "success": sum(r["success"] for r in rs),
            "wall_s_median": med("wall_s"),
            "wall_s_all": [r["wall_s"] for r in rs],
            "tool_calls_median": med("tool_calls"),
            "papers_median": statistics.median([r["quality"]["paper_count"] for r in rs]),
            "papers_all": [r["quality"]["paper_count"] for r in rs],
            "reachable_paper_links": sum(1 for r in rs for s in r["quality"]["link_status"].values() if s == 200),
            "checked_paper_links": sum(len(r["quality"]["link_status"]) for r in rs),
        }
        if mode == "multi":
            summary[mode].update({
                "planning_s_median": med("planning_s"),
                "slowest_worker_s_median": med("slowest_worker_s"),
                "after_workers_s_median": med("after_workers_s"),
            })
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, help="label for the output folder under benchmarks/research_paths/")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--backend", default=BACKEND)
    ap.add_argument("--cdp", default=CDP)
    ap.add_argument("--modes", default="single,multi")
    a = ap.parse_args()
    BACKEND, CDP = a.backend, a.cdp
    MODES = a.modes.split(",")
    asyncio.run(run(a.phase, a.trials))
