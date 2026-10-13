"""
Browser programs: Python the agent writes to do many browser operations in ONE tool call.

How it works
    The program runs in its own Python process (services/program_child.py is its runtime). That process has NO direct
    browser connection. Each helper it calls (js, click_at_xy, drag, press_key, goto_url, ...) is sent over a local Unix
    socket to this module, which performs it through ComexToolService on the same ToolExecutionContext that started the
    program. So every browser operation is authorized, tab-locked, deadline-bound, cancellable and checked against the
    lease on its own: a context that does not permit "pointer" cannot click from inside a program either.

Permissions and consequences (stated plainly)
    BROWSER   Reaches only the tab the agent is authorized for, only through the operations its context permits
              (page_script, pointer, press_keys, scroll, navigate, wait_for, screenshot, select_option, cdp on an allow-list).
              No Target/Browser/Storage/Network CDP, no other tabs, no Comex UI, no browser-internal pages.
    MACHINE   Enforced by the operating system (macOS Seatbelt, `sandbox-exec`, deny-by-default profile below), not by
              filtering: the program can read the Python runtime and system libraries and its own two files; it can read
              and write only its own workspace folder (one per run, under COMEX_PROGRAM_WORKSPACE); it cannot start any
              process (no shell, no fork, no exec); its only connection is the browser RPC socket (no TCP/UDP, no DNS).
              Python runs isolated (-I -S): standard library only. If the sandbox is not available or fails its
              self-test, programs do not run at all (fail closed). Turn the whole feature off with COMEX_PROGRAMS=0.
    LIMITS    Wall-clock timeout (default 120 s, at most 600 s, and never beyond the task's own deadline), at most
              MAX_CALLS browser operations, output capped, stopped immediately when the task is cancelled.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("comex.services.program_runtime")

CHILD_PATH = str(Path(__file__).with_name("program_child.py"))
MAX_CODE_CHARS = 60_000
MAX_CALLS = 3000
MAX_TIMEOUT_S = 600.0
DEFAULT_TIMEOUT_S = 120.0
MAX_OUTPUT_CHARS = 8000
_ENV_ALLOW = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TZ", "SHELL")


SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def programs_enabled() -> bool:
    return os.getenv("COMEX_PROGRAMS", "1") != "0"


def workspace_dir() -> Path:
    p = Path(os.getenv("COMEX_PROGRAM_WORKSPACE") or "~/Comex-Workspace").expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _python() -> Tuple[str, str]:
    """The real interpreter and its installation prefix (a virtualenv's python is a symlink to these)."""
    return (os.path.realpath(getattr(sys, "_base_executable", None) or sys.executable), os.path.realpath(sys.base_prefix))


def _q(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sandbox_profile(run_dir: str, workspace: str, socket_path: str) -> str:
    """
    The Seatbelt profile one program runs under. Deny by default; every rule below is a deliberate exception. Paths are
    real paths (Seatbelt matches resolved paths: /tmp is /private/tmp).
    """
    exe, prefix = _python()
    runtime = [prefix, "/System", "/usr/lib", "/private/var/db/dyld", "/private/var/db/timezone", "/usr/share/zoneinfo"]
    devices = ["/dev/null", "/dev/urandom", "/dev/random", "/private/etc/localtime"]
    return "\n".join([
        "(version 1)",
        "(deny default)",
        ";; the interpreter, started once by sandbox-exec; no other program can be executed and no process created",
        f"(allow process-exec (literal {_q(exe)}))",
        ";; read-only: what Python needs to start (the root entry itself, runtime, system libraries) and its own files",
        "(allow file-read* (literal \"/\") " + " ".join(f"(literal {_q(d)})" for d in devices) + " "
        + " ".join(f"(subpath {_q(p)})" for p in runtime) + f" (subpath {_q(run_dir)}))",
        ";; the only place a program can write",
        f"(allow file-read* file-write* (subpath {_q(workspace)}))",
        "(allow file-write-data (literal \"/dev/null\"))",
        "(allow sysctl-read)",
        ";; the only connection: the browser RPC socket to the Comex backend",
        f"(allow network-outbound (remote unix-socket (path-literal {_q(socket_path)})))",
        "(allow signal (target self))",
    ])


_SANDBOX_STATE: Dict[str, Any] = {}


def sandbox_status() -> Tuple[bool, str]:
    """
    Whether programs can be isolated here, checked once by experiment: under the real profile Python must start, and it
    must NOT be able to read a file outside its workspace. Anything unexpected means programs stay disabled.
    """
    if "ok" in _SANDBOX_STATE:
        return _SANDBOX_STATE["ok"], _SANDBOX_STATE["reason"]
    ok, reason = False, ""
    if sys.platform != "darwin":
        reason = "browser programs need the macOS sandbox (sandbox-exec); this platform has no supported isolation yet"
    elif not os.path.exists(SANDBOX_EXEC):
        reason = f"{SANDBOX_EXEC} is missing, so programs cannot be isolated"
    else:
        import subprocess
        probe = os.path.realpath(tempfile.mkdtemp(prefix="cmxs-", dir="/tmp"))
        try:
            # the secret sits next to (not inside) the run folder and the workspace, as .env sits next to a workspace
            run_dir, ws, secret = os.path.join(probe, "run"), os.path.join(probe, "ws"), os.path.join(probe, "secret.txt")
            os.mkdir(run_dir)
            os.mkdir(ws)
            Path(secret).write_text("must not be readable")
            code = ("import os\nprint('started')\n"
                    f"try:\n    open({secret!r}).read(); print('LEAK')\nexcept PermissionError:\n    print('denied')\n")
            exe, _ = _python()
            out = subprocess.run([SANDBOX_EXEC, "-p", sandbox_profile(run_dir, ws, os.path.join(run_dir, "s")), exe, "-I", "-S", "-c", code],
                                 capture_output=True, text=True, timeout=20, cwd=ws, env={"PATH": "/usr/bin:/bin", "HOME": ws})
            ok = out.returncode == 0 and out.stdout.split() == ["started", "denied"]
            reason = "" if ok else f"the sandbox self-test failed (exit {out.returncode}: {(out.stdout + out.stderr).strip()[:200]})"
        except Exception as e:
            reason = f"the sandbox self-test could not run: {e}"
        finally:
            shutil.rmtree(probe, ignore_errors=True)
    if not ok:
        logger.warning("Browser programs are disabled: %s", reason)
    _SANDBOX_STATE.update(ok=ok, reason=reason)
    return ok, reason


def skill_definitions(code: str) -> str:
    """
    The reusable part of a program, for saving it as a skill: functions, classes, imports and constants. Top-level
    actions (calls, loops) are dropped, so loading a skill into a later program defines things and does nothing else.
    Raises ValueError when there is nothing reusable (no function or class) or the code does not parse.
    """
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"the program does not parse: {e}") from None
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            keep.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(node, "value", None), ast.Constant):
            keep.append(node)
    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in keep):
        raise ValueError("there is no function to reuse: write the reusable part as a function (def ...) and call it")
    return "\n\n".join(ast.get_source_segment(code, n) for n in keep)


