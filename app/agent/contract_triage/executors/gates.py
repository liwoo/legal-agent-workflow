"""Policy-gate nodes — the validator fan-out → gather → outcome.

``FanOut`` dispatches the three policy validators (privacy / statutory /
insurance) to run in parallel; each returns one ``GateCheck`` on a deep copy of
the state; ``Gather`` joins them and ``GateOutcome`` short-circuits to the human
gate on any blocker.
"""

from agent_framework import Executor, WorkflowContext, handler

from .. import agents
from ..models import GateType
from ..models.state import TriageState


class FanOut(Executor):
    """fan-out: dispatch validators."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("fanout", "Dispatching policy validators")
        await ctx.send_message(state)


async def _run_gate(state: TriageState, gate: GateType, node: str,
                    ctx: WorkflowContext[TriageState]) -> None:
    """Shared validator body: the LLM's verdict for one policy gate."""
    s = state.model_copy(deep=True)
    g, confidence = await agents.gate_llm(s, gate)
    s.gate_checks = [g] if g else []
    # Drop this gate's confidence in the transient carrier; ``Gather`` merges
    # all branches' entries into ``confidence_scores`` and clears the carrier.
    # A skipped gate (gate doesn't apply) yields no confidence — nothing to
    # record.
    s.gate_confidences = [confidence] if confidence else []
    s.visit(node)
    await ctx.send_message(s)


class ValidatorDPA(Executor):
    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        await _run_gate(state, GateType.PRIVACY, "dpa", ctx)


class ValidatorStatutory(Executor):
    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        await _run_gate(state, GateType.STATUTORY, "statutory", ctx)


class ValidatorFinance(Executor):
    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        await _run_gate(state, GateType.INSURANCE, "finance", ctx)


class Gather(Executor):
    """reducer: join all validators; short-circuit on any blocker."""

    @handler
    async def run(self, items: list[TriageState], ctx: WorkflowContext[TriageState]) -> None:
        base = items[0]
        base.gate_checks = [g for it in items for g in it.gate_checks]
        # Fold each branch's transient ``gate_confidences`` back into the
        # run-level list — items[0]'s ``confidence_scores`` still carries the
        # shared pre-fanout prefix (the classifier's entry).
        base.confidence_scores.extend(c for it in items for c in it.gate_confidences)
        base.gate_confidences = []
        base.visit("gather", f"Gathered {len(base.gate_checks)} gate result(s)")
        await ctx.send_message(base)


class GateOutcome(Executor):
    """router: gate_outcome."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("gate_outcome")
        state.route = "blocked" if state.has_blocking_gate() else "clear"
        await ctx.send_message(state)
