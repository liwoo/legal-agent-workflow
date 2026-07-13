"""Graph nodes — one Executor per node in ../../agent-graph.mmd.

Message flowing between nodes = ``TriageState`` (the shared state). Routers set
``state.route`` and forward; switch-case edges (wired in workflow.py) branch on
it. The human_gate is a real Agent-Framework ``request_info`` interrupt, so it
pauses the run and resumes via ``workflow.run(responses=...)`` — surfaced in
DevUI and driven by the FastAPI ``/resolve`` endpoint.
"""

from agent_framework import Executor, WorkflowContext, handler, response_handler
from pydantic import BaseModel
from typing_extensions import Never

from . import agents, heuristics
from .models import (
    EndState,
    ForwardObligation,
    GateStatus,
    ObligationType,
    PaperSource,
    PositionTier,
    ResolutionAction,
    SignatoryLevel,
)
from .state import Interrupt, TriageRequest, TriageState

# node-id constants (match the frontend workflow-graph fixture / GET /api/workflow/graph)
N_START = "START"


# ── scoring / finalisation ──────────────────────────────────────────────────

_SCORE = {
    EndState.SIGNED_NO_EDITS: 95,
    EndState.SIGNED_DESK_EDITS: 85,
    EndState.SIGNED_WITH_DEVIATION: 62,
    EndState.MORE_INFO_NEEDED: 30,
    EndState.BLOCKED: 35,
    EndState.BUSINESS_DECISION: 45,
    EndState.ESCALATED: 50,
    EndState.DECLINED: 40,
}

_RECOMMENDATION = {
    EndState.SIGNED_NO_EDITS: "Auto-approve and spot-check — clean own-paper template.",
    EndState.SIGNED_DESK_EDITS: "Approve at the desk and route for signature.",
    EndState.SIGNED_WITH_DEVIATION: "Approve with the recorded fallback deviation; log it (Ch.10).",
    EndState.MORE_INFO_NEEDED: "Return to sender — the draft/detail needed to review is missing.",
    EndState.BLOCKED: "Clear the blocking precondition before proceeding.",
    EndState.BUSINESS_DECISION: "Business decision: accept the non-negotiable terms as-is, or decline.",
    EndState.ESCALATED: "Escalate to Legal Director (Ch.10, 2-business-day SLA).",
    EndState.DECLINED: "Walk away — refusal point not conceded.",
}


async def finalize(state: TriageState) -> None:
    """Set score, recommended action and the reviewer explanation."""
    if state.end_state is None:
        state.end_state = EndState.SIGNED_DESK_EDITS
    state.recommended_action = _RECOMMENDATION.get(state.end_state)
    base = _SCORE.get(state.end_state, 50)
    if state.has_action_required() and base > 60:
        base -= 8
    state.score = max(0, min(100, base))
    state.explanation = await agents.explain(state)


def _forward_obligations(state: TriageState) -> None:
    cls = state.classification
    if not cls:
        return
    if "renewal" in cls.document_family.value or state.end_state and "signed" in state.end_state.value:
        if any(r.action is ResolutionAction.FALLBACK_APPLIED for r in state.redlines):
            state.forward_obligations.append(
                ForwardObligation(type=ObligationType.RECORD_DEVIATION,
                                  note="Record the fallback concession in the deviations log (Ch.10 → Ch.12).")
            )
    if "renewal" in cls.document_family.value:
        state.forward_obligations.append(
            ForwardObligation(type=ObligationType.DIARISE_RENEWAL_NOTICE,
                              note="Diarise the renewal-notice window (Playbook §6.1).")
        )


# ── intake & classification ─────────────────────────────────────────────────


