"""
Independent result checks for browser programs.

A program's own output is its claim. These checks are evidence: they run AFTER the program has exited, in the backend,
through ComexToolService's read paths (read-only evaluation, wait conditions, or a read of a Google Sheet's saved data),
so the program cannot mark its own work. A program skill is credited only when such a check passes.

Check specs (JSON objects the agent passes with the program):
    {"type": "sheet_values", "expected": [["a", "b"], ...], "start_row": 1, "start_col": 1}
        Google Sheets: the saved cells starting at (start_row, start_col), 1-based, must equal `expected` (trimmed).
    {"type": "js_equals", "expression": "...", "expected": <any JSON>}   read-only page expression equals a value
    {"type": "js_true", "expression": "..."}                               read-only page expression is truthy
    {"type": "text", "expected": "Checkmate"}                              the page shows this text
    {"type": "url_contains", "expected": "/done"}
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Tuple

CHECK_TYPES = ("sheet_values", "js_equals", "js_true", "text", "url_contains")
MAX_EXPECTED_CELLS = 5000

# Google's CSV view of the sheet open in this tab (same origin, your session): what is saved, not what is on screen
SHEETS_CSV_JS = """(async () => {
  const m = location.pathname.match(/\\/spreadsheets\\/d\\/([^/]+)/);
  if (!m) return {error: 'this tab is not a Google Sheets document'};
  const gid = new URLSearchParams(location.hash.slice(1)).get('gid') || '0';
  const r = await fetch('/spreadsheets/d/' + m[1] + '/gviz/tq?tqx=out:csv&headers=0&gid=' + gid, {credentials: 'include'});
  return {status: r.status, text: await r.text()};
})()"""


EXAMPLES = ('{"type": "sheet_values", "expected": [["3 x 1", "3"], ["3 x 2", "6"]], "start_row": 1, "start_col": 1} (Google Sheets); '
            '{"type": "js_equals", "expression": "document.title", "expected": "Done"}; '
            '{"type": "js_true", "expression": "document.querySelectorAll(\'.row\').length === 20"}; '
            '{"type": "text", "expected": "Checkmate"}; {"type": "url_contains", "expected": "/done"}')


def parse_check(check: Any) -> Any:
    """A check given as a JSON string is read as the object it spells."""
    if isinstance(check, str):
        try:
            return json.loads(check)
        except json.JSONDecodeError:
            return check
    return check


def validate_check(check: Any) -> str:
    """Empty string if the check spec is usable, else why not, with working examples (shown to the agent)."""
    if not isinstance(check, dict) or check.get("type") not in CHECK_TYPES:
        got = check.get("type") if isinstance(check, dict) else type(check).__name__
        return (f"check needs a \"type\" that is one of {', '.join(CHECK_TYPES)} (got {got!r}). Examples: {EXAMPLES}")
    t = check["type"]
    if t == "sheet_values":
        exp = check.get("expected")
        if not isinstance(exp, list) or not exp or not all(isinstance(r, list) for r in exp):
            return "sheet_values needs expected: a list of rows (lists of cell values)"
        if sum(len(r) for r in exp) > MAX_EXPECTED_CELLS:
            return f"sheet_values can check at most {MAX_EXPECTED_CELLS} cells"
    elif t in ("js_equals", "js_true") and not isinstance(check.get("expression"), str):
        return f"{t} needs expression: a read-only JavaScript expression"
    elif t in ("text", "url_contains") and not isinstance(check.get("expected"), str):
        return f"{t} needs expected: a string"
    return ""


def compare_region(rows: List[List[str]], expected: List[List[Any]], start_row: int = 1, start_col: int = 1) -> Tuple[bool, str]:
    """Do the cells at (start_row, start_col) equal expected? Values are compared as trimmed text."""
    r0, c0 = max(1, int(start_row)) - 1, max(1, int(start_col)) - 1
    for i, exp_row in enumerate(expected):
        row = rows[r0 + i] if r0 + i < len(rows) else []
        for j, exp in enumerate(exp_row):
            got = row[c0 + j].strip() if c0 + j < len(row) else ""
            want = str(exp).strip()
            if got != want:
                return False, f"cell row {r0 + i + 1}, column {c0 + j + 1}: expected {want!r}, found {got!r}"
    return True, f"{sum(len(r) for r in expected)} cells match"


async def run_check(svc: Any, ctx: Any, check: Dict[str, Any], *, sheet_tries: int = 6) -> Tuple[bool, str]:
    """(passed, detail). Never raises: a check that cannot run is a failed check, with the reason."""
    import asyncio
    why = validate_check(check)
    if why:
        return False, f"invalid check: {why}"
    t = check["type"]
    try:
        if t == "sheet_values":
            last = "the sheet had no data yet"
            for _ in range(max(1, sheet_tries)):  # Sheets saves a moment after typing
                res = await svc.page_script(ctx, SHEETS_CSV_JS, timeout_ms=15000)
                if not res.success:
                    return False, f"could not read the sheet: {res.error_message}"
                data = (res.data or {}).get("value") if isinstance(res.data, dict) else None
                if not isinstance(data, dict) or data.get("error"):
                    return False, (data or {}).get("error") or "could not read the sheet"
                if data.get("status") != 200:
                    return False, f"the sheet's data could not be read (HTTP {data.get('status')})"
                rows = list(csv.reader(io.StringIO(data.get("text") or "")))
                ok, detail = compare_region(rows, check["expected"], check.get("start_row", 1), check.get("start_col", 1))
                if ok:
                    return True, detail
                last = detail
                await asyncio.sleep(1.0)
            return False, last
        if t == "js_equals":
            res = await svc.evaluate(ctx, check["expression"])
            if not res.success:
                return False, f"could not evaluate: {res.error_message}"
            value = (res.data or {}).get("value")
            ok = json.dumps(value, sort_keys=True) == json.dumps(check.get("expected"), sort_keys=True)
            return ok, ("value matches" if ok else f"expected {json.dumps(check.get('expected'))[:200]}, found {json.dumps(value)[:200]}")
        condition = {"js_true": {"type": "js", "expression": check.get("expression")},
                     "text": {"type": "text", "expected": check.get("expected")},
                     "url_contains": {"type": "url_contains", "expected": check.get("expected")}}[t]
        res = await svc.wait_for(ctx, condition, int(check.get("timeout_ms", 4000)))
        if not res.success:
            return False, f"could not check: {res.error_message}"
        met = bool((res.data or {}).get("met"))
        return met, ("condition met" if met else f"condition not met ({(res.data or {}).get('detail', '')})")
    except Exception as e:  # a broken check never counts as a pass
        return False, f"the check failed to run: {type(e).__name__}: {e}"
