"""
One-time repair of the graph database after the Kuzu replay bug (see graph/store.py, _rebuild_fts_indexes).

A database that a killed backend left behind can have rows that crash the process when they are updated (SIGBUS in
NodeTable::update). The store repairs this by itself when it finds a leftover write-ahead log; this script does the same
on demand, for a database that was already damaged before that repair existed.

    .venv/bin/python scripts/repair_graph_fts.py [path]      (default: GRAPH_DB_PATH or ~/.comex/graph.db)

Stop the Comex backend first (the database can only be opened by one process). A copy of the database is made next to
it before anything changes; no data is deleted, only the full-text indexes are rebuilt.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    path = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else os.getenv("GRAPH_DB_PATH", "~/.comex/graph.db"))
    if not os.path.exists(path):
        print(f"No database at {path}")
        return 1
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for suffix in ("", ".wal"):
        if os.path.exists(path + suffix):
            shutil.copy2(path + suffix, f"{path}.backup-{stamp}{suffix}")
    print(f"Backup: {path}.backup-{stamp}")
    from graph.store import AgentGraphStore
    try:
        store = AgentGraphStore(path)
    except RuntimeError as e:
        print(f"Could not open the database (is the Comex backend still running?): {e}")
        return 2
    with store._lock:
        store._rebuild_fts_indexes("one-time repair (scripts/repair_graph_fts.py)")
    store.close()
    print("Full-text indexes rebuilt. Start the backend again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
