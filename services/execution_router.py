"""
Execution routing for Comex: two independent decisions made once per task, before the agent loop starts.

    PERCEPTION  what the task has to be looked at with:  semantic (DOM, text, elements), structured (a complete table or
                record extraction), visual (screenshots). A task can need several; none of them implies a program.
    EXECUTION   typed    the existing typed browser tools (the default; includes one structured operation that returns a lot)
                program  a bounded Python-driven browser program that does many predictable operations in one call

Policy, in order (cheapest first; the common path makes no network call and takes microseconds):
  1. Vague request (no concrete content to classify)      -> typed, uncertain, the main model decides. Jev is not asked: it cannot know either.
  2. Complete table extraction                            -> typed (browser_read_table), override. A big output is not a big execution.
  3. Strong many-operations signals (large counts, loops,
     detailed drawings)                                   -> program.
  4. Clearly small or ordinary                            -> typed.
  5. Borderline                                           -> ask Jev's many_ops yes/no once, if enabled. p >= 0.70 -> program,
                                                             p <= 0.35 -> typed, otherwise uncertain.
  6. Jev disabled, down, slow, invalid, or unsure         -> typed, uncertain, fallback reason recorded, escalation hint attached.

Never called after browser actions. The Jev call sends the task text and the page kind to TypeSafe, so it only happens when
COMEX_JEV_ROUTER=1 (agent_service.py --jevmode) and the task is borderline. The API key is read from the environment
(TYPESAFE_API_KEY), is never logged, returned or stored.

This module only DECIDES. It does not execute anything, and "program" is a recommendation: the agent-facing program tool is
not connected yet, so until it is the decision is advisory.
"""

from __future__ import annotations

import logging
import math
import os
import re
import time
from collections import OrderedDict
from typing import Any, Dict, List, Literal, Optional, Tuple

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("comex.services.execution_router")

Execution = Literal["typed", "program"]
Perception = Literal["semantic", "structured", "visual"]
PagePath = Literal["semantic", "table", "visual", "mixed"]

# ── thresholds (the Jev ones come from the 30-task dev probe: program tasks 0.74 and above, others 0.40 and below) ──
SCORE_PROGRAM = 0.70      # deterministic score at or above which the task is routed to a program
SCORE_TYPED = 0.25        # at or below which it is clearly ordinary
JEV_P_PROGRAM = 0.70
JEV_P_TYPED = 0.35
JEV_TIMEOUT_S = float(os.getenv("COMEX_JEV_TIMEOUT_S", "1.5"))
JEV_URL = os.getenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai/v1/systemone")
CIRCUIT_FAILURES = 3
CIRCUIT_PAUSE_S = 60.0

_JEV_QUESTION = {
    "many_ops": {
        "type": "noul",
        "instructions": "The task needs more than about eight similar or computed browser operations (many shapes, many fields, many items)",
    }
}


class RouteRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    page_path: Optional[PagePath] = None   # what browser_observe already reported, if anything


class RouteDecision(BaseModel):
    execution: Execution
    perception: List[Perception]
    confidence: float = Field(ge=0.0, le=1.0)
    source: str                              # override_table | deterministic | jev | fallback
    signals: List[str]                       # the evidence behind the choice, in plain words
    uncertain: bool = False                  # True: the router could not classify with confidence; execution defaults to typed
    fallback: Optional[str] = None           # why Jev's answer was not used, when it was wanted
    escalate: Optional[Literal["main_model_decides", "program_if_typed_stalls"]] = None
    jev_called: bool = False
    jev_p: Optional[float] = None
    latency_ms: float = 0.0


# ── deterministic analysis ───────────────────────────────────────────────────────────────────────
_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100, "dozen": 12}
_NUM = r"(\d+|" + "|".join(_WORD_NUM) + r")"
_UNITS = (r"(?:rows?|records?|items?|line items|products?|tags?|requests?|emails?|pages?|links?|codes?|fields?|squares?|cells?|slots?|"
          r"boxes|checkboxes?|buildings?|shapes?|branches|planets?|files?|posts?|cards?|entries|profiles?|customers?|messages?|photos?|"
          r"names?|values?|clouds?|stars?|windows?|trees?|houses?|elements?|points?|labels?|users?|orders?|months?|days?|weeks?|bars?)")
