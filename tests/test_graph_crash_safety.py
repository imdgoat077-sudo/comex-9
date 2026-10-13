"""
The graph database survives a killed backend. Kuzu 0.11 replays a leftover write-ahead log after an unclean exit in a
way that breaks rows covered by full-text indexes: the next update of such a row crashed the process (SIGBUS). Found
live, reproduced for skills, lessons and user facts. The store now rebuilds the full-text indexes when it opens a
database that a killed process left behind, and closes cleanly on shutdown.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = textwrap.dedent("""
    import os, sys
    sys.path.insert(0, {root!r})
    from graph.store import AgentGraphStore
    path, step, table = sys.argv[1], sys.argv[2], sys.argv[3]
    s = AgentGraphStore(path)
    if table == "skill":
        s.save_program_skill("times table", "example.com", "d " + step, "def f():\\n    pass\\n", "{{}}", "t", "prog-" + step)
    elif table == "lesson":
        s.save_lesson("example.com", "a popup covers the results", "close it " + step)
    else:
        s.set_user_memory("home_city", "city " + step)
    print(step, "ok", flush=True)
    if step == "first":
        os._exit(0)  # like a killed backend: no clean close
""")


@pytest.mark.parametrize("table", ["skill", "lesson", "usermem"])
def test_a_killed_backend_leaves_a_database_that_still_takes_updates(tmp_path, table):
    script = tmp_path / "write.py"
    script.write_text(SCRIPT.format(root=str(ROOT)))
    db = str(tmp_path / "g.db")
    for step in ("first", "second", "third"):
        r = subprocess.run([sys.executable, str(script), db, step, table], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, f"{table} {step}: exit {r.returncode} {r.stderr[-300:]}"
        assert f"{step} ok" in r.stdout


@pytest.mark.parametrize("table", ["skill", "lesson", "usermem"])
def test_a_database_left_by_an_older_unsafe_run_is_repaired_on_open(tmp_path, table):
    """A database written without per-write checkpoints and then killed (as older versions did) is repaired when the
    store opens it: the full-text indexes are rebuilt, so updates no longer crash, and search still works."""
    import os
    script = tmp_path / "write.py"
    script.write_text(SCRIPT.format(root=str(ROOT)))
    db = str(tmp_path / "g.db")
    old = {**os.environ, "COMEX_GRAPH_CHECKPOINT_THRESHOLD": "-1"}  # the old behaviour, which leaves a log to replay
    r = subprocess.run([sys.executable, str(script), db, "first", table], capture_output=True, text=True, timeout=120, env=old)
    assert r.returncode == 0 and os.path.getsize(db + ".wal") > 0
    for step in ("second", "third"):
        r = subprocess.run([sys.executable, str(script), db, step, table], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, f"{table} {step}: exit {r.returncode} {r.stderr[-300:]}"
    from graph.store import AgentGraphStore
    s = AgentGraphStore(db)
    domain = {"skill": "SKILLS", "lesson": "LESSONS", "usermem": "USER"}[table]
    query = {"skill": "times table", "lesson": "popup", "usermem": "home city"}[table]
    assert s.search_memory(query, domain=domain), "the rebuilt index finds the row"
    s.close()


def test_the_store_closes_cleanly_twice(tmp_path):
    from graph.store import AgentGraphStore
    s = AgentGraphStore(str(tmp_path / "g.db"))
    s.close()
    s.close()
