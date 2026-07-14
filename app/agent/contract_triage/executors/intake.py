"""Intake & classification nodes — the top of docs/agent-graph.mmd.

Read the PDF, derive any missing intake facts, write the six-axis classification,
then route: back to the sender (more_info / blocked), down the fast path
(our clean template), or into the full policy review.
"""

from agent_framework import Executor, WorkflowContext, handler

from .. import agents
from ..models import PaperSource
from ..models.state import TriageRequest, TriageState
from .finalize import N_START, _apply_intake_review


class Ingest(Executor):
    """Start node — assemble State from the intake fields and read the PDF.

    ``id``, ``date_received`` and ``pdf_path`` are always provided; the document
    is always read. Any intake fact left blank (counterparty, summary, sender's
    ask) is then derived from the PDF text, so a reviewer can triage from the
    document alone.
    """

    @handler
    async def run(self, req: TriageRequest, ctx: WorkflowContext[TriageState]) -> None:
        from ..io.data import item_from_metadata
        from ..io.pdf import derive_intake, read_pdf

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
    """Write the six-axis classification + flags — decided by the LLM."""

    @handler
    async def run(self, state: TriageState, ctx: WorkflowContext[TriageState]) -> None:
        from ..io.data import inherited_flags, prior_contracts

        item = state.item
        inherited = inherited_flags(item.id, item.related_contracts or None)
        prior_ids = item.related_contracts or prior_contracts(item.id)

        cls, flags, review = await agents.classify_llm(item, inherited, prior_ids)
        state.classification = cls
        state.flags = flags
        _apply_intake_review(state, review)
        state.visit(
            "classify",
            f"Classified: {cls.document_family.value} · "
            f"{cls.paper_source.value} · {cls.direction.value}",
        )
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
        from ..models import DocumentFamily

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
        from ..models import DataFlag

        needs_gates = bool(state.data_flags & {DataFlag.PERSONAL_DATA, DataFlag.SPECIAL_CATEGORY,
                                               DataFlag.CROSS_BORDER})
        state.route = "fanout" if needs_gates else "approve"
        await ctx.send_message(state)
