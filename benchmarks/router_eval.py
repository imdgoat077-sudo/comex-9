"""
Held-out routing evaluation. Runs benchmarks/router_eval_set.py (68 labelled tasks, hash recorded) through four arms, ONCE:

    always_typed           what Comex does today (no program mode)
    deterministic_only     the router with Jev off (borderline tasks fall back to typed, flagged uncertain)
    production             the router as it ships: deterministic first, Jev only for borderline tasks
    jev_every_task         Jev's many_ops on every task (threshold 0.5) plus the table override: what 'just use the model' would do

Reported: execution accuracy (overall and per category), perception precision and recall for the two costly kinds (visual,
structured), uncertainty flagging on the ambiguous tasks, fallback frequency, decision latency, Jev call rate, and the expected
effect of each mistake using only what we measured (see MISTAKE_COST). Accuracy alone is not the point.

    python benchmarks/router_eval.py
"""

import asyncio
import hashlib
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
import router_eval_set  # noqa: E402
from services.execution_router import JevClient, JevError, RouteRequest, route, route_deterministic  # noqa: E402

# What a wrong route costs, from our own measurements. "measured" rows cite the runs; the rest are NOT measured.
MISTAKE_COST = {
    ("program", "typed", "measured_program_needed"): "measured: typed tools scored 1/9 on the rocket in both runs (306 s and 569 s); the Original's script agent scored 9/9",
    ("typed", "program", "measured_typed_better"): "measured: the script agent was slower on chess (41 s vs 29.5 s) and drawing (38 s vs 22 s), roughly +12 to +16 s",
    ("program", "typed", "hypothesis_program_helps"): "NOT measured: possible missed speedup on bulk DOM work",
    ("typed", "program", "typed_expected"): "NOT measured: possibly an unnecessary program on an ordinary task",
}


