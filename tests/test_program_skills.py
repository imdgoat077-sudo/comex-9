"""
Program skills: a program becomes a skill only after an independent check of its result passed; reuse is credited only
by such checks; skills that keep failing are demoted and no longer offered. Checks run after the program, through the
service, so a program cannot mark its own work. Real headless Chrome for the browser parts.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from types import SimpleNamespace

import pytest

from graph.store import AgentGraphStore
from services.program_checks import compare_region, run_check, validate_check
from services.program_runtime import sandbox_status
from tests.browser_lab import find_chrome
from tests.test_program_runtime import Rig, lab  # noqa: F401


@pytest.fixture
def store():
    d = tempfile.mkdtemp()
    return AgentGraphStore(os.path.join(d, f"g{uuid.uuid4().hex}.db"))


# ── checks (no browser) ─────────────────────────────────────────────────────────────────────────────

def test_check_specs_are_validated():
    assert validate_check({"type": "sheet_values", "expected": [["a"]]}) == ""
    assert "one of" in validate_check({"type": "trust_me"})
    assert "expected" in validate_check({"type": "sheet_values", "expected": "a"})
    assert "expression" in validate_check({"type": "js_true"})


def test_sheet_region_comparison():
    rows = [["", "", ""], ["", "3 x 1", "3"], ["", "3 x 2", " 6 "]]
    assert compare_region(rows, [["3 x 1", "3"], ["3 x 2", 6]], start_row=2, start_col=2)[0]
    ok, why = compare_region(rows, [["3 x 1", "3"], ["3 x 2", "7"]], start_row=2, start_col=2)
    assert not ok and "row 3, column 3" in why and "'7'" in why
    assert not compare_region(rows, [["x"]] * 5, 1, 1)[0]  # missing rows are empty cells, not a pass


async def test_the_sheet_check_reads_the_saved_sheet_and_waits_for_it_to_save():
    csvs = iter(['"",""\n', '"3 x 1","3"\n"3 x 2","6"\n'])  # first read: not saved yet

    class Svc:
        async def page_script(self, ctx, expr, timeout_ms=15000):
            assert "gviz/tq?tqx=out:csv" in expr
            return SimpleNamespace(success=True, data={"value": {"status": 200, "text": next(csvs)}})

    ok, detail = await run_check(Svc(), None, {"type": "sheet_values", "expected": [["3 x 1", "3"], ["3 x 2", "6"]]}, sheet_tries=3)
    assert ok and "4 cells match" in detail


async def test_a_check_that_cannot_run_is_a_failure_never_a_pass():
    class Broken:
        async def page_script(self, *a, **k):
            raise RuntimeError("tab closed")
    ok, detail = await run_check(Broken(), None, {"type": "sheet_values", "expected": [["a"]]})
    assert not ok and "tab closed" in detail


# ── store: evidence and demotion ───────────────────────────────────────────────────────────────────

def test_program_skills_are_credited_only_by_checks_and_demoted_when_they_keep_failing(store):
    sid = store.save_program_skill("fill table", "docs.google.com", "types a table", "def fill(rows): type_table(rows)",
                                   json.dumps({"type": "sheet_values"}), "write 3s table", "prog-1", "agent-1")
    sk = store.find_skills_for_domain("docs.google.com")[0]
    assert (sk["kind"], sk["status"], sk["success_count"], sk["source_run_id"]) == ("program", "probation", 1, "prog-1")
    store.record_skill_use([sid], True)  # the generic "the run succeeded" loop must not credit a program skill
    assert store.find_skills_for_domain("docs.google.com")[0]["usage_count"] == 1
    store.record_program_skill_check([sid], True)
    assert store.find_skills_for_domain("docs.google.com")[0]["status"] == "active"
    for _ in range(4):
        store.record_program_skill_check([sid], False)
    assert store.find_skills_for_domain("docs.google.com") == []          # no longer offered
    assert store.get_program_skills(["fill table"], "docs.google.com") == []
    listed = store.list_skills()
    assert listed[0]["status"] == "demoted" and listed[0]["failure_count"] == 4  # still visible in Memory


# ── the tools in a real browser ────────────────────────────────────────────────────────────────────

needs_browser = pytest.mark.skipif(find_chrome() is None or not sandbox_status()[0],
                                   reason="needs Chrome/Chromium and the program sandbox")


@pytest.fixture
async def rig(lab):  # noqa: F811
    r = Rig(lab)
    yield r
    from nervous.cdp_session import _GLOBAL_SESSIONS
    for s in list(_GLOBAL_SESSIONS.values()):
        try:
            await s.stop()
            await s.cdp.close()
        except Exception:
            pass
    _GLOBAL_SESSIONS.clear()


def test_a_skill_keeps_only_definitions_so_loading_it_repeats_nothing():
    """Found live: a saved skill ended with its own call, so reusing it typed the old table again first."""
    from services.program_runtime import skill_definitions
    code = "import json\nLIMIT = 20\ndef times_table(n, upto):\n    type_table([[n, i] for i in range(upto)])\ntimes_table(7, 10)\nprint('done')\n"
    kept = skill_definitions(code)
    assert "def times_table" in kept and "LIMIT = 20" in kept and "import json" in kept
    assert "times_table(7, 10)" not in kept and "print(" not in kept
    with pytest.raises(ValueError, match="no function to reuse"):
        skill_definitions("type_table([['a']])")
    with pytest.raises(ValueError, match="does not parse"):
        skill_definitions("def broken(:\n")


def test_a_bad_check_is_explained_with_working_examples():
    """Found live: the model sent checks without a valid type four times; the error now shows what works."""
    from services.program_checks import parse_check
    why = validate_check(parse_check('{"type": "sheet", "expected": []}'))
    assert "'sheet'" in why and '"type": "js_equals"' in why and '"type": "sheet_values"' in why
    assert parse_check('{"type": "text", "expected": "ok"}') == {"type": "text", "expected": "ok"}
