"""
Start or stop an isolated Comex stack for benchmarks: a second Electron instance (own debugging port, own profile,
window opened without taking focus) and its own backend with a throwaway graph database. The user's running app,
its tabs, its profile and its memory are never touched.

    python benchmarks/isolated_stack.py start --backend-dir . --log-dir benchmarks/hybrid/run1
    python benchmarks/research ... --backend http://127.0.0.1:8091 --cdp http://127.0.0.1:9333
    python benchmarks/isolated_stack.py stop

The dev server (vite on :5173) must already be running; the isolated Electron loads the same UI from it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(tempfile.gettempdir()) / "comex_isolated_stack.json"
CDP_PORT, BACKEND_PORT = 9333, 8091


def _get(url, timeout=1.0):
    return urllib.request.urlopen(url, timeout=timeout).read()


def start(backend_dir: Path, log_dir: Path, trace: bool = True, extra_env: dict | None = None) -> None:
    if STATE.exists():
        sys.exit(f"already started ({STATE}); run stop first")
    try:
        _get("http://localhost:5173/", 2)
    except Exception:
        sys.exit("the dev server is not running on :5173 (npm run dev)")
    log_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="comex-iso-")
    env = {**os.environ, "COMEX_CDP_PORT": str(CDP_PORT), "COMEX_USER_DATA": os.path.join(tmp, "profile"),
           "COMEX_BENCH_WINDOW": "1", "VISUAL_CURSOR_ENABLED": "false", "NODE_ENV": "development"}
    electron = subprocess.Popen([str(ROOT / "node_modules/.bin/electron"), "."], cwd=str(ROOT), env=env,
                                stdout=open(log_dir / "electron.log", "w"), stderr=subprocess.STDOUT)
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            targets = json.loads(_get(f"http://127.0.0.1:{CDP_PORT}/json/list"))
            if any(t.get("type") == "page" and t.get("url", "").startswith("http://localhost:5173") for t in targets):
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        electron.terminate()
        sys.exit("isolated Electron did not come up")
    benv = {**os.environ, "PORT": str(BACKEND_PORT), "CDP_URL": f"http://127.0.0.1:{CDP_PORT}",
            "GRAPH_DB_PATH": os.path.join(tmp, "graph.db"), "VISUAL_CURSOR_ENABLED": "false",
            **({"COMEX_TRACE_TOOLS": "1"} if trace else {}), **(extra_env or {})}
    backend = subprocess.Popen([str(ROOT / ".venv/bin/python"), "agent_service.py"], cwd=str(backend_dir), env=benv,
                               stdout=open(log_dir / "backend.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            _get(f"http://127.0.0.1:{BACKEND_PORT}/health")
            break
        except Exception:
            time.sleep(0.5)
    else:
        electron.terminate(); backend.terminate()
        sys.exit("isolated backend did not start")
    STATE.write_text(json.dumps({"electron": electron.pid, "backend": backend.pid, "tmp": tmp, "backend_dir": str(backend_dir)}))
    print(f"isolated stack up: backend http://127.0.0.1:{BACKEND_PORT}  cdp http://127.0.0.1:{CDP_PORT}  (code: {backend_dir})")


def stop() -> None:
    if not STATE.exists():
        print("nothing to stop")
        return
    st = json.loads(STATE.read_text())
    for name in ("backend", "electron"):
        try:
            os.killpg(os.getpgid(st[name]), signal.SIGTERM)
        except Exception:
            try:
                os.kill(st[name], signal.SIGTERM)
            except Exception:
                pass
    time.sleep(1)
    shutil.rmtree(st["tmp"], ignore_errors=True)
    STATE.unlink(missing_ok=True)
    print("isolated stack stopped")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["start", "stop"])
    ap.add_argument("--backend-dir", default=str(ROOT))
    ap.add_argument("--log-dir", default=str(ROOT / "benchmarks/hybrid/stack"))
    a = ap.parse_args()
    start(Path(a.backend_dir).resolve(), Path(a.log_dir)) if a.action == "start" else stop()