_COUNT_RE = re.compile(rf"\b{_NUM}\s+(?:[a-z\-]+\s+){{0,2}}?{_UNITS}\b")
_BY_RE = re.compile(r"\b(\d+)\s*(?:x|by)\s*(\d+)\b")

_OP_VERB = re.compile(r"\b(enter|type|fill|tick|click|drag|rename|set|reorder|mark|accept|open|upvote|select|add|delete|remove|archive|colou?r|"
                      r"draw|update|approve|press|check off)\b")
_EXTRACT_VERB = re.compile(r"\b(extract|copy|list|read|export|get|collect|show|tell|find|summari[sz]e|who|which|what|compare|gather)\b")
_STRONG_OP = re.compile(r"\b(enter|fill|tick|click|drag|rename|set|reorder|mark|accept|type|approve|archive)\b")
_EACH = re.compile(r"\b(each|every|one after another|one by one|all \d+|one at a time|each one)\b")
_LOOP = re.compile(r"\b(go through|click through|work through|for each|iterate|loop|repeat)\b")
_TABLE = re.compile(r"\b(tables?|standings|directory|attendance|transcript|fixtures|price list)\b")
_DRAW = re.compile(r"\b(draw|sketch|paint|illustrate)\b")
_ARTEFACT = re.compile(r"\b(floor plan|diagram|flowchart|mind map|skyline|map of|infographic|mural|landscape|chessboard|timeline|org chart|bar chart|"
                       r"pie chart|scene|poster|logo design)\b")
_DETAIL = re.compile(r"\b(detailed|elaborate|intricate|complex|colou?rful|realistic|full|complete)\b")
_VISUAL = re.compile(r"\b(draw|sketch|paint|canvas|whiteboard|excalidraw|chess|wordle|minesweeper|game|chart|graph|logo|pictures?|images?|photos?|"
                     r"screenshot|gauge|map pin|layout|look(?:s)? like|look at|highlighted|diagram|flowchart|mind map|floor plan|skyline|"
                     r"pawn|knight|bishop|rook|checkmate)\b")
_VAGUE = re.compile(r"\b(nicer|prettier|better looking|clean up|tidy|organi[sz]e|handle|sort out|finish the|update the records|"
                    r"fill out the form|do the same|the rest of them|rest of them|pending items|take care of)\b")


def _num(tok: str) -> int:
    return int(tok) if tok.isdigit() else _WORD_NUM.get(tok, 0)


def _max_count(t: str) -> int:
    best = 0
    for m in _COUNT_RE.finditer(t):
        best = max(best, _num(m.group(1)))
    for m in _BY_RE.finditer(t):
        best = max(best, int(m.group(1)) * int(m.group(2)))
    return best


def _parts_listed(t: str) -> int:
    """How many things a drawing request enumerates: 'with doors, windows and furniture labels' -> 3."""
    m = re.search(r"\bwith\b(.+)", t)
    if not m:
        return 0
    return len([p for p in re.split(r",|\band\b", m.group(1)) if len(p.strip().split()) >= 1 and p.strip()])


