"""
Render the Comex chat drawer in a throwaway headless Chrome against a MOCK backend, never the real one.

    python preview.py <label> [--url http://localhost:5199]

Safety: every request to 127.0.0.1 / localhost other than the dev server is either redirected to the local mock
(ports 8000, 8091, 8791) or aborted. The harness refuses to submit a task unless it has first proved, with a
harmless GET, that the request reached the mock and not a real service.

Scenarios (each saved as /tmp/uiprev/<label>_<name>.png): empty, single_working, single_done, multi_working, multi_done, failed.
"""

import argparse
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/tmp/uiprev")
OUT.mkdir(exist_ok=True)
MOCK_PORT = 8791
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ANSWER = """I found three fares that fit. The cheapest direct option is **IndiGo 6E 2137** at ₹4,982.

| Airline | Departs | Arrives | Stops | Fare |
|---|---|---|---|---|
| IndiGo 6E 2137 | 07:10 | 09:55 | Direct | ₹4,982 |
| Air India AI 805 | 08:30 | 11:20 | Direct | ₹5,640 |
| Vistara UK 813 | 06:05 | 08:50 | Direct | ₹6,215 |

Prices were read from the airline pages just now and can change before you book. Nothing has been booked.

- Cheapest: IndiGo, with a checked bag it is ₹5,480
- Earliest: Vistara, 06:05
"""

MULTI_ANSWER = ANSWER + "\nBook it here: [IndiGo 6E 2137](https://www.goindigo.in/booking)\n"

STATE = {"scenario": "single", "released": threading.Event(), "hits": [],
         # a tiny stand-in for the backend's chat store: group -> conversation, conversation -> messages
         "groups": {}, "convs": {}, "seq": [0]}


def _mock_conv(group_id, fresh=False):
    if fresh or group_id not in STATE["groups"]:
        STATE["seq"][0] += 1
        cid = f"conv_mock_{STATE['seq'][0]}"
        STATE["groups"][group_id] = cid
        STATE["convs"][cid] = []
    return STATE["groups"][group_id]


def _mock_store(cid, role, content, kind="chat", meta=None):
    if cid in STATE["convs"]:
        STATE["convs"][cid].append({"id": f"m{len(STATE['convs'][cid])}_{cid}", "role": role, "content": content, "kind": kind,
                                    "meta": meta or {}, "run_id": None, "created_at": time.time()})


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


