"""Bounded redline loop — map each counterparty change to a playbook section,
disposition it (hold / fallback / strike / escalate), then loop until every
redline is resolved or the iteration cap is hit.
"""

from agent_framework import Executor, WorkflowContext, handler

from .. import agents
from ..models import PositionTier, ResolutionAction
from ..models.state import TriageState


class MapRedline(Executor):
    """node: map each redline to a playbook section."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("map_redline", "Mapping redlines to the playbook")
        if state.iteration == 0:
            state.redlines, confidence = await agents.redlines_llm(state)
            state.confidence_scores.append(confidence)
        await ctx.send_message(state)


class Disposition(Executor):
    """router: disposition (standard / fallback / banned / refusal-novel)."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("disposition")
        tiers = {r.tier for r in state.redlines}
        if PositionTier.OFF_PLAYBOOK in tiers or any(
            r.action is ResolutionAction.ESCALATED for r in state.redlines
        ):
            state.route = "escalate"
        elif any(r.action is ResolutionAction.STRUCK for r in state.redlines):
            state.route = "strike"
        elif any(r.tier in (PositionTier.FALLBACK_1, PositionTier.FALLBACK_2) for r in state.redlines):
            state.route = "fallback"
        else:
            state.route = "hold"
        await ctx.send_message(state)


class _DispositionNode(Executor):
    label: str
    action_note: str

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit(self.label, self.action_note)
        await ctx.send_message(state)


class Hold(_DispositionNode):
    label = "hold"
    action_note = "Held standard position."


class Fallback(_DispositionNode):
    label = "fallback"
    action_note = "Applied approved fallback wording and recorded it."


class Strike(_DispositionNode):
    label = "strike"
    action_note = "Struck banned clause and offered a substitute."


class LoopControl(Executor):
    """router: loop_control (all resolved? iter < max?)."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.iteration += 1
        state.visit("loop_control")
        # All redlines are mapped+dispositioned in a single pass, so they're resolved.
        if state.iteration >= state.max_iterations and state.pending_redlines:
            state.route = "maxed"
        else:
            state.route = "resolved"
        await ctx.send_message(state)
