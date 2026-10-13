"""
Phase 0: is TypeSafe's Jev (System One) usable as the Comex execution-mode router?

Measures, on 30 browser tasks whose correct mode was written down BEFORE running:
  - latency of one call (sequential, then a parallel burst)
  - accuracy of the `mode` choice and of the `many_ops` yes/no, and whether confidence tells right from wrong
The key is read from .env (TYPESAFE_API_KEY) and is never printed or saved.

    python benchmarks/router_probe.py
"""

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
URL = "https://api.typesafe.ai/v1/systemone"

QUESTIONS = {
    "mode": {
        "type": "choice",
        "instructions": "Which way of working fits this browser task best",
        "criteria": {
            "semantic": "ordinary reading, searching, extracting, clicking and filling a few fields on normal web pages",
            "visual": "a few actions on a canvas, game board or chart that must be looked at and clicked by coordinates",
            "program": "many repeated, computed or scripted operations done in one go: detailed drawings, bulk entry, loops over many items, geometry",
        },
    },
    "many_ops": {
        "type": "noul",
        "instructions": "The task needs more than about eight similar or computed browser operations (many shapes, many fields, many items)",
    },
}

# (task, page facts, correct mode). Written before the first call; the labels are mine.
TASKS = [
    ("Search for the best laptop under 50000 rupees and read the top result", "Page: Google search results", "semantic"),
    ("Add the cheapest headphones to the cart", "Page: online shop with a search box and product list", "semantic"),
    ("Who is the CEO of Stripe? Find it and cite the page", "Page: new tab", "semantic"),
    ("Fill the contact form with my name and email and submit it", "Page: form with 4 fields", "semantic"),
    ("Summarise the top three stories on Hacker News", "Page: news list", "semantic"),
    ("Open the first result and tell me the price", "Page: product search results", "semantic"),
    ("Read the grade history table and list every course with its grade", "Page: HTML table, 57 rows over 6 pages", "semantic"),
    ("Log into the dashboard and download last month's invoice", "Page: login form", "semantic"),
    ("Find three research papers on multi-agent orchestration with links", "Page: Google Scholar", "semantic"),
    ("Check whether this flight is still available and report the fare", "Page: airline search results", "semantic"),
    ("Play the move that checkmates Black on this chess board", "Page: chess board, 64 squares drawn in divs", "visual"),
    ("Draw a rectangle and put a circle inside it", "Page: Excalidraw whiteboard, empty canvas", "visual"),
    ("Click the red square that appears on the canvas", "Page: canvas game", "visual"),
    ("Guess the hidden five letter word in this game", "Page: word game, keyboard input only", "visual"),
    ("Drag the slider handle to 70 percent on this chart", "Page: chart widget drawn on a canvas", "visual"),
    ("Pick the highest bar in this chart and tell me its value", "Page: bar chart on canvas", "visual"),
    ("Draw a detailed colourful rocket with about 20 shapes: body, nose, fins, porthole, flames and stars", "Page: Excalidraw whiteboard, empty canvas", "program"),
    ("Enter all 40 rows from this list into the web form, one after another", "Page: data entry form with a repeat Add row button", "program"),
    ("Click through all 30 pages of results and collect every price into one list", "Page: paginated product list with Next button", "program"),
    ("Draw a pixel art picture using 100 coloured squares on this canvas", "Page: drawing canvas with a colour palette", "program"),
    ("Draw a 12 month calendar grid with labels on the whiteboard", "Page: Excalidraw whiteboard", "program"),
    ("Type these 25 product codes into the order form and press add after each", "Page: order form", "program"),
    ("Tick every checkbox in this settings list and then save", "Page: list of 60 checkboxes", "program"),
    ("Draw a bar chart of these 12 values with axes and labels on the canvas", "Page: whiteboard canvas", "program"),
    ("Rename 35 files in this web file manager following a pattern", "Page: web file manager, 35 items", "program"),
    ("Fill in the timetable grid with these 48 slots", "Page: timetable grid of 6 by 8 cells", "program"),
    ("Draw a detailed map of a small island with roads, a river and 15 buildings", "Page: Excalidraw whiteboard", "program"),
    ("Reorder these 20 cards by dragging each one to its target position", "Page: drag and drop board with 20 cards", "program"),
    ("Scroll the feed and open each of the first 30 posts to collect the author", "Page: social feed", "program"),
    ("Set the quantity of each of the 24 line items to the values in this list", "Page: invoice with 24 line items", "program"),
]


def _key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("TYPESAFE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("TYPESAFE_API_KEY not found in .env")


async def ask(client, key, task, page):
    t0 = time.monotonic()
    r = await client.post(URL, json={"state": f"Task: {task}\n{page}", "model": "jev-latest", "questions": QUESTIONS},
                          headers={"Authorization": f"Bearer {key}"}, timeout=30)
    ms = (time.monotonic() - t0) * 1000
    r.raise_for_status()
    return r.json(), ms


async def main():
    key = _key()
    out = ROOT / "benchmarks/router"
    out.mkdir(exist_ok=True)
    rows = []
    async with httpx.AsyncClient() as client:
        for task, page, want in TASKS:  # sequential: the realistic case, one decision at task start
            data, ms = await ask(client, key, task, page)
            a = data["answers"]
            rows.append({"task": task, "want": want, "got": a["mode"]["choice"], "mode_conf": a["mode"]["confidence"],
                         "mode_probs": a["mode"]["probabilities"], "many_ops": a["many_ops"]["noul"], "ms": round(ms), "model": data["model"],
                         "input_tokens": data["usage"]["input_tokens"]})
        t0 = time.monotonic()
        burst = await asyncio.gather(*[ask(client, key, t, p) for t, p, _ in TASKS[:10]])
        burst_wall = (time.monotonic() - t0) * 1000
    lat = sorted(r["ms"] for r in rows)
    ok = [r for r in rows if r["got"] == r["want"]]
    bad = [r for r in rows if r["got"] != r["want"]]
    prog_want = [r["want"] == "program" for r in rows]
    prog_by_mode = [r["got"] == "program" for r in rows]
    prog_by_noul = [r["many_ops"] > 0.5 for r in rows]
    acc = lambda pred: round(sum(p == w for p, w in zip(pred, prog_want)) / len(rows), 3)
    summary = {
        "model": rows[0]["model"], "tasks": len(rows),
        "latency_ms": {"min": lat[0], "median": statistics.median(lat), "p90": lat[int(len(lat) * 0.9) - 1], "max": lat[-1]},
        "parallel_burst_10": {"wall_ms": round(burst_wall), "each_ms": sorted(round(ms) for _, ms in burst)},
        "mode_accuracy": round(len(ok) / len(rows), 3),
        "program_vs_not_accuracy_from_mode": acc(prog_by_mode),
        "program_vs_not_accuracy_from_many_ops": acc(prog_by_noul),
        "mean_confidence_when_right": round(statistics.mean(r["mode_conf"] for r in ok), 3) if ok else None,
        "mean_confidence_when_wrong": round(statistics.mean(r["mode_conf"] for r in bad), 3) if bad else None,
        "wrong": [{"task": r["task"][:70], "want": r["want"], "got": r["got"], "conf": r["mode_conf"], "many_ops": r["many_ops"]} for r in bad],
    }
    (out / "typesafe_probe.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