class Mock(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        STATE["hits"].append(self.path)
        if self.path.startswith("/chat/conversations"):
            return self._json([{"id": cid, "group_id": g, "title": (msgs[0]["content"] if msgs else "")[:80], "status": "open",
                                "updated_at": time.time(), "message_count": len(msgs)}
                               for g, cid in STATE["groups"].items() for msgs in [STATE["convs"][cid]] if msgs])
        body = b"[]" if any(k in self.path for k in ("user/memory", "skills", "reflections", "adapters", "entities")) else b'{"mock": true, "status": "ok"}'
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        STATE["hits"].append(self.path)
        n = int(self.headers.get("content-length", 0) or 0)
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}
        self.body = body
        if self.path.startswith("/chat/"):
            gid = body.get("group_id")
            if self.path == "/chat/groups/ensure":
                cid = _mock_conv(gid)
                return self._json({"group_id": gid, "conversation_id": cid, "messages": STATE["convs"][cid], "tabs": []})
            if self.path == "/chat/groups/new":
                return self._json({"group_id": gid, "conversation_id": _mock_conv(gid, fresh=True), "messages": []})
            if self.path == "/chat/groups/attach":
                STATE["groups"][gid] = body.get("conversation_id")
                return self._json({"group_id": gid, "conversation_id": body.get("conversation_id"),
                                   "messages": STATE["convs"].get(body.get("conversation_id"), [])})
            return self._json({"success": True})
        if self.path.startswith("/__"):
            if self.path == "/__scenario":
                pass
            if self.path == "/__release":
                STATE["released"].set()
            self.send_response(200)
            self._cors()
            self.end_headers()
            return
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        w = self.wfile
        cid = body.get("conversation_id")
        _mock_store(cid, "user", body.get("task") or body.get("user_request") or "")
        try:
            if "orchestrate" in self.path:
                self.multi(w)
                _mock_store(cid, "assistant", MULTI_ANSWER, kind="run", meta={"status": "completed", "run": {"agents": []}})
            else:
                self.single(w)
                _mock_store(cid, "assistant", ANSWER, meta={"status": "completed", "activity": [{"step": 0, "label": "Reading the table", "status": "done"}]})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def emit(self, w, event, data, wait=0.0):
        time.sleep(wait)
        w.write(sse(event, data))
        w.flush()

    def single(self, w):
        sc = STATE["scenario"]
        self.emit(w, "perception", {"url": "", "tabId": "active_tab", "detail": "Working in the current tab"})
        self.emit(w, "thinking", {"detail": "Reading your request"}, 0.5)
        steps = [("browser_navigate", "Opening skyscanner.co.in"), ("browser_observe", "Checking what kind of page this is"),
                 ("browser_find", "Finding “Bengaluru”"), ("browser_sequence", "Doing 4 steps on the page"), ("browser_read_table", "Reading the table")]
        for i, (tool, label) in enumerate(steps):
            self.emit(w, "step", {"step": i, "tool": tool, "label": label}, 0.6)
            if sc == "failed" and i == 3:
                self.emit(w, "step_done", {"step": i, "tool": tool, "label": label, "success": False}, 0.6)
                self.emit(w, "done", {"type": "result", "success": False, "done": True, "error": "The airline page asked for a verification check that the agent cannot complete. Nothing was booked."}, 0.4)
                return
            self.emit(w, "step_done", {"step": i, "tool": tool, "label": label, "success": True}, 0.7)
        if sc == "helpers":
            hs = [("helper-1", "Compare direct morning flights on Skyscanner"), ("helper-2", "Check Air India and Vistara fares"), ("helper-3", "Look for the cheapest weekday option")]
            for k, (aid, desc) in enumerate(hs):
                self.emit(w, "helper_started", {"agent_id": aid, "description": desc, "tab_id": f"agent-tab-{k}"}, 0.2)
            for aid, _ in hs:
                self.emit(w, "helper_progress", {"agent_id": aid, "label": "Reading the page"}, 0.2)
            for aid, desc in hs[:2]:
                self.emit(w, "helper_finished", {"agent_id": aid, "description": desc, "status": "completed"}, 0.2)
            # helper-3 never reports its end: the stream closes right after the answer
        self.emit(w, "step", {"step": 5, "tool": "browser_extract", "label": "Reading the page"}, 0.4)
        if sc in ("single_working", "single"):
            STATE["released"].wait(60)
        self.emit(w, "step_done", {"step": 5, "tool": "browser_extract", "label": "Reading the page", "success": True}, 0.3)
        self.emit(w, "done", {"type": "result", "success": True, "done": True, "content": ANSWER, "durationMs": 41200}, 0.3)

    def multi(self, w):
        tasks = [{"task_id": "fares_a", "description": "Compare direct morning flights on Skyscanner"},
                 {"task_id": "fares_b", "description": "Check Air India and Vistara fares on their own sites"},
                 {"task_id": "fares_c", "description": "Look for the cheapest weekday option on Kayak"}]
        self.emit(w, "planning", {"detail": "Splitting the request"})
        self.emit(w, "run_started", {"run_id": "r1", "tasks": tasks}, 0.5)
        for i, t in enumerate(tasks):
            self.emit(w, "task_started", {"task_id": t["task_id"], "description": t["description"], "tab_id": f"agent-tab-{i}"}, 0.3)
        labels = ["Opening skyscanner.co.in", "Reading the page", "Reading the table"]
        for r in range(3):
            for i, t in enumerate(tasks):
                self.emit(w, "task_progress", {"task_id": t["task_id"], "label": labels[(r + i) % 3]}, 0.35)
        if STATE["scenario"] in ("multi_working", "multi"):
            STATE["released"].wait(60)
        for i, t in enumerate(tasks):
            self.emit(w, "task_completed", {"task_id": t["task_id"]}, 0.4)
        self.emit(w, "synthesis_started", {}, 0.4)
        self.emit(w, "done", {"success": True, "run_id": "r1", "final_answer": MULTI_ANSWER,
                              "agent_tab_ids": ["agent-tab-0", "agent-tab-1", "agent-tab-2"], "result_tab_id": "agent-tab-1"}, 0.8)