def run_workspace() -> str:
    """A fresh folder for one program run (its files stay there for the user); real path, for the sandbox."""
    p = workspace_dir() / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{os.urandom(3).hex()}"
    p.mkdir(parents=True, exist_ok=True)
    return os.path.realpath(p)


def child_env(socket_path: str) -> Dict[str, str]:
    """A minimal environment: allow-listed names only, so no API key or token is passed by environment variable."""
    env = {k: os.environ[k] for k in _ENV_ALLOW if k in os.environ}
    env.update({"COMEX_PROGRAM_SOCKET": socket_path, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
    return env


@dataclass
class ProgramResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    timed_out: bool = False
    cancelled: bool = False
    wall_ms: int = 0
    rpc_calls: int = 0
    rpc_ms: int = 0
    ops: Dict[str, int] = field(default_factory=dict)
    failed_ops: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        head = (f"program {'finished' if self.ok else 'FAILED'} in {self.wall_ms / 1000:.1f}s; {self.rpc_calls} browser operations "
                f"({', '.join(f'{k} x{v}' for k, v in sorted(self.ops.items())) or 'none'}); "
                f"{self.rpc_ms / 1000:.1f}s of that was browser time")
        parts = [head]
        if self.timed_out:
            parts.append("It was stopped because it ran out of time. Anything it had already done to the page stays done.")
        if self.cancelled:
            parts.append("It was stopped because the task was cancelled.")
        if self.error:
            parts.append(f"Error: {self.error}")
        if self.stderr.strip():
            parts.append("stderr:\n" + self.stderr.strip())
        if self.failed_ops:
            parts.append("Browser operations that were refused or failed (the program may have handled them): " + "; ".join(self.failed_ops[:8]))
        parts.append("stdout:\n" + (self.stdout.strip() or "(nothing printed)"))
        return "\n".join(parts)


class ProgramOpError(Exception):
    pass


async def _read_capped(stream: asyncio.StreamReader, cap: int) -> str:
    buf = bytearray()
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            break
        if len(buf) < cap:
            buf.extend(chunk[: cap - len(buf)])
    text = buf.decode("utf-8", errors="replace")
    return text + ("\n[output cut]" if len(buf) >= cap else "")


class ProgramRunner:
    def __init__(self, service: Any, context: Any, *, max_calls: int = MAX_CALLS) -> None:
        self.service = service
        self.context = context
        self.max_calls = max_calls
        self.ops: Counter = Counter()
        self.rpc_ms = 0
        self.calls = 0
        self.failed: List[str] = []

    # ── one browser operation, through the service ───────────────────────────────────────────────
    @staticmethod
    def _unwrap(res: Any) -> Any:
        if res.success:
            return res.data
        raise ProgramOpError(res.error_message or str(res.error_code))

    async def _dispatch(self, op: str, a: Dict[str, Any]) -> Any:
        s, c = self.service, self.context
        if op == "js":
            return self._unwrap(await s.page_script(c, a["expression"], timeout_ms=int(a.get("timeout_ms", 15000))))
        if op == "read_js":
            return self._unwrap(await s.evaluate(c, a["expression"]))
        if op == "pointer":
            return self._unwrap(await s.pointer(c, a["action"], float(a["x"]), float(a["y"]),
                                                to_x=a.get("to_x"), to_y=a.get("to_y"), button=a.get("button", "left")))
        if op == "keys":
            return self._unwrap(await s.press_keys(c, keys=a.get("keys"), text=a.get("text")))
        if op == "scroll":
            return self._unwrap(await s.scroll(c, delta_y=float(a.get("delta_y") or 0), delta_x=float(a.get("delta_x") or 0),
                                               x=a.get("x"), y=a.get("y")))
        if op == "select":
            return self._unwrap(await s.select_option(c, a["selector"], a["value"]))
        if op == "navigate":
            return self._unwrap(await s.navigate(c, a["url"]))
        if op == "wait":
            return self._unwrap(await s.wait_for(c, a["condition"], timeout_ms=int(a.get("timeout_ms", 5000))))
        if op == "screenshot":
            return self._unwrap(await s.screenshot(c))
        if op == "cdp":
            return self._unwrap(await s.cdp(c, a["method"], a.get("params") or {}))
        raise ProgramOpError(f"unknown operation {op!r}")

    async def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    req = json.loads(line)
                    op, args, rid = req["op"], req.get("args") or {}, req.get("id")
                except Exception:
                    break
                t0 = time.monotonic()
                self.calls += 1
                self.ops[op] += 1
                try:
                    if self.calls > self.max_calls:
                        raise ProgramOpError(f"the program used its {self.max_calls} browser operations; stop and report what is done")
                    if self.context.is_cancelled():
                        raise ProgramOpError("the task was cancelled")
                    data = await self._dispatch(op, args)
                    reply = {"id": rid, "ok": True, "data": data}
                except ProgramOpError as e:
                    self.failed.append(f"{op}: {str(e)[:120]}")
                    reply = {"id": rid, "ok": False, "error": str(e)}
                except Exception as e:  # never let one bad call kill the connection silently
                    self.failed.append(f"{op}: {type(e).__name__}")
                    reply = {"id": rid, "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
                self.rpc_ms += int((time.monotonic() - t0) * 1000)
                try:
                    writer.write((json.dumps(reply, default=str) + "\n").encode())
                    await writer.drain()
                except (ConnectionError, BrokenPipeError):
                    break
        finally:
            try:
                writer.close()
            except Exception:
                pass

    # ── the whole program ─────────────────────────────────────────────────────────────────────────
    async def run(self, code: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ProgramResult:
        t0 = time.monotonic()
        pre = self.service._precheck_context(self.context, "program")
        if pre is not None:
            return ProgramResult(ok=False, error=pre.error_message, error_code=str(pre.error_code))
        if not isinstance(code, str) or not code.strip():
            return ProgramResult(ok=False, error="code must be a non-empty string.", error_code="VALIDATION_ERROR")
        if len(code) > MAX_CODE_CHARS:
            return ProgramResult(ok=False, error=f"the program is {len(code)} characters; the limit is {MAX_CODE_CHARS}.", error_code="VALIDATION_ERROR")
        sandboxed, why = sandbox_status()
        if not sandboxed:
            return ProgramResult(ok=False, error=f"Browser programs are not available: {why}.", error_code="SANDBOX_UNAVAILABLE")
        timeout_s = max(1.0, min(float(timeout_s), MAX_TIMEOUT_S, self.context.time_remaining() - 1.0))
        # short path: Unix socket paths are limited to about 100 characters; real path: the sandbox matches real paths
        tmp = os.path.realpath(tempfile.mkdtemp(prefix="cmxp-", dir="/tmp"))
        sock_path = os.path.join(tmp, "s")
        prog_path = os.path.join(tmp, "program.py")
        child_path = os.path.join(tmp, "program_child.py")
        Path(prog_path).write_text(code, encoding="utf-8")
        shutil.copyfile(CHILD_PATH, child_path)  # the program reads nothing from the repository (its .env lives there)
        self.workspace = run_workspace()
        server = await asyncio.start_unix_server(self._on_client, path=sock_path)
        proc = None
        reason = None
        try:
            exe, _ = _python()
            env = child_env(sock_path)
            env.update(HOME=self.workspace, TMPDIR=self.workspace)
            proc = await asyncio.create_subprocess_exec(
                SANDBOX_EXEC, "-p", sandbox_profile(tmp, self.workspace, sock_path), exe, "-I", "-S", child_path, prog_path,
                cwd=self.workspace, env=env,
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                start_new_session=True)
            out_t = asyncio.create_task(_read_capped(proc.stdout, MAX_OUTPUT_CHARS))
            err_t = asyncio.create_task(_read_capped(proc.stderr, MAX_OUTPUT_CHARS))
            deadline = t0 + timeout_s
            while proc.returncode is None:
                if self.context.is_cancelled():
                    reason = "cancelled"
                    break
                if time.monotonic() >= deadline:
                    reason = "timeout"
                    break
                try:
                    await asyncio.wait_for(proc.wait(), 0.2)
                except asyncio.TimeoutError:
                    pass
            if proc.returncode is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await proc.wait()
            stdout = await out_t
            stderr = await err_t
        finally:
            server.close()
            try:
                await server.wait_closed()
            except Exception:
                pass
            shutil.rmtree(tmp, ignore_errors=True)
        ok = proc is not None and proc.returncode == 0 and reason is None
        return ProgramResult(ok=ok, stdout=stdout, stderr=stderr, exit_code=proc.returncode if proc else None,
                             timed_out=reason == "timeout", cancelled=reason == "cancelled",
                             error=None if ok else (f"timed out after {timeout_s:.0f}s" if reason == "timeout" else
                                                    "cancelled" if reason == "cancelled" else f"exit code {proc.returncode if proc else '?'}"),
                             wall_ms=int((time.monotonic() - t0) * 1000), rpc_calls=self.calls, rpc_ms=self.rpc_ms,
                             ops=dict(self.ops), failed_ops=self.failed)
