"""
The browser-program sandbox (services/program_runtime.py) is enforced by macOS, not by convention. Each test runs a
REAL program under the real profile and tries to escape: read secrets, write elsewhere, start processes, open network
connections. The browser RPC socket must keep working. A stub service stands in for the browser.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services import program_runtime as R

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="the program sandbox is macOS Seatbelt")
REPO = Path(__file__).resolve().parent.parent


class StubService:
    """Answers page_script like the real service would; every other method is unused here."""
    def __init__(self):
        self.scripts = []

    def _precheck_context(self, ctx, op):
        return None

    async def page_script(self, ctx, expression, timeout_ms=15000):
        self.scripts.append(expression)
        return SimpleNamespace(success=True, data={"value": 6 * 7})


class Ctx:
    def is_cancelled(self):
        return False

    def time_remaining(self):
        return 60.0


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("COMEX_PROGRAM_WORKSPACE", str(tmp_path / "workspace"))
    return tmp_path


async def run(code, timeout=20):
    runner = R.ProgramRunner(StubService(), Ctx())
    res = await runner.run(code, timeout_s=timeout)
    return res, runner


def denied(res):
    return res.ok and "DENIED" in res.stdout and "ALLOWED" not in res.stdout


def test_the_sandbox_is_available_and_self_tested_here():
    ok, why = R.sandbox_status()
    assert ok, why


async def test_the_browser_channel_and_the_workspace_still_work():
    res, runner = await run("v = js('6 * 7')\nopen('out.txt', 'w').write('hello')\nprint(v, open('out.txt').read())")
    assert res.ok and res.stdout.strip() == "42 hello", res.to_text()
    assert (Path(runner.workspace) / "out.txt").read_text() == "hello"


async def test_cannot_read_the_env_file_or_other_home_directory_files():
    targets = [str(REPO / ".env"), str(REPO / "agent_service.py"), str(Path.home() / ".zshrc"), str(Path.home() / ".ssh")]
    code = "\n".join([
        "import os",
        f"for p in {targets!r}:",
        "    try:",
        "        open(p).read() if not os.path.isdir(p) else os.listdir(p)",
        "        print('ALLOWED', p)",
        "    except (PermissionError, FileNotFoundError, IsADirectoryError, OSError) as e:",
        "        print('DENIED', type(e).__name__)",
    ])
    res, _ = await run(code)
    assert denied(res), res.to_text()
    if (REPO / ".env").exists():  # the file is really there, so 'DENIED' is the sandbox, not a missing file
        assert "PermissionError" in res.stdout


async def test_cannot_list_or_stat_outside_the_workspace():
    code = "\n".join([
        "import os",
        f"for p in [{str(REPO)!r}, {str(Path.home())!r}, '/Users']:",
        "    try:",
        "        os.listdir(p); print('ALLOWED listing', p)",
        "    except OSError:",
        "        print('DENIED')",
    ])
    res, _ = await run(code)
    assert denied(res), res.to_text()


async def test_cannot_write_outside_the_workspace(tmp_path):
    outside = [str(tmp_path / "escape.txt"), str(REPO / "escape.txt"), "/private/tmp/comex-escape.txt", str(Path.home() / "escape.txt")]
    code = "\n".join([
        f"for p in {outside!r}:",
        "    try:",
        "        open(p, 'w').write('x'); print('ALLOWED', p)",
        "    except OSError:",
        "        print('DENIED')",
    ])
    res, _ = await run(code)
    assert denied(res), res.to_text()
    assert not any(Path(p).exists() for p in outside)


async def test_cannot_start_any_process():
    code = "\n".join([
        "import os, subprocess, sys",
        "attempts = [",
        "    lambda: subprocess.run(['/bin/echo', 'hi'], capture_output=True),",
        "    lambda: subprocess.run(['/bin/sh', '-c', 'echo hi'], capture_output=True),",
        "    lambda: subprocess.run([sys.executable, '-c', 'print(1)'], capture_output=True),",
        "    lambda: os.system('echo hi'),",
        "    lambda: os.posix_spawn('/bin/echo', ['echo', 'hi'], {}),",
        "    lambda: os.fork(),",
        "]",
        "for a in attempts:",
        "    try:",
        "        r = a()",
        "        if r == 0 and a is attempts[5]:",
        "            os._exit(0)",
        "        bad = (isinstance(r, int) and r == 0 and a is attempts[3]) or getattr(r, 'returncode', 1) == 0 or (isinstance(r, int) and r > 0 and a is attempts[5])",
        "        print('ALLOWED' if bad else 'DENIED', r)",
        "    except OSError as e:",
        "        print('DENIED', type(e).__name__)",
    ])
    res, _ = await run(code)
    assert denied(res) and res.stdout.count("DENIED") == 6, res.to_text()


async def test_cannot_open_network_connections():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    port = server.getsockname()[1]
    accepted = []
    def accept():
        try:
            accepted.append(server.accept())
        except OSError:
            pass  # the listener is closed at the end of the test
    threading.Thread(target=accept, daemon=True).start()
    code = "\n".join([
        "import socket",
        f"for target in [('127.0.0.1', {port}), ('1.1.1.1', 80)]:",
        "    try:",
        "        socket.create_connection(target, timeout=2); print('ALLOWED', target)",
        "    except OSError:",
        "        print('DENIED')",
        "try:",
        "    socket.getaddrinfo('example.com', 80); print('ALLOWED dns')",
        "except OSError:",
        "    print('DENIED')",
        "try:",
        "    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'x', ('127.0.0.1', 9)); print('ALLOWED udp')",
        "except OSError:",
        "    print('DENIED')",
    ])
    res, _ = await run(code)
    server.close()
    assert denied(res) and not accepted, res.to_text()


async def test_cannot_reach_another_unix_socket(tmp_path):
    other = os.path.realpath(tempfile.mkdtemp(prefix="cmxo-", dir="/tmp")) + "/o"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(other)
    srv.listen(1)
    code = f"import socket\ns = socket.socket(socket.AF_UNIX)\ntry:\n    s.connect({other!r}); print('ALLOWED')\nexcept OSError:\n    print('DENIED')"
    res, _ = await run(code)
    srv.close()
    assert denied(res), res.to_text()


async def test_without_a_working_sandbox_programs_do_not_run_at_all(monkeypatch):
    monkeypatch.setattr(R, "_SANDBOX_STATE", {})
    monkeypatch.setattr(R, "SANDBOX_EXEC", "/nonexistent/sandbox-exec")
    svc = StubService()
    res = await R.ProgramRunner(svc, Ctx()).run("js('1')\nprint('ran')")
    assert not res.ok and res.error_code == "SANDBOX_UNAVAILABLE" and "ran" not in res.stdout and svc.scripts == []
    monkeypatch.setattr(R, "_SANDBOX_STATE", {})  # let later tests probe the real sandbox again
