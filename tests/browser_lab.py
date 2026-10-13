"""
A throwaway real browser for tests: a static file server for tests/fixtures/browser plus a headless
Chrome with remote debugging on its own port and its own profile. It never touches the user's browser.

    lab = BrowserLab.start()          # returns None if no Chrome is installed (tests then skip)
    page = await lab.open("chess.html")
    ... lab.stop()
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "browser")
_CHROME_CANDIDATES = [
    os.getenv("CHROME_BIN", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]


def find_chrome() -> Optional[str]:
    for c in _CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_WORDS = json.load(open(os.path.join(FIXTURES, "words.json")))


def score_guess(secret: str, guess: str):
    res = ["absent"] * 5
    left = {}
    for i in range(5):
        if guess[i] == secret[i]:
            res[i] = "correct"
        else:
            left[secret[i]] = left.get(secret[i], 0) + 1
    for i in range(5):
        if res[i] != "correct" and left.get(guess[i], 0) > 0:
            res[i] = "present"
            left[guess[i]] -= 1
    return res


def secret_for(seed: int) -> str:
    return _WORDS[((seed % len(_WORDS)) + len(_WORDS)) % len(_WORDS)]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_a, **_k):  # keep test output clean
        pass

    def do_POST(self):  # the word game's scorer: the answer never reaches the page
        if self.path != "/api/score":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0)) or 0) or b"{}")
        guess = str(body.get("guess", "")).lower()
        valid = len(guess) == 5 and guess in _WORDS
        out = {"valid": valid}
        if valid:
            secret = secret_for(int(body.get("seed", 0)))
            out.update(result=score_guess(secret, guess), won=guess == secret)
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@dataclass
class Page:
    target_id: str
    ws_url: str
    url: str


class BrowserLab:
    def __init__(self, chrome: str, width: int = 1280, height: int = 800, scale: float = 1.0) -> None:
        self.chrome = chrome
        self.cdp_port = _free_port()
        self.http_port = _free_port()
        self._profile = tempfile.mkdtemp(prefix="comex-lab-")
        handler = functools.partial(_QuietHandler, directory=FIXTURES)
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.http_port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self._proc = subprocess.Popen(
            [chrome, *([] if os.getenv("COMEX_LAB_VISIBLE") == "1" else ["--headless=new"]), f"--remote-debugging-port={self.cdp_port}", f"--user-data-dir={self._profile}",
             f"--window-size={width},{height}", f"--force-device-scale-factor={scale}", "--no-first-run",
             "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.cdp_port}/json/version", timeout=1)
                return
            except Exception:
                time.sleep(0.2)
        self.stop()
        raise RuntimeError("headless Chrome did not start")

    @classmethod
    def start(cls, **kw) -> Optional["BrowserLab"]:
        chrome = find_chrome()
        return cls(chrome, **kw) if chrome else None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.http_port}"

    @property
    def cdp_http(self) -> str:
        return f"http://127.0.0.1:{self.cdp_port}"

    def open(self, name: str) -> Page:
        url = f"{self.base}/{name}"
        req = urllib.request.Request(f"{self.cdp_http}/json/new?{url}", method="PUT")
        info = json.load(urllib.request.urlopen(req, timeout=10))
        return Page(info["id"], info["webSocketDebuggerUrl"], url)

    def pages(self):
        return [t for t in json.load(urllib.request.urlopen(f"{self.cdp_http}/json/list", timeout=5)) if t.get("type") == "page"]

    def only(self, page: Page) -> None:
        """Close every other page, so 'the active tab' is unambiguous for an agent that resolves it by listing."""
        for t in self.pages():
            if t["id"] != page.target_id:
                try:
                    urllib.request.urlopen(f"{self.cdp_http}/json/close/{t['id']}", timeout=5)
                except Exception:
                    pass

    def close_page(self, page: Page) -> None:
        try:
            urllib.request.urlopen(f"{self.cdp_http}/json/close/{page.target_id}", timeout=5)
        except Exception:
            pass

    def stop(self) -> None:
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._httpd.shutdown()
        shutil.rmtree(self._profile, ignore_errors=True)
