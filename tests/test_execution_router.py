"""Execution router: deterministic policy, optional Jev, and every way Jev can fail."""

from __future__ import annotations

import json
import logging
import time

import httpx
import pytest

from services.execution_router import (
    JEV_P_PROGRAM,
    JevClient,
    RouteDecision,
    RouteRequest,
    analyse_task,
    route,
    route_deterministic,
)

KEY = "apikey_TEST_KEY_THAT_MUST_NEVER_LEAK_0123456789"
BORDERLINE = "Tick every checkbox in this settings list and then save"


def jev_client(handler, **kw):
    return JevClient(api_key=KEY, url="https://jev.test/v1/systemone", transport=httpx.MockTransport(handler), **kw)


def jev_ok(p):
    def h(request):
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {"many_ops": {"type": "noul", "noul": p}}, "usage": {}})
    return h


class Counter:
    def __init__(self, inner):
        self.inner, self.n = inner, 0

    def __call__(self, request):
        self.n += 1
        return self.inner(request)


def decide(task, page_path=None):
    return route_deterministic(RouteRequest(task=task, page_path=page_path))[0]


# ── deterministic policy ─────────────────────────────────────────────────────────────────────────
def test_straightforward_browsing_is_typed_and_makes_no_model_call():
    for task in ("Go to Wikipedia and find out when the Eiffel Tower was completed", "Open the pricing page and tell me what the Pro plan costs",
                 "Fill the five fields of the shipping address form with this address", "Add these three books to the cart: Dune, Emma and Ulysses"):
        d, borderline = route_deterministic(RouteRequest(task=task))
        assert d.execution == "typed" and not borderline and not d.uncertain and d.source == "deterministic" and d.perception == ["semantic"], (task, d)


def test_many_predictable_operations_are_routed_to_a_program():
    for task in ("Enter these 45 customer records into the CRM form, one after another", "Rename the 40 tags following the pattern tag-01 to tag-40",
                 "Click Accept on each of the 22 pending requests", "Go through all 50 pages of search results and collect each product title"):
        d, borderline = route_deterministic(RouteRequest(task=task))
        assert d.execution == "program" and not borderline and d.source == "deterministic", (task, d)
        assert "visual" not in d.perception, "a program does not imply screenshots"


def test_canvas_tasks_need_visual_perception_but_a_few_actions_stay_typed():
    few = decide("Draw one red rectangle on the Excalidraw canvas", "visual")
    assert few.execution == "typed" and "visual" in few.perception
    chess = decide("Play e2 to e4 as White's opening move", "visual")
    assert chess.execution == "typed" and "visual" in chess.perception
    long = decide("Draw a detailed sailing ship on the sea with three sails, waves, a sun and ten clouds in Excalidraw", "visual")
    assert long.execution == "program" and "visual" in long.perception and any("detailed" in s or "many" in s for s in long.signals)


def test_complete_table_extraction_stays_typed_however_many_rows_and_asks_for_structured_perception():
    for task, page in (("Extract all 57 rows of the grade history table", "table"), ("Export all 200 rows of this results table as text", None),
                       ("Copy every row of the attendance table into a list, including the other pages", "table")):
        d = decide(task, page)
        assert d.execution == "typed" and d.source == "override_table" and "structured" in d.perception and d.confidence >= 0.9, (task, d)
    # but filling a table in is many operations, not one extraction
    assert decide("Fill in all 40 rows of this table with the values below").execution == "program"


def test_perception_and_execution_are_independent_choices():
    assert decide("Look at this bar chart and tell me which month had the highest sales", "visual").perception == ["semantic", "visual"]
    assert decide("Look at this bar chart and tell me which month had the highest sales", "visual").execution == "typed"
    p = decide("Tick the box next to each of the 80 emails in this list and archive them", "semantic")
    assert p.execution == "program" and "visual" not in p.perception


def test_vague_requests_are_flagged_uncertain_without_asking_jev():
    for task in ("Make the drawing look nicer", "Clean up this page", "Do the same thing for the rest of them", "Handle the pending items"):
        d, borderline = route_deterministic(RouteRequest(task=task))
        assert d.uncertain and d.execution == "typed" and d.escalate == "main_model_decides" and not borderline, (task, d)


def test_deterministic_path_is_fast_and_pure():
    t0 = time.perf_counter()
    for _ in range(200):
        route_deterministic(RouteRequest(task="Draw a floor plan of a three bedroom house with doors, windows and furniture labels"))
    assert (time.perf_counter() - t0) / 200 < 0.005
    assert analyse_task("x") == analyse_task("x")


def test_request_validation_rejects_empty_and_unknown_page_kinds():
    with pytest.raises(Exception):
        RouteRequest(task="")
    with pytest.raises(Exception):
        RouteRequest(task="hello", page_path="spreadsheet")  # type: ignore[arg-type]


# ── Jev: used only for borderline tasks ─────────────────────────────────────────────────────────
async def test_borderline_task_uses_jev_and_each_answer_band_is_handled():
    d, borderline = route_deterministic(RouteRequest(task=BORDERLINE))
    assert borderline and d.uncertain and d.escalate == "program_if_typed_stalls"
    yes = await route(RouteRequest(task=BORDERLINE), jev=jev_client(jev_ok(0.91)), use_jev=True)
    assert yes.execution == "program" and yes.source == "jev" and yes.jev_called and yes.jev_p == 0.91 and not yes.uncertain and yes.confidence >= JEV_P_PROGRAM
    no = await route(RouteRequest(task=BORDERLINE), jev=jev_client(jev_ok(0.08)), use_jev=True)
    assert no.execution == "typed" and no.source == "jev" and no.confidence == 0.92 and not no.uncertain
    unsure = await route(RouteRequest(task=BORDERLINE), jev=jev_client(jev_ok(0.5)), use_jev=True)
    assert unsure.execution == "typed" and unsure.uncertain and unsure.fallback == "jev_low_confidence" and unsure.source == "fallback"


