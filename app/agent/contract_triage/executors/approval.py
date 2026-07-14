"""Approval & side-effects — set the signer and provisional outcome, route to
signature, then (the terminal SIGNED node) diarise, record deviations and yield.
"""

from agent_framework import Executor, WorkflowContext, handler
from typing_extensions import Never

from ..models import EndState, PaperSource, ResolutionAction, SignatoryLevel
from ..models.state import TriageState
from .finalize import _forward_obligations, finalize


class Approval(Executor):
    """router: approval — route by value band, set signer + provisional outcome."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("approval")
        cls = state.classification
        state.signer = cls.signatory_level if cls else SignatoryLevel.LEGAL_COUNSEL
        if not state.redlines and cls and cls.paper_source is PaperSource.OURS_CLEAN:
            state.end_state = EndState.SIGNED_NO_EDITS
        elif any(r.action is ResolutionAction.FALLBACK_APPLIED for r in state.redlines):
            state.end_state = EndState.SIGNED_WITH_DEVIATION
        else:
            state.end_state = EndState.SIGNED_DESK_EDITS
        await ctx.send_message(state)


class Execute(Executor):
    """node: route signer → capture signature."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        signer = state.signer.value if state.signer else "legal_counsel"
        state.visit("execute", f"Routed to signer: {signer}", "success")
        await ctx.send_message(state)


class SideEffects(Executor):
    """node (terminal SIGNED): diarise, record deviations, set flags."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[Never, TriageState]) -> None:
        _forward_obligations(state)
        await finalize(state)
        state.visit("side_effects", "Diarised · deviations recorded", "success")
        state.visit("SIGNED", "SIGNED", "success")
        await ctx.yield_output(state)
