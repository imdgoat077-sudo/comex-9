"""
Action requests in multi-agent mode ("book 2 tickets at VR Mall") go to one agent with an action budget instead of
3-action researchers plus a follow-up; numbers must come from pages; contradictions with the chat are reported; a
named stopping point (sign-in, payment) ends the task instead of a refusal.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from nervous.action_policy import ServerTabLeaseRegistry, ServerTabTargetRegistry
from services.orchestrator import (ACTION_MAX_TOOL_CALLS, GROUNDING_RULE, MultiAgentOrchestrator, OrchestratorTask,
                                   RunStatus, WorkerResult, _parse_decomposition_response, build_action_brief,
                                   build_worker_brief, decompose_request_via_llm, synthesize_final_answer)
from services.tool_service import ComexToolService


def _orchestrator(**kwargs) -> MultiAgentOrchestrator:
    return MultiAgentOrchestrator(tool_service=MagicMock(spec=ComexToolService), lease_registry=ServerTabLeaseRegistry(),
                                  target_registry=ServerTabTargetRegistry(), **kwargs)


def test_planner_direct_action_means_no_research_tasks():
    plan = _parse_decomposition_response(json.dumps({
        "subtasks": [], "follow_up_action": None,
        "direct_action": "Book 2 tickets for Jailer 2 at PVR VR Mall; stop when it asks for login",
        "start_url": "https://in.bookmyshow.com/movies/chennai/jailer-2/ET00518674"}), 4)
    assert plan.tasks == [] and "VR Mall" in plan.direct_action
    assert plan.start_url == "https://in.bookmyshow.com/movies/chennai/jailer-2/ET00518674"


def test_an_unsafe_start_url_is_dropped_not_the_action():
    plan = _parse_decomposition_response(json.dumps({"subtasks": [], "direct_action": "Add it to the cart",
                                                     "start_url": "javascript:alert(1)"}), 4)
    assert plan.direct_action == "Add it to the cart" and plan.start_url is None


def test_research_requests_still_plan_subtasks():
    plan = _parse_decomposition_response(json.dumps({"subtasks": [{"id": "a", "objective": "Find headphones"}],
                                                     "direct_action": None}), 4)
    assert plan.direct_action is None and [t.id for t in plan.tasks] == ["a"]


async def test_decompose_passes_a_direct_action_through():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"subtasks": [], "direct_action": "Write a note about Python"}'))
    plan = await decompose_request_via_llm("go to a notes app and write a note about python", llm)
    assert plan.direct_action == "Write a note about Python" and plan.tasks == []


async def test_a_direct_action_runs_one_agent_with_the_action_budget():
    briefs, seen = [], {}

    def factory(brief):
        briefs.append(brief)
        async def fn(ctx, svc):
            seen.update(ctx.metadata)
            return WorkerResult(findings="Selected 2 seats (F7, F8) at ₹190 each; stopped at the sign-in screen.", success=True)
        return fn

    orch = _orchestrator(worker_factory=factory)
    run = orch.create_action_run("yes book 2 tickets in vr mall and stop when it asks for my login",
                                 "Book 2 tickets at PVR VR Mall; stop at login", "https://in.bookmyshow.com/x",
                                 context="User: find Jailer 2 shows near Anna Nagar\nComex: PVR VR Mall has shows.")
    task = run.tasks["action"]
    assert len(run.tasks) == 1 and task.approved and task.sensitive_action and task.url == "https://in.bookmyshow.com/x"
    res = await orch.execute_run(run)
    assert run.status == RunStatus.COMPLETED and "stopped at the sign-in screen" in res.final_answer
    assert seen["kind"] == "action" and seen["max_tool_calls"] == ACTION_MAX_TOOL_CALLS
    brief = briefs[0]
    assert "YOUR TASK (asked for by the user): Book 2 tickets at PVR VR Mall" in brief
    assert "PVR VR Mall has shows" in brief and "[UNTRUSTED DATA START]" in brief
    assert "do not refuse" in brief and "'not shown'" in brief and "never proceed to checkout" in brief


async def test_the_endpoint_routes_a_direct_action_plan_to_one_agent():
    import agent_service as A
    from services.orchestrator import RunPlan
    orch = _orchestrator(worker_factory=lambda brief: AsyncMock())
    req = A.OrchestrateRequest(user_request="book 2 tickets at vr mall")
    with patch.object(A, "_get_orchestrator", return_value=orch), \
         patch("services.orchestrator.decompose_request_via_llm",
               AsyncMock(return_value=RunPlan(tasks=[], direct_action="Book 2 tickets at VR Mall"))):
        run = await A._create_orchestration_run(req)
    assert list(run.tasks) == ["action"] and run.follow_up_action is None


async def test_the_worker_uses_the_budget_and_intent_the_task_carries():
    import agent_service as A
    calls = {}

    async def fake_loop(**kw):
        calls.update(kw)
        return "done"

    ctx = MagicMock(worker_id="w1", target_tab_id="t1", lease=None, deadline_mono=None,
                    metadata={"kind": "action", "max_tool_calls": 25})
    with patch.object(A, "execute_agent_loop", side_effect=fake_loop):
        await A.make_worker_task_fn("brief")(ctx, MagicMock())
    assert calls["max_tool_calls"] == 25 and calls["intent"] == "VISIBLE_BROWSER_TASK"
    ctx.metadata = {}
    with patch.object(A, "execute_agent_loop", side_effect=fake_loop):
        await A.make_worker_task_fn("brief")(ctx, MagicMock())
    assert calls["max_tool_calls"] == A.WORKER_MAX_TOOL_CALLS and calls["intent"] == "RESEARCH"


def test_research_and_helper_briefs_carry_the_grounding_rule():
    t = OrchestratorTask(id="a", description="Ticket prices at PVR VR Mall")
    assert GROUNDING_RULE in build_worker_brief("jailer 2 tickets", t, [t])
    assert "contradicts something said earlier" in build_worker_brief("jailer 2 tickets", t, [t])
    assert "not shown" in build_action_brief("x", "add to cart", "conclusion")


async def test_synthesis_sees_the_conversation_and_the_rules_on_numbers_and_contradictions():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="ok"))
    orch = _orchestrator()
    run = orch.create_run("find shows", [OrchestratorTask(id="a", description="shows"), OrchestratorTask(id="b", description="prices")],
                          context="Comex: VR Mall has morning shows from 09:00.")
    await synthesize_final_answer("find shows", run, llm)
    system, user = (m["content"] for m in llm.ainvoke.call_args[0][0])
    assert "VR Mall has morning shows" in user and "[UNTRUSTED DATA START]" in user
    assert "not shown" in system and "contradicts what the earlier conversation said" in system


def test_the_single_agent_prompt_has_the_same_rules():
    import agent_service as A
    p = A.SYSTEM_PROMPT
    assert "Never silently replace the earlier claim" in p
    assert 'say "not shown"' in p
    assert "Do not refuse or say an assistant cannot do this" in p
