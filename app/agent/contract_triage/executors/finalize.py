"""Shared finalisation logic for the terminal / pause nodes.

Every terminal or human-gate node passes through :func:`finalize`, so this is the
one place the agent scores the outcome, writes the reviewer explanation, and
records its own compact result to SQLite (independent of the API layer). The
intake-review and forward-obligation helpers used by the intake / side-effect
nodes live here too, next to the scoring they feed.
"""

import logging

from .. import agents
from ..io.observability import record_workflow_attribute
from ..models import (
    EndState,
    ForwardObligation,
    GateStatus,
    GateType,
    ObligationType,
    ResolutionAction,
)
from ..models.state import TriageState

_log = logging.getLogger(__name__)

# node-id constant (matches the frontend workflow-graph fixture / GET /api/workflow/graph)
N_START = "START"


# ── scoring / finalisation ──────────────────────────────────────────────────

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
    """Set confidence, recommended action and the reviewer explanation.

    The confidence score is the mean of the per-decision self-reported
    confidences pushed onto ``state.confidence_scores`` by each LLM node
    (classifier + each applicable policy gate + redline advisor). Averaging
    across independent decisions smooths a signal that is poorly calibrated
    in any single call. Presented on the 0-100 scale expected by the UI.
    Emitted as an OTEL span attribute so it lands as trace metadata in
    Langfuse.

    Every terminal/pause node passes through here, so this is also where the
    agent *itself* records its outcome to SQLite (``db.save_outcome``) — the
    graph writes its own result, independent of the API layer.
    """
    if state.end_state is None:
        state.end_state = EndState.SIGNED_DESK_EDITS
    state.recommended_action = _RECOMMENDATION.get(state.end_state)
    # A "signed" outcome with policy checks still flagged is NOT a clean approve:
    # the flagged actions are preconditions to signature, so say so instead of
    # recommending signature outright.
    if state.end_state.value.startswith("signed") and state.has_action_required():
        state.recommended_action = (
            "Do not sign yet — clear the flagged policy checks first "
            f"({_flagged_gate_labels(state)}). Complete the required actions, then approve."
        )

    scores = [c.score for c in state.confidence_scores]
    if scores:
        mean = sum(scores) / len(scores)
        state.score = round(mean * 10)  # 0-10 mean → 0-100 percentage
    else:
        state.score = None
    _log.info(
        "confidence: item=%s end_state=%s per_stage=%s mean_of_10=%s score=%s",
        state.item.id,
        state.end_state.value if state.end_state else None,
        [f"{c.stage}={c.score}" for c in state.confidence_scores],
        f"{sum(scores) / len(scores):.2f}" if scores else "None",
        state.score,
    )
    if state.score is not None:
        record_workflow_attribute("triage.confidence", state.score / 100.0)

    state.explanation = await agents.explain(state)
    _persist_outcome(state)


_GATE_LABEL = {
    GateType.PRIVACY: "data protection",
    GateType.STATUTORY: "statutory checks",
    GateType.INSURANCE: "insurance & cover",
    GateType.SECURITY: "information security",
}


def _flagged_gate_labels(state: TriageState) -> str:
    """Human names of the gates that still need action, for the recommendation."""
    labels = [
        _GATE_LABEL.get(g.gate, g.gate.value.replace("_", " "))
        for g in state.gate_checks
        if g.status is GateStatus.ACTION_REQUIRED
    ]
    return ", ".join(dict.fromkeys(labels)) or "policy checks"


def _persist_outcome(state: TriageState) -> None:
    """Write the compact outcome record from within the graph (best-effort)."""
    from ..io import db

    db.save_outcome(
        state.item.id,
        {
            "end_state": state.end_state.value if state.end_state else None,
            "score": state.score,
            "signer": state.signer.value if state.signer else None,
            "gate_count": len(state.gate_checks),
            "blocking": state.has_blocking_gate(),
            "redline_count": len(state.redlines),
            "obligation_count": len(state.forward_obligations),
            "recommended_action": state.recommended_action,
            "interrupt": state.interrupt.reason if state.interrupt else None,
            "trace": state.trace,
        },
    )


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


def _apply_intake_review(state: TriageState, review: "agents.IntakeReview") -> None:
    """Fill or validate the sender's ask (and counterparty) from the document.

    The sender's ask is derived from the paper when the reviewer left it blank,
    and validated against the paper when they supplied one: an unsupported ask is
    corrected to what the document actually says and the discrepancy is logged, so
    a wrong or overreaching intake note never rides through unchecked.
    """
    item = state.item

    if review.counterparty_name and item.counterparty.name in ("", "Unknown"):
        item.counterparty.name = review.counterparty_name

    provided = (item.sender_ask or "").strip()
    derived = (review.senders_ask or "").strip()

    if not provided:
        if derived:
            item.sender_ask = derived
            state.visit("classify", f"Derived the sender's ask from the document: “{derived}”", "info")
        return

    # An ask was supplied (by the reviewer or the ingest reader) — validate it.
    if review.ask_supported:
        state.visit("classify", "Validated the sender's ask against the document.", "info")
        return
    note = review.ask_note or "the document does not support the stated ask"
    if derived:
        item.sender_ask = derived
    state.notes.append(f"ask_validation: {note}")
    state.visit(
        "classify",
        f"Sender's ask did not match the document — corrected. {note}",
        "warning",
    )