def analyse_task(task: str) -> Dict[str, Any]:
    """Pure function: the deterministic evidence. No I/O."""
    t = " ".join(task.lower().split())
    n_words = len(t.split())
    count = _max_count(t)
    op = bool(_OP_VERB.search(t))
    strong_op = bool(_STRONG_OP.search(t))
    each = bool(_EACH.search(t))
    loop = bool(_LOOP.search(t))
    draw = bool(_DRAW.search(t))
    artefact = bool(_ARTEFACT.search(t))
    detail = bool(_DETAIL.search(t))
    parts = _parts_listed(t) if draw else 0
    table = bool(_TABLE.search(t))
    extract = bool(_EXTRACT_VERB.search(t))
    has_number = bool(re.search(rf"\b{_NUM}\b", t))
    vague = bool(_VAGUE.search(t)) and not (count >= 6)
    score = 0.0
    sig: List[str] = []
    if count >= 20:
        score += 0.6; sig.append(f"large count ({count})")
    elif count >= 8:
        score += 0.4; sig.append(f"many items ({count})")
    elif count >= 6:
        score += 0.2; sig.append(f"several items ({count})")
    if count >= 20 and op:
        score += 0.15; sig.append("an operation on each of them")
    if op and each and count >= 6:
        score += 0.25; sig.append("'each/every' with an operation")
    if loop:
        score += 0.15; sig.append("loop wording")
    if strong_op and each and count < 6:
        score += 0.3; sig.append("an operation on 'each/every' of an unstated number of things")
    if draw:
        d = 0.05
        if detail:
            d += 0.5; sig.append("detailed drawing")
        if artefact:
            d += 0.3; sig.append("multi-part artefact")
        if parts >= 5:
            d += 0.3; sig.append(f"{parts} parts listed")
        elif parts >= 3:
            d += 0.15; sig.append(f"{parts} parts listed")
        if count >= 8:
            d += 0.55; sig.append("drawing with many elements")
        score += d
    return {"n_words": n_words, "count": count, "op": op, "strong_op": strong_op, "each": each, "loop": loop, "draw": draw,
            "table": table, "extract": extract, "has_number": has_number, "vague": vague, "score": round(min(score, 1.0), 3),
            "signals": sig}


def perceive(task: str, page_path: Optional[str], table_override: bool) -> List[str]:
    t = task.lower()
    need = ["semantic"]  # DOM and text are cheap and always useful
    if table_override or page_path == "table":
        need.append("structured")
    if page_path in ("visual", "mixed") or _VISUAL.search(t):
        need.append("visual")
    return need


def route_deterministic(req: RouteRequest) -> Tuple[RouteDecision, bool]:
    """Everything that needs no network. Returns (decision, borderline): borderline means Jev's yes/no may settle it."""
    t0 = time.perf_counter()
    a = analyse_task(req.task)
    sig = list(a["signals"])

    def done(execution, conf, source, signals, **kw):
        table_override = source == "override_table"
        return RouteDecision(execution=execution, perception=perceive(req.task, req.page_path, table_override), confidence=conf,
                             source=source, signals=signals, latency_ms=round((time.perf_counter() - t0) * 1000, 3), **kw)

    if a["vague"] and a["score"] < SCORE_PROGRAM:
        return done("typed", 0.5, "deterministic", ["the request has no concrete content to classify"], uncertain=True,
                    escalate="main_model_decides"), False
    if a["table"] and a["extract"] and not a["strong_op"]:
        return done("typed", 0.92, "override_table", ["complete table extraction: one structured operation, however many rows"] ), False
    if a["score"] >= SCORE_PROGRAM:
        return done("program", round(min(0.95, 0.55 + 0.4 * a["score"]), 2), "deterministic", sig), False
    if a["score"] <= SCORE_TYPED:
        conf = 0.9 if a["score"] == 0 else 0.8
        return done("typed", conf, "deterministic", sig or ["ordinary task: no repeated or computed operations"]), False
    return done("typed", 0.5, "deterministic", sig + ["borderline: some many-operations signals, not enough"], uncertain=True,
                escalate="program_if_typed_stalls"), True


