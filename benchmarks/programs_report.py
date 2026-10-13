"""
Typed tools vs browser programs: build the comparison report from the per-trial results of

    python benchmarks/hybrid_scenarios.py --label programs_<mode> --mode <mode> --scenarios sheet,excalidraw,chess,wordle --trials 3

for mode in typed, hybrid, program. Every number comes from the saved trial files (benchmarks/hybrid/programs_<mode>/*.json);
success is the page's own state, never what the agent said.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODES = ("typed", "hybrid", "program")
SCENARIOS = ("sheet", "excalidraw", "chess", "wordle")


def trials(mode: str, scenario: str) -> list[dict]:
    d = ROOT / "hybrid" / f"programs_{mode}"
    return [json.loads(p.read_text()) for p in sorted(d.glob(f"{scenario}_*.json"))]


def med(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def fmt(v, unit="", digits=1):
    if v is None:
        return "–"
    return f"{v:.{digits}f}{unit}" if isinstance(v, float) else f"{v}{unit}"


def main() -> int:
    lines = ["# Typed tools vs browser programs", "",
             "Same tasks, same model, same isolated headless Chrome and backend per mode; success read from the page.",
             "Modes: **typed** = programs switched off; **hybrid** = the agent chooses; **program** = the prompt asks for one "
             "browser_program call. Medians over the trials; ranges in brackets.", "",
             "| Scenario | Mode | Success | Quality | Wall time | Model calls | Model time | Browser time | Failed calls | Recovered | Programs |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    failures = []
    for sc in SCENARIOS:
        for mode in MODES:
            rows = trials(mode, sc)
            if not rows:
                continue
            walls = [r["wall_s"] for r in rows]
            llm_ms = med([r.get("llm_ms") for r in rows])
            tool_ms = med([r.get("tool_ms") for r in rows])
            lines.append("| {} | {} | {}/{} | {} | {} ({}–{}) | {} | {} | {} | {} | {} | {} |".format(
                sc, mode, sum(r["success"] for r in rows), len(rows), fmt(med([r.get("quality") for r in rows]), "", 2),
                fmt(med(walls), " s"), fmt(min(walls), "", 0), fmt(max(walls), " s", 0),
                fmt(med([r.get("llm_calls_measured") or r.get("llm_calls_derived") for r in rows])),
                fmt(llm_ms / 1000 if llm_ms else None, " s"), fmt(tool_ms / 1000 if tool_ms else None, " s"),
                sum(r.get("failed_tool_calls") or 0 for r in rows), sum(bool(r.get("recovered")) for r in rows),
                sum(r.get("program_calls") or 0 for r in rows)))
            for r in rows:
                if not r["success"]:
                    failures.append(f"- {sc} / {mode} / trial {r['trial']}: {json.dumps(r.get('state'))}"
                                    f"{' — ' + r['error'] if r.get('error') else ''}")
    lines += ["", "## Failures", ""] + (failures or ["None."])
    lines += ["", "## Per trial", "", "| Scenario | Mode | Trial | Pass | Wall | Tools | Programs | Failed calls | Tools used |", "|---|---|---|---|---|---|---|---|---|"]
    for sc in SCENARIOS:
        for mode in MODES:
            for r in trials(mode, sc):
                used = ", ".join(sorted(set(r.get("tools") or [])))
                lines.append(f"| {sc} | {mode} | {r['trial']} | {'yes' if r['success'] else 'NO'} | {r['wall_s']} s | {r['tool_calls']} | "
                             f"{r.get('program_calls', 0)} | {r.get('failed_tool_calls') or 0} | {used} |")
    out = ROOT / "hybrid" / "programs_report.md"
    out.write_text("\n".join(lines) + "\n")
    print(out.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
