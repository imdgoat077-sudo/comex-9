"""
The single agent works in the tab the user is looking at, and stays there for the whole run.

Before: every tool call re-resolved "the active tab" as the first page in Chrome's target list, which has nothing to do
with the tab on screen and reorders when pages navigate. The agent could work in an unseen tab, or hop tabs mid-run.
"""

from __future__ import annotations

import json

import pytest

import agent_service as A
from nervous.action_policy import get_target_registry


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b


def page(tid, url):
    return {"id": tid, "type": "page", "url": url, "webSocketDebuggerUrl": f"ws://127.0.0.1:9222/devtools/page/{tid}"}


UI = page("UI", "http://localhost:5173/")
SHIELD = page("SHIELD", "file:///Users/me/Comex/electron/agent_shield.html")
CURSOR = page("CURSOR", "file:///Users/me/Comex/electron/cursor.html")
HOME = page("HOME", "about:blank")
SHOP = page("SHOP", "https://shop.example/")
NEWS = page("NEWS", "https://news.example/")


def serve(monkeypatch, targets):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp(targets))


@pytest.fixture(autouse=True)
def _clean():
    get_target_registry().reset()
    A._FG_PINS.clear()
    yield
    get_target_registry().reset()
    A._FG_PINS.clear()


def test_the_tab_on_screen_wins_even_when_it_is_not_first_in_chromes_list(monkeypatch):
    serve(monkeypatch, [UI, SHIELD, HOME, SHOP, NEWS])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "NEWS")
    assert A._resolve_foreground_cdp_ws().endswith("/NEWS")


def test_without_an_answer_from_electron_overlay_windows_and_the_interface_are_never_picked(monkeypatch):
    serve(monkeypatch, [UI, SHIELD, CURSOR, page("DIST", "file:///app/dist/index.html"), SHOP, NEWS])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: None)
    assert A._resolve_foreground_cdp_ws().endswith("/SHOP")
    serve(monkeypatch, [UI, SHIELD])
    assert A._resolve_foreground_cdp_ws() == ""


def test_a_reported_tab_that_no_longer_exists_falls_back_to_a_real_page(monkeypatch):
    serve(monkeypatch, [UI, SHOP])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "GONE")
    assert A._resolve_foreground_cdp_ws().endswith("/SHOP")


def test_electron_being_unreachable_is_not_an_error(monkeypatch):
    monkeypatch.setattr(A, "CDP_URL", "http://127.0.0.1:1")  # nothing listens here
    assert A._electron_active_target_id() is None


def test_a_pinned_run_stays_on_its_tab_when_the_list_reorders_or_the_user_switches_tabs(monkeypatch):
    serve(monkeypatch, [UI, SHIELD, SHOP, NEWS])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "SHOP")
    alias = A._pin_foreground_tab("run1")
    assert alias and alias.startswith("fg-")
    # the page navigates and Chrome lists the other tab first; the user also switches to the other tab
    serve(monkeypatch, [NEWS, UI, SHIELD, SHOP])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "NEWS")
    for _ in range(3):  # every tool call resolves again
        target_id, ws = A._resolve_verified_tab_ws(alias, trusted_app_context=True)
        assert target_id == "SHOP" and ws.endswith("/SHOP")


def test_a_pinned_tab_that_is_closed_fails_closed_instead_of_hopping_to_another_tab(monkeypatch):
    serve(monkeypatch, [UI, SHOP, NEWS])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "SHOP")
    alias = A._pin_foreground_tab("run2")
    serve(monkeypatch, [UI, NEWS])  # SHOP was closed
    assert A._resolve_verified_tab_ws(alias, trusted_app_context=True) == (None, None)


def test_pin_registry_is_bounded(monkeypatch):
    serve(monkeypatch, [UI, SHOP])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "SHOP")
    aliases = [A._pin_foreground_tab(f"r{i}") for i in range(40)]
    assert len(A._FG_PINS) == 32
    assert get_target_registry().lookup_tab_target(aliases[0]) is None
    assert get_target_registry().lookup_tab_target(aliases[-1]) is not None


async def test_the_wrapper_pins_a_trusted_single_agent_and_releases_the_pin_afterwards(monkeypatch):
    seen = {}

    async def fake_impl(task, default_cdp_url, **kw):
        seen.update(kw)
        seen["registered"] = get_target_registry().lookup_tab_target(kw["tab_id"])
        return "ok"
    serve(monkeypatch, [UI, SHOP])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "SHOP")
    monkeypatch.setattr(A, "_execute_agent_loop_impl", fake_impl)
    out = await A.execute_agent_loop("do it", "http://x", tab_id="active_tab", trusted_app_context=True)
    assert out == "ok"
    assert seen["tab_id"].startswith("fg-") and seen["registered"][0] == "SHOP"
    assert get_target_registry().lookup_tab_target(seen["tab_id"]) is None, "the pin is released when the run ends"
    assert not A._FG_PINS


async def test_the_wrapper_releases_the_pin_even_when_the_run_raises(monkeypatch):
    async def boom(task, default_cdp_url, **kw):
        raise RuntimeError("model exploded")
    serve(monkeypatch, [UI, SHOP])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "SHOP")
    monkeypatch.setattr(A, "_execute_agent_loop_impl", boom)
    with pytest.raises(RuntimeError):
        await A.execute_agent_loop("x", "http://x", trusted_app_context=True)
    assert not A._FG_PINS and not get_target_registry()._targets


@pytest.mark.parametrize("kw", [
    {"worker_id": "w1", "trusted_app_context": False, "tab_id": "agent-tab-1"},      # workers keep their leased tab
    {"trusted_app_context": True, "tab_id": "tab-explicit-9"},                         # an explicit tab is respected
    {"trusted_app_context": True, "tab_id": "active_tab", "legacy_mode": True},      # legacy mode is untouched
    {"trusted_app_context": False, "tab_id": "active_tab"},                            # untrusted callers get no foreground
])
async def test_the_wrapper_leaves_everything_else_alone(monkeypatch, kw):
    seen = {}

    async def fake_impl(task, default_cdp_url, **k):
        seen.update(k)
        return "ok"
    serve(monkeypatch, [UI, SHOP])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: "SHOP")
    monkeypatch.setattr(A, "_execute_agent_loop_impl", fake_impl)
    await A.execute_agent_loop("x", "http://x", **kw)
    assert seen["tab_id"] == kw["tab_id"] and not get_target_registry()._targets


async def test_if_no_tab_can_be_found_the_run_proceeds_exactly_as_before(monkeypatch):
    seen = {}

    async def fake_impl(task, default_cdp_url, **k):
        seen.update(k)
        return "ok"
    serve(monkeypatch, [UI])
    monkeypatch.setattr(A, "_electron_active_target_id", lambda: None)
    monkeypatch.setattr(A, "_execute_agent_loop_impl", fake_impl)
    await A.execute_agent_loop("x", "http://x", trusted_app_context=True)
    assert seen.get("tab_id") in (None, "active_tab")