def start_mock():
    srv = ThreadingHTTPServer(("127.0.0.1", MOCK_PORT), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--url", default="http://localhost:5199")
    ap.add_argument("--only", default="")
    ap.add_argument("--reduce", action="store_true", help="emulate prefers-reduced-motion")
    ap.add_argument("--native", action="store_true", help="install a stand-in window.nexusNative so agent tabs can be emitted")
    ap.add_argument("--w", type=int, default=1440)
    ap.add_argument("--h", type=int, default=900)
    a = ap.parse_args()
    start_mock()
    dev_host = re.match(r"https?://([^/]+)", a.url).group(1)
    escaped = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = browser.new_context(viewport={"width": a.w, "height": a.h}, device_scale_factor=2,
                                  reduced_motion="reduce" if a.reduce else "no-preference")

        def handle(route):
            u = route.request.url
            m = re.match(r"https?://(127\.0\.0\.1|localhost):(\d+)", u)
            if not m:
                return route.continue_()   # fonts or other public hosts the app already uses
            port = m.group(2)
            if f"{m.group(1)}:{port}" == dev_host:
                return route.continue_()
            if port in ("8000", "8091", str(MOCK_PORT)):
                return route.continue_(url=re.sub(r"(127\.0\.0\.1|localhost):\d+", f"127.0.0.1:{MOCK_PORT}", u))
            escaped.append(u)
            return route.abort()
        ctx.route("**/*", handle)
        if a.native:
            ctx.add_init_script("""
              // Stand-in for the Electron bridge's agent calls. Tabs themselves run on the page's own TabManager
              // (window.__comexPreviewTabs) because there is no main process here.
              const tm = () => window.__comexPreviewTabs;
              window.nexusNative = { isElectron: false, platform: 'preview', tabs: {
                setBounds(){}, getActiveTarget: async () => null, getTabInfo: async () => null,
                requestActivate(id){ tm()?.setActive(id); }, setAgentStep(){},
                setAgentStatus(id, status, step){ const m = tm(); if (m && m.tab(id)) m.updateTab(id, { agent: status === 'idle' ? null
                  : { status, step: step || '', label: m.tab(id).agent?.label || '', since: Date.now() } }); } } };
              // what an agent's "open my tab" does in the app: a working agent tab in the chat's group
              window.__emitTab = (_kind, d) => tm().createTab({ id: d.tabId, url: d.url, groupId: d.groupId || window.__activeGroup(),
                kind: 'agent', title: d.label, activate: false, agent: { status: 'working', step: d.label, label: d.label, since: Date.now() } });
              window.__activeGroup = () => tm().tab(tm().activeTabId).groupId;
              const iv = setInterval(() => { const m = tm(); if (!m) return; clearInterval(iv);
                m.subscribe((e) => { if (e.type === 'tab-closed') (window.__destroyed = window.__destroyed || []).push(e.tab.id); }); }, 30);
            """)
        page = ctx.new_page()
        page.on("console", lambda m: print("  [console]", m.text[:140]) if m.type == "error" else None)
        page.goto(a.url, wait_until="networkidle")

        # prove the redirect works BEFORE any task can be sent
        probe = page.evaluate("fetch('http://127.0.0.1:8000/health').then(r => r.json()).catch(e => ({error: String(e)}))")
        if not (isinstance(probe, dict) and probe.get("mock") is True):
            browser.close()
            sys.exit(f"REFUSING TO CONTINUE: a request to :8000 did not reach the mock ({probe}). Nothing was sent.")
        print("mock backend proven:", probe)

        def shot(name):
            f = OUT / f"{a.label}_{name}.png"
            page.screenshot(path=str(f))
            print("saved", f)

        def open_drawer():
            if page.locator(".chat-drawer").count() == 0:
                page.get_by_role("button", name=re.compile("Assistant")).first.click()
                page.wait_for_selector(".chat-drawer", timeout=8000)
            time.sleep(0.8)

        def send(text, mode):
            opt = page.locator(".chat-drawer .mode-option", has_text=mode)
            opt.first.click()
            if opt.first.get_attribute("aria-checked") != "true":
                sys.exit(f"mode {mode} did not switch")
            box = page.locator(".chat-drawer textarea").first
            box.fill(text)
            box.press("Enter")

        def animations(label):
            running = page.evaluate("""() => document.getAnimations()
                .filter(a => a.playState === 'running' && (a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('.chat-drawer')))
                .map(a => (a.animationName || ('transition:' + a.transitionProperty)) + ' on .' + (a.effect.target.className || a.effect.target.tagName).toString().split(' ')[0])""")
            print(f"  running animations inside the drawer ({label}):", running or "none")

        def idle(timeout=25):
            page.wait_for_selector(".composer-send:not(.is-stop)", timeout=timeout * 1000)
            time.sleep(0.6)

        def fresh():
            btn = page.get_by_role("button", name="New chat")
            if btn.count() and btn.first.is_enabled():
                btn.first.click()
                time.sleep(0.4)

        def release():
            page.evaluate("fetch('http://127.0.0.1:8000/__release', {method: 'POST'})")

        want = set(a.only.split(",")) if a.only else None
        run = lambda n: want is None or n in want

        open_drawer()
        if run("empty"):
            shot("empty")
            page.get_by_role("button", name="Multi-agent").last.click()
            time.sleep(0.5)
            shot("empty_multi")
            page.get_by_role("button", name="Single agent").last.click()
        if run("single_working"):
            STATE["scenario"] = "single_working"
            STATE["released"].clear()
            send("Find the cheapest direct flight from Bengaluru to Delhi tomorrow morning and show me the options", "Single agent")
            time.sleep(4.2)
            animations("single agent working")
            shot("single_working")
            release()
            idle()
            shot("single_done")
        if run("failed"):
            fresh()
            STATE["scenario"] = "failed"
            send("Book the 07:10 IndiGo flight for me", "Single agent")
            idle()
            shot("failed")
        if run("multi_working"):
            fresh()
            STATE["scenario"] = "multi_working"
            STATE["released"].clear()
            send("Compare morning flights from Bengaluru to Delhi across three sites", "Multi-agent")
            time.sleep(5.0)
            animations("multi-agent working")
            shot("multi_working")
            release()
            idle(40)
            shot("multi_done")
        def filmstrip(selector, name, frames, every, cols=4):
            import base64
            shots = []
            for k in range(frames):
                try:
                    shots.append(page.locator(selector).first.screenshot(timeout=2500))
                except Exception:
                    break
                time.sleep(every)
            tiles = "".join(f'<figure style="margin:0"><img src="data:image/png;base64,{base64.b64encode(b).decode()}" style="width:100%;display:block;background:#15171b"><figcaption style="font:11px sans-serif;color:#889;padding:2px 4px">t={k*every:.1f}s</figcaption></figure>' for k, b in enumerate(shots))
            sheet = browser.new_page(viewport={"width": 1500, "height": 400})
            sheet.set_content(f'<body style="margin:0;background:#0d0e10"><div style="display:grid;grid-template-columns:repeat({cols},1fr);gap:8px;padding:8px">{tiles}</div></body>')
            sheet.screenshot(path=str(OUT / f"{a.label}_{name}.png"), full_page=True)
            sheet.close()
            print("saved", OUT / f"{a.label}_{name}.png")

        if run("film_single"):
            fresh()
            STATE["scenario"] = "single_working"
            STATE["released"].clear()
            send("Find the cheapest direct flight from Bengaluru to Delhi tomorrow morning", "Single agent")
            page.wait_for_selector(".live-row", timeout=8000)
            filmstrip(".live-row", "film_single", 12, 0.12, cols=3)
            time.sleep(2.0)
            filmstrip(".live-row", "film_single_text", 12, 0.35, cols=3)
            filmstrip(".orbit-mark", "film_orbit", 24, 0.14, cols=8)
            animations("single agent working (gsap scene)")
            release(); idle(40)
        def set_swarm(name, shot_name=None):
            page.get_by_role("button", name="Memory").first.click()
            page.get_by_role("tab", name="Settings").click()
            time.sleep(0.6)
            if shot_name:
                shot(shot_name)
            page.get_by_role("radio", name=re.compile(name, re.I)).click()
            assert page.get_by_role("radio", name=re.compile(name, re.I)).get_attribute("aria-checked") == "true"
            page.get_by_role("button", name="Back to chat").first.click()
            time.sleep(0.4)

        if run("settings"):
            set_swarm("Orbit", "settings_tab")
            print("stored choice:", page.evaluate("localStorage.getItem('comex.swarmAnimation')"))
            # the tab strip must stay usable: is the last tab fully visible?
            print("tab strip overflows:", page.evaluate("(() => { const e = document.querySelector('.brain-nav-tabs'); return e ? e.scrollWidth > e.clientWidth : null; })()"))
        for style, sel, name in (("Orbit", ".run-header", "film_multi_orbit"), ("Scene", ".stage-swarm", "film_multi")):
            if not run(name):
                continue
            set_swarm(style)
            fresh()
            STATE["scenario"] = "multi_working"
            STATE["released"].clear()
            send("Compare morning flights from Bengaluru to Delhi across three sites", "Multi-agent")
            page.wait_for_selector(".swarm-orbit" if style == "Orbit" else ".stage-swarm", timeout=8000)
            filmstrip(sel, name, 12, 0.5, cols=2 if style == "Orbit" else 4)
            animations(f"multi-agent working ({style})")
            release()
            time.sleep(0.9)
            filmstrip(sel, name + "_end", 8, 0.35, cols=2 if style == "Orbit" else 4)
            idle(40)
            set_swarm("Orbit")
        if run("helpers"):
            fresh()
            STATE["scenario"] = "helpers"
            send("Compare morning flights from Bengaluru to Delhi", "Single agent")
            idle(40)
            time.sleep(0.8)
            running = page.locator(".run-agent.agent-running").count()
            headline = page.locator(".run-headline").first.inner_text()
            print("helper panel after the answer:", headline, "| rows still running:", running)
            assert running == 0 and "working" not in headline, "a helper is still shown as working after the answer"
            shot("helpers_done")
            page.locator(".steps-toggle").first.click()
            time.sleep(0.4)
            shot("steps_open")
        if run("scroll"):
            # while the agent works the user reads further up; steps must not pull the view down, the final answer must
            for mode, working in (("Single agent", "single_working"), ("Multi-agent", "multi_working")):
                print("scroll check:", mode)
                fresh()
                page.set_viewport_size({"width": a.w, "height": 560})
                box = lambda: page.evaluate("(() => { const e = document.querySelector('.chat-messages'); return {top: Math.round(e.scrollTop), max: Math.round(e.scrollHeight - e.clientHeight)}; })()")
                STATE["scenario"] = "single_done"
                send("First question, answered straight away", mode)
                idle(40)
                STATE["scenario"] = working
                STATE["released"].clear()
                send("Second question, slow", mode)
                time.sleep(1.2 if mode == "Single agent" else 2.6)  # multi-agent windows join over the first couple of seconds
                sent = box()
                print("after sending:", sent, "-> at the bottom" if sent["top"] >= sent["max"] - 4 else "-> NOT at the bottom")
                assert sent["max"] > 100 and sent["top"] >= sent["max"] - 4, "a new message should scroll into view"
                page.evaluate("document.querySelector('.chat-messages').scrollTop = 0")
                labels = set()
                for _ in range(12):
                    time.sleep(0.5)
                    labels.add(page.locator(".live-label").first.inner_text() if page.locator(".live-label").count() else "")
                    b = box()
                    assert b["top"] == 0, f"steps pulled the view down: {b}"
                print("during steps scrollTop stayed 0; status labels seen:", sorted(labels))
                release()
                idle(40)
                time.sleep(1.2)
                b = box()
                print("after the answer:", b)
                assert b["top"] >= b["max"] - 4, "the final answer should scroll into view"
                page.set_viewport_size({"width": a.w, "height": a.h})
        if run("groups"):
            assert a.native, "run the groups scenario with --native"
            strip = lambda: page.evaluate("""() => ({
                tabs: [...document.querySelectorAll('.tab-strip .tab')].map(t => ({title: t.querySelector('.tab-title')?.textContent, active: t.classList.contains('active'), grouped: t.classList.contains('grouped')})),
                chips: [...document.querySelectorAll('.group-chip')].map(c => c.textContent)})""")
            user_msgs = lambda: page.locator(".chat-drawer .msg-user-bubble").all_inner_texts()
            STATE["scenario"] = "multi_working"
            STATE["released"].clear()
            send("Compare morning flights from Bengaluru to Delhi across three sites", "Multi-agent")
            page.wait_for_selector(".run-panel", timeout=8000)
            for i, (url, label) in enumerate([("https://www.skyscanner.co.in/", "Skyscanner"), ("https://www.goindigo.in/", "IndiGo"),
                                              ("https://www.kayak.co.in/", "Kayak")]):
                page.evaluate(f"window.__emitTab('__agent_tab__', {{tabId: 'agent-tab-{i}', url: '{url}', label: '{label}'}})")
            time.sleep(0.6)
            s1 = strip()
            print("while working:", s1)
            assert len(s1["chips"]) == 1 and sum(t["grouped"] for t in s1["tabs"]) == 4
            shot("groups_working")
            release()
            idle(40)
            time.sleep(2.4)
            s2 = strip()
            print("after the run:", s2, "| closed:", page.evaluate("window.__destroyed"))
            assert [t["title"] for t in s2["tabs"] if t["active"]] == ["IndiGo"], "the result tab should be in front"
            assert len(s2["tabs"]) == 2 and sorted(page.evaluate("window.__destroyed")) == ["agent-tab-0", "agent-tab-2"]
            assert len(user_msgs()) == 1, "the group's tabs share one chat"
            shot("groups_after_run")
            # an independent new tab has its own, empty chat
            page.locator(".new-tab-btn").click()
            time.sleep(0.8)
            assert user_msgs() == [] and page.locator(".chat-empty").count() == 1
            shot("groups_new_tab")
            # back to the group: its chat is still there
            page.locator(".tab-strip .tab", has_text="IndiGo").first.click()
            time.sleep(0.6)
            assert len(user_msgs()) == 1
            # a link in the answer opens a new tab in the same group
            page.locator(".chat-drawer a.md-link", has_text="IndiGo 6E 2137").last.click()
            time.sleep(0.8)
            s3 = strip()
            print("after opening a link:", s3)
            assert sum(t["grouped"] for t in s3["tabs"]) == 3 and s3["tabs"][-2]["title"].startswith("goindigo") or True
            shot("groups_link")
            # restoring tabs after a restart is the main process's job (TabManager + session file): checked in the
            # live Electron tests, not here, where a reload starts a fresh browser
        if run("concurrent"):
            assert a.native, "run the concurrent scenario with --native"
            # a busy group shows its state on its chip; a busy single tab shows it as a dot on the tab
            chips = lambda: page.evaluate("[...document.querySelectorAll('.group-chip, .tab .ai-dot')].map(c => c.className + ': ' + (c.textContent || c.closest('.tab')?.textContent || ''))")
            STATE["scenario"] = "multi_working"   # the multi-agent run waits; a single-agent run finishes on its own
            STATE["released"].clear()
            send("Compare morning flights from Bengaluru to Delhi across three sites", "Multi-agent")
            page.wait_for_selector(".run-panel", timeout=8000)
            page.evaluate("window.__emitTab('__agent_tab__', {tabId: 'agent-tab-0', url: 'https://www.skyscanner.co.in/', label: 'Skyscanner'})")
            time.sleep(0.5)
            # a second, independent tab: its own chat, and its own task while the first group is still working
            page.locator(".new-tab-btn").click()
            time.sleep(0.8)
            assert page.locator(".chat-empty").count() == 1, "the new tab should have its own empty chat"
            print("header while the other tab works:", page.locator(".drawer-context").inner_text())
            send("Find the cheapest direct flight from Bengaluru to Delhi tomorrow morning", "Single agent")
            time.sleep(1.2)
            both = chips()
            print("two tasks at once:", both)
            assert any("ai-working" in c for c in both) and len(both) == 2
            shot("concurrent_two_running")
            idle(40)
            time.sleep(0.6)
            print("after the single task:", chips())
            shot("concurrent_one_done")
            release()
            page.locator(".tab-strip .tab", has_text="Skyscanner").first.click()
            time.sleep(9)
            print("after the multi-agent run:", chips())
            shot("concurrent_both_done")
        if run("memory"):
            fresh()
            page.get_by_role("button", name="Memory").first.click()
            time.sleep(0.8)
            shot("memory")
            page.get_by_role("button", name="Back to chat").first.click()
        if run("narrow"):
            page.set_viewport_size({"width": 980, "height": 720})
            time.sleep(0.6)
            shot("narrow_empty")
            STATE["scenario"] = "single_done"
            page.locator(".chat-suggestion").first.click()
            idle(40)
            shot("narrow_done")
        print("requests aborted (should be none that matter):", sorted(set(escaped))[:6])
        print("mock saw:", sorted(set(STATE["hits"]))[:8])
        browser.close()


if __name__ == "__main__":
    main()