class Ingest(Executor):
    """Start node — assemble State from the intake fields and read the PDF.

    ``id``, ``date_received`` and ``pdf_path`` are always provided; the document
    is always read. Any intake fact left blank (counterparty, summary, sender's
    ask) is then derived from the PDF text, so a reviewer can triage from the
    document alone.
    """

    @handler
    async def run(self, req: TriageRequest, ctx: WorkflowContext[TriageState]) -> None:
        from .data import item_from_metadata
        from .pdf import derive_intake, read_pdf

        item = item_from_metadata(
            {
                "id": req.id or "AD-HOC",
                "name": req.name,
                "counterparty": req.counterparty,
                "summary": req.summary,
                "senders_ask": req.senders_ask,
                "received_from": req.received_from,
                "date_received": req.date_received,
                "related_contracts": [
                    s.strip() for s in req.related_contracts.split(",") if s.strip()
                ],
            },
            req.pdf_path or None,
        )

        state = TriageState(item=item)
        state.visit(N_START)

        extract = read_pdf(item.pdf_path) if item.pdf_path else None
        if extract and extract.ok:
            item.document_text = extract.text
            state.visit(
                "ingest",
                f"Read PDF {item.pdf_path} ({extract.pages} page(s), {extract.char_count} chars)",
                "success",
            )
        else:
            item.document_text = ""
            reason = extract.error if extract else "no pdf_path provided"
            state.visit("ingest", f"PDF unreadable: {reason}", "warning")

        # Derive any intake fact the reviewer left blank from the document.
        derived = derive_intake(item.document_text)
        filled: list[str] = []
        if not item.what_arrived and derived.what_arrived:
            item.what_arrived = derived.what_arrived
            filled.append("summary")
        if not item.sender_ask and derived.sender_ask:
            item.sender_ask = derived.sender_ask
            filled.append("sender's ask")
        if item.counterparty.name in ("", "Unknown") and derived.counterparty:
            item.counterparty.name = derived.counterparty
            filled.append("counterparty")
        if filled:
            state.visit("ingest", f"Derived from PDF: {', '.join(filled)}", "info")

        await ctx.send_message(state)


class Classify(Executor):
    """Write the six-axis classification + flags."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        cls, flags = heuristics.classify(state.item)
        state.classification = cls
        state.flags = flags
        state.visit("classify",
                    f"Classified: {cls.document_family.value} · {cls.paper_source.value} · {cls.direction.value}")
        await ctx.send_message(state)


class IntakeGate(Executor):
    """router: draft? prior_file? blocker?"""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("intake_gate")
        if state.classification.paper_source is PaperSource.NO_DRAFT or "no_draft" in state.flags:
            state.route = "more_info"
        elif any(f == "dpia_required_before_order_form" for f in state.flags):
            state.route = "blocked"
        else:
            state.route = "ok"
        await ctx.send_message(state)


class TriageRouter(Executor):
    """router: our template & no redlines? (fast path vs full review)"""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("triage")
        cls = state.classification
        from .models import DocumentFamily

        redlined = cls.paper_source in (PaperSource.OURS_REDLINED, PaperSource.COUNTERPARTY,
                                        PaperSource.COUNTERPARTY_FIXED)
        in_scope_addon = (
            cls.document_family in (DocumentFamily.SOW, DocumentFamily.AMENDMENT)
            and "out_of_scope" not in state.flags
        )
        if cls.paper_source is PaperSource.OURS_CLEAN and not redlined:
            state.route = "guard"
        elif in_scope_addon and cls.paper_source is not PaperSource.COUNTERPARTY:
            state.route = "guard"
        else:
            state.route = "fanout"
        await ctx.send_message(state)


class CheapGuard(Executor):
    """node: lightweight validation of a clean own-paper template."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("cheap_guard", "Lightweight guard check")
        await ctx.send_message(state)


class GuardCheck(Executor):
    """router: guard clean?"""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("guard_check")
        # Personal data or systems access even on our clean paper still needs the gates.
        from .models import DataFlag

        needs_gates = bool(state.data_flags & {DataFlag.PERSONAL_DATA, DataFlag.SPECIAL_CATEGORY,
                                               DataFlag.CROSS_BORDER})
        state.route = "fanout" if needs_gates else "approve"
        await ctx.send_message(state)


# ── policy gates: fan-out → gather ──────────────────────────────────────────


class FanOut(Executor):
    """fan-out: dispatch validators."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("fanout", "Dispatching policy validators")
        await ctx.send_message(state)


class ValidatorDPA(Executor):
    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        s = state.model_copy(deep=True)
        g = heuristics.gate_privacy(s)
        s.gate_checks = [g] if g else []
        s.visit("dpa")
        await ctx.send_message(s)


class ValidatorStatutory(Executor):
    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        s = state.model_copy(deep=True)
        g = heuristics.gate_statutory(s)
        s.gate_checks = [g] if g else []
        s.visit("statutory")
        await ctx.send_message(s)


class ValidatorFinance(Executor):
    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        s = state.model_copy(deep=True)
        g = heuristics.gate_finance(s)
        s.gate_checks = [g] if g else []
        s.visit("finance")
        await ctx.send_message(s)


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


# ── negotiability fork ──────────────────────────────────────────────────────


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
        from .models import DataFlag

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


# ── redline loop ────────────────────────────────────────────────────────────


class MapRedline(Executor):
    """node: map each redline to a playbook section."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        state.visit("map_redline", "Mapping redlines to the playbook")
        if state.iteration == 0:
            state.redlines = heuristics.extract_redlines(state)
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


# ── approval & side-effects ─────────────────────────────────────────────────


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


# ── human-in-the-loop: single re-entrant interrupt ──────────────────────────


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
