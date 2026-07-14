"""Negotiability fork — non-negotiable paper goes to gap analysis (accept/decline
as a business decision); negotiable paper goes into the redline loop.
"""

from agent_framework import Executor, WorkflowContext, handler

from ..models import PaperSource
from ..models.state import TriageState


class Negotiability(Executor):
    """router: non-negotiable paper?"""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("negotiability")
        state.route = "nonneg" if state.classification.paper_source is PaperSource.COUNTERPARTY_FIXED \
            else "negotiable"
        await ctx.send_message(state)


class GapAnalysis(Executor):
    """node: gap analysis vs playbook (non-negotiable paper)."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("gap_analysis", "Gap analysis vs playbook")
        from ..models import DataFlag

        # Non-negotiable + regulated/public body typically trips a refusal point
        # (uncapped liability, governing law, audit rights).
        refusal = DataFlag.REGULATED_COUNTERPARTY in state.data_flags or state.item.counterparty.is_public_body
        state.notes.append("refusal_point_hit" if refusal else "within_playbook")
        state.route = "refusal" if refusal else "ok"
        await ctx.send_message(state)


class GapCheck(Executor):
    """router: refusal point hit?"""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("gap_check")
        state.route = "business_decision" if "refusal_point_hit" in state.notes else "approve"
        await ctx.send_message(state)
