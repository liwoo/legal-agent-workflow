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
    g = await agents.gate_llm(s, gate)
    s.gate_checks = [g] if g else []
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
        base.visit("gather", f"Gathered {len(base.gate_checks)} gate result(s)")
        await ctx.send_message(base)


class GateOutcome(Executor):
    """router: gate_outcome."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("gate_outcome")
        state.route = "blocked" if state.has_blocking_gate() else "clear"
        await ctx.send_message(state)
