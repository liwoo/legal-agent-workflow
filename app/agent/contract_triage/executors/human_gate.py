"""Human-in-the-loop — a single re-entrant interrupt plus the two terminal
outcomes it can route to (DECLINED / ESCALATED).

``HumanGate`` is a real Agent-Framework ``request_info`` interrupt reachable from
every escalation point: it pauses the run and resumes via
``workflow.run(responses=...)`` — surfaced in DevUI and driven by the FastAPI
``/resolve`` endpoint.
"""

from agent_framework import Executor, WorkflowContext, handler, response_handler
from pydantic import BaseModel
from typing_extensions import Never

from ..models import EndState
from ..models.state import Interrupt, TriageState
from .finalize import finalize


class HumanDecision(BaseModel):
    """The reviewer's response that resumes a paused workflow."""

    decision: str = "resolved"  # resolved | declined | escalated
    note: str | None = None


_REASON = {
    "more_info": ("more_info", EndState.MORE_INFO_NEEDED, "Sender", None),
    "blocked": ("blocked", EndState.BLOCKED, "Data Protection / Finance", None),
    "escalate": ("escalate", EndState.ESCALATED, "Legal Director", "2 business days"),
    "maxed": ("escalate", EndState.ESCALATED, "Legal Director", "2 business days"),
    "business_decision": ("business_decision", EndState.BUSINESS_DECISION, "COO", None),
}


class HumanGate(Executor):
    """interrupt: human_gate — pause, await a reviewer decision, then resume."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState, TriageState]) -> None:
        reason, end_state, owner, sla = _REASON.get(
            state.route or "escalate", _REASON["escalate"]
        )
        state.end_state = end_state
        state.interrupt = Interrupt(reason=reason, owner=owner, sla=sla)
        await finalize(state)
        state.visit("human_gate", f"Paused for human review ({reason})", "warning")
        # Real Agent-Framework interrupt: pauses the run until a response arrives.
        await ctx.request_info(request_data=state, response_type=HumanDecision)

    @response_handler
    async def resume(
        self, original: TriageState, decision: HumanDecision, ctx: WorkflowContext[TriageState]
    ) -> None:
        state = original
        state.notes.append(f"human:{decision.decision}" + (f" — {decision.note}" if decision.note else ""))
        if decision.decision == "declined":
            state.route = "declined"
        elif decision.decision == "escalated":
            state.route = "escalated"
        else:
            state.route = "resolved"
        state.visit("human_gate", f"Reviewer decision: {decision.decision}", "info")
        await ctx.send_message(state)


class Declined(Executor):
    """terminal: END DECLINED."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[Never, TriageState]) -> None:
        state.end_state = EndState.DECLINED
        state.interrupt = None
        await finalize(state)
        state.visit("DECLINED", "DECLINED", "critical")
        await ctx.yield_output(state)


class Escalated(Executor):
    """terminal: END ESCALATED (SLA breach / reviewer escalation)."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[Never, TriageState]) -> None:
        state.end_state = EndState.ESCALATED
        await finalize(state)
        state.visit("ESCALATED", "ESCALATED", "warning")
        await ctx.yield_output(state)