def _env_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("TYPESAFE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def file_hash(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def perception_scores(rows, kind):
    tp = sum(1 for r in rows if kind in r["want_perception"] and kind in r["perception"])
    fp = sum(1 for r in rows if kind not in r["want_perception"] and kind in r["perception"])
    fn = sum(1 for r in rows if kind in r["want_perception"] and kind not in r["perception"])
    return {"precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / (tp + fn), 3) if tp + fn else None, "false_requests": fp, "misses": fn}


def summarise(arm, rows):
    n = len(rows)
    right = [r for r in rows if r["execution"] == r["want"]]
    cats = defaultdict(lambda: [0, 0])
    for r in rows:
        cats[r["category"]][1] += 1
        cats[r["category"]][0] += r["execution"] == r["want"]
    amb = [r for r in rows if r["ambiguous"]]
    clear = [r for r in rows if not r["ambiguous"]]
    lat = sorted(r["latency_ms"] for r in rows)
    mistakes = Counter((r["want"], r["execution"], r["value"]) for r in rows if r["execution"] != r["want"])
    return {
        "arm": arm, "cases": n,
        "execution_accuracy": round(len(right) / n, 3),
        "accuracy_excluding_ambiguous": round(sum(r["execution"] == r["want"] for r in clear) / len(clear), 3),
        "per_category": {c: f"{a}/{b}" for c, (a, b) in sorted(cats.items())},
        "program_recall": round(sum(1 for r in rows if r["want"] == "program" and r["execution"] == "program") / sum(1 for r in rows if r["want"] == "program"), 3),
        "program_false_positives": sum(1 for r in rows if r["want"] != "program" and r["execution"] == "program"),
        "ambiguous_flagged_uncertain": f"{sum(r['uncertain'] for r in amb)}/{len(amb)}",
        "clear_tasks_wrongly_flagged_uncertain": f"{sum(r['uncertain'] for r in clear)}/{len(clear)}",
        "perception_visual": perception_scores(rows, "visual"),
        "perception_structured": perception_scores(rows, "structured"),
        "jev_called": sum(r["jev_called"] for r in rows),
        "fallbacks": dict(Counter(r["fallback"] for r in rows if r["fallback"])),
        "decision_latency_ms": {"median": round(statistics.median(lat), 2), "p90": lat[int(n * 0.9) - 1], "max": lat[-1], "total_ms": round(sum(lat), 1)},
        "mistakes": [{"want": w, "got": g, "value": v, "count": c, "effect": MISTAKE_COST.get((w, g, v), "ambiguous or no measured effect")} for (w, g, v), c in mistakes.items()],
    }


def row(case, execution, perception, source, conf, uncertain, fallback, jev_called, jev_p, latency_ms):
    return {"id": case["id"], "category": case["category"], "task": case["task"], "want": case["execution"], "want_perception": case["perception"],
            "ambiguous": case["ambiguous"], "value": case["value"], "execution": execution, "perception": perception, "source": source,
            "confidence": conf, "uncertain": uncertain, "fallback": fallback, "jev_called": jev_called, "jev_p": jev_p, "latency_ms": latency_ms}


async def main():
    key = _env_key()
    cases = router_eval_set.CASES
    result = {"set_sha256": router_eval_set.set_hash(), "router_sha256": file_hash(ROOT / "services/execution_router.py"),
              "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"), "jev_key_present": bool(key), "arms": {}, "rows": {}}
    arm_rows = {}

    arm_rows["always_typed"] = [row(c, "typed", ["semantic"], "static", 1.0, False, None, False, None, 0.0) for c in cases]

    rows = []
    for c in cases:
        d, _ = route_deterministic(RouteRequest(task=c["task"], page_path=c["page_path"]))
        rows.append(row(c, d.execution, d.perception, d.source, d.confidence, d.uncertain, "jev_not_enabled" if d.escalate == "program_if_typed_stalls" else None, False, None, d.latency_ms))
    arm_rows["deterministic_only"] = rows

    client = JevClient(api_key=key)
    rows = []
    for c in cases:
        d = await route(RouteRequest(task=c["task"], page_path=c["page_path"]), jev=client, use_jev=True)
        rows.append(row(c, d.execution, d.perception, d.source, d.confidence, d.uncertain, d.fallback, d.jev_called, d.jev_p, d.latency_ms))
    arm_rows["production"] = rows

    client2 = JevClient(api_key=key)
    rows = []
    for c in cases:
        t0 = time.perf_counter()
        det, _ = route_deterministic(RouteRequest(task=c["task"], page_path=c["page_path"]))
        p, fb = None, None
        try:
            p = await client2.many_ops(c["task"], c["page_path"])
        except JevError as e:
            fb = e.reason
        if det.source == "override_table":
            ex = "typed"
        elif p is None:
            ex = "typed"
        else:
            ex = "program" if p >= 0.5 else "typed"
        rows.append(row(c, ex, det.perception, "jev" if p is not None else "fallback", round(max(p, 1 - p), 2) if p is not None else 0.0,
                        False, fb, p is not None, round(p, 3) if p is not None else None, round((time.perf_counter() - t0) * 1000, 1)))
    arm_rows["jev_every_task"] = rows

    for arm, rows in arm_rows.items():
        result["arms"][arm] = summarise(arm, rows)
    result["rows"] = arm_rows
    out = ROOT / "benchmarks/router/eval_v1_results.json"
    out.write_text(json.dumps(result, indent=2))
    for arm, s in result["arms"].items():
        print(f"\n== {arm}")
        print(f"  accuracy {s['execution_accuracy']}  (excluding ambiguous {s['accuracy_excluding_ambiguous']})  program recall {s['program_recall']}  program false positives {s['program_false_positives']}")
        print(f"  per category {s['per_category']}")
        print(f"  ambiguous flagged {s['ambiguous_flagged_uncertain']}   clear wrongly flagged {s['clear_tasks_wrongly_flagged_uncertain']}")
        print(f"  visual {s['perception_visual']}   structured {s['perception_structured']}")
        print(f"  jev calls {s['jev_called']}  fallbacks {s['fallbacks']}  latency {s['decision_latency_ms']}")
        for m in s["mistakes"]:
            print(f"  mistake x{m['count']}: should be {m['want']}, got {m['got']} [{m['value']}]  {m['effect']}")


if __name__ == "__main__":
    asyncio.run(main())