async def test_jev_is_never_called_for_clear_or_vague_or_table_cases():
    c = Counter(jev_ok(0.99))
    client = jev_client(c)
    for task, page in (("Open the pricing page and tell me what the Pro plan costs", None), ("Enter these 45 customer records into the CRM form, one after another", None),
                       ("Extract all 57 rows of the grade history table", "table"), ("Make the drawing look nicer", "visual")):
        await route(RouteRequest(task=task, page_path=page), jev=client, use_jev=True)
    assert c.n == 0


async def test_jev_is_not_called_unless_enabled_and_the_default_follows_the_environment(monkeypatch):
    c = Counter(jev_ok(0.99))
    d = await route(RouteRequest(task=BORDERLINE), jev=jev_client(c), use_jev=False)
    assert c.n == 0 and d.fallback == "jev_not_enabled" and d.execution == "typed" and d.uncertain
    monkeypatch.delenv("COMEX_JEV_ROUTER", raising=False)
    assert (await route(RouteRequest(task=BORDERLINE), jev=jev_client(c))).fallback == "jev_not_enabled"
    monkeypatch.setenv("COMEX_JEV_ROUTER", "1")
    assert (await route(RouteRequest(task=BORDERLINE), jev=jev_client(c))).source == "jev"


@pytest.mark.parametrize("name,handler,reason", [
    ("server error", lambda r: httpx.Response(500, text="boom"), "jev_http_500"),
    ("unauthorized", lambda r: httpx.Response(401, json={"error": "bad key"}), "jev_http_401"),
    ("not json", lambda r: httpx.Response(200, text="<html>"), "jev_invalid_response"),
    ("missing answer", lambda r: httpx.Response(200, json={"answers": {}}), "jev_invalid_response"),
    ("value is text", lambda r: httpx.Response(200, json={"answers": {"many_ops": {"noul": "yes"}}}), "jev_invalid_response"),
    ("value above one", lambda r: httpx.Response(200, json={"answers": {"many_ops": {"noul": 1.7}}}), "jev_invalid_response"),
    ("value negative", lambda r: httpx.Response(200, json={"answers": {"many_ops": {"noul": -0.2}}}), "jev_invalid_response"),
    ("value is a bool", lambda r: httpx.Response(200, json={"answers": {"many_ops": {"noul": True}}}), "jev_invalid_response"),
    ("value is null", lambda r: httpx.Response(200, json={"answers": {"many_ops": {"noul": None}}}), "jev_invalid_response"),
])
async def test_every_invalid_or_failed_jev_answer_falls_back_to_typed_uncertain(name, handler, reason):
    d = await route(RouteRequest(task=BORDERLINE), jev=jev_client(handler), use_jev=True)
    assert (d.execution, d.uncertain, d.source, d.fallback, d.escalate) == ("typed", True, "fallback", reason, "program_if_typed_stalls"), name
    assert d.jev_p is None


async def test_timeout_and_unreachable_server_and_missing_key_fall_back():
    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    def down(request):
        raise httpx.ConnectError("no route", request=request)
    assert (await route(RouteRequest(task=BORDERLINE), jev=jev_client(slow), use_jev=True)).fallback == "jev_timeout"
    assert (await route(RouteRequest(task=BORDERLINE), jev=jev_client(down), use_jev=True)).fallback == "jev_unreachable"
    c = Counter(jev_ok(0.9))
    nokey = JevClient(api_key="", transport=httpx.MockTransport(c))
    d = await route(RouteRequest(task=BORDERLINE), jev=nokey, use_jev=True)
    assert d.fallback == "jev_no_key" and c.n == 0 and not d.jev_called and d.execution == "typed"


async def test_circuit_breaker_stops_calling_a_failing_service_and_cache_avoids_repeat_calls():
    c = Counter(lambda r: httpx.Response(500))
    client = jev_client(c)
    for i in range(3):
        await route(RouteRequest(task=f"{BORDERLINE} {i}"), jev=client, use_jev=True)
    assert c.n == 3
    d = await route(RouteRequest(task=f"{BORDERLINE} again"), jev=client, use_jev=True)
    assert d.fallback == "jev_circuit_open" and c.n == 3, "after three failures it stops calling for a while"
    ok = Counter(jev_ok(0.9))
    good = jev_client(ok)
    for _ in range(3):
        await route(RouteRequest(task=BORDERLINE), jev=good, use_jev=True)
    assert ok.n == 1


async def test_the_api_key_never_appears_in_decisions_representations_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    client = jev_client(lambda r: httpx.Response(500, text=f"echo {KEY}"))
    d = await route(RouteRequest(task=BORDERLINE), jev=client, use_jev=True)
    d2 = await route(RouteRequest(task=BORDERLINE), jev=jev_client(jev_ok(0.9)), use_jev=True)
    for blob in (json.dumps(d.model_dump()), json.dumps(d2.model_dump()), repr(client), str(d), caplog.text):
        assert KEY not in blob
    assert isinstance(d, RouteDecision) and d.model_dump()["fallback"] == "jev_http_500"