# ── Jev (optional) ───────────────────────────────────────────────────────────────────────────────
class JevError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class JevClient:
    """One yes/no question, a short timeout, a small cache, and a circuit breaker. Never raises into the router."""

    def __init__(self, api_key: Optional[str] = None, url: str = JEV_URL, timeout_s: float = JEV_TIMEOUT_S,
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._key = api_key if api_key is not None else os.getenv("TYPESAFE_API_KEY", "")
        self._url = url
        self._timeout = timeout_s
        self._transport = transport
        self._cache: "OrderedDict[str, float]" = OrderedDict()
        self._fails = 0
        self._open_until = 0.0
        self.calls = 0

    @property
    def available(self) -> bool:
        return bool(self._key)

    def __repr__(self) -> str:  # never show the key
        return f"JevClient(available={self.available}, url={self._url!r})"

    async def many_ops(self, task: str, page_path: Optional[str]) -> float:
        if not self._key:
            raise JevError("jev_no_key")
        if time.monotonic() < self._open_until:
            raise JevError("jev_circuit_open")
        state = f"Task: {task}\nPage kind: {page_path or 'unknown'}"
        if state in self._cache:
            self._cache.move_to_end(state)
            return self._cache[state]
        self.calls += 1
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as c:
                r = await c.post(self._url, headers={"Authorization": f"Bearer {self._key}"},
                                 json={"state": state, "model": "jev-latest", "questions": _JEV_QUESTION})
        except httpx.TimeoutException:
            self._note_failure()
            raise JevError("jev_timeout")
        except Exception:
            self._note_failure()
            raise JevError("jev_unreachable")
        if r.status_code != 200:
            self._note_failure()
            raise JevError(f"jev_http_{r.status_code}")
        try:
            p = r.json()["answers"]["many_ops"]["noul"]
            if isinstance(p, bool) or not isinstance(p, (int, float)) or math.isnan(p) or not (0.0 <= float(p) <= 1.0):
                raise ValueError
            p = float(p)
        except Exception:
            self._note_failure()
            raise JevError("jev_invalid_response")
        self._fails = 0
        self._cache[state] = p
        if len(self._cache) > 256:
            self._cache.popitem(last=False)
        return p

    def _note_failure(self) -> None:
        self._fails += 1
        if self._fails >= CIRCUIT_FAILURES:
            self._open_until = time.monotonic() + CIRCUIT_PAUSE_S
            self._fails = 0


def jev_enabled() -> bool:
    return os.getenv("COMEX_JEV_ROUTER", "0") == "1"


_default_client: Optional[JevClient] = None


def default_client() -> JevClient:
    global _default_client
    if _default_client is None:
        _default_client = JevClient()
    return _default_client


async def route(req: RouteRequest, jev: Optional[JevClient] = None, use_jev: Optional[bool] = None) -> RouteDecision:
    """The whole decision. Jev is consulted only for borderline tasks, only when enabled, and only once."""
    t0 = time.perf_counter()
    decision, borderline = route_deterministic(req)
    if not borderline:
        return decision
    use = jev_enabled() if use_jev is None else use_jev
    if not use:
        return decision.model_copy(update={"source": "fallback", "fallback": "jev_not_enabled",
                                           "latency_ms": round((time.perf_counter() - t0) * 1000, 3)})
    client = jev or default_client()
    try:
        p = await client.many_ops(req.task, req.page_path)
    except JevError as e:
        logger.info("router: jev unavailable (%s); using fallback", e.reason)
        return decision.model_copy(update={"source": "fallback", "fallback": e.reason, "jev_called": e.reason not in ("jev_no_key", "jev_circuit_open"),
                                           "latency_ms": round((time.perf_counter() - t0) * 1000, 3)})
    if p >= JEV_P_PROGRAM:
        out = {"execution": "program", "confidence": round(p, 2), "uncertain": False, "escalate": None}
    elif p <= JEV_P_TYPED:
        out = {"execution": "typed", "confidence": round(1 - p, 2), "uncertain": False, "escalate": None}
    else:
        return decision.model_copy(update={"source": "fallback", "fallback": "jev_low_confidence", "jev_called": True, "jev_p": round(p, 3),
                                           "latency_ms": round((time.perf_counter() - t0) * 1000, 3)})
    return decision.model_copy(update={**out, "source": "jev", "jev_called": True, "jev_p": round(p, 3),
                                       "signals": decision.signals + [f"Jev many_ops = {p:.2f}"],
                                       "latency_ms": round((time.perf_counter() - t0) * 1000, 3)})
