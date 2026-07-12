"""Per-node tests: feed each router an entry state and assert the branch it sets.

Every router in the graph sets ``state.route``; the switch-case edges in
``workflow.py`` turn that into the next hop. Here we invoke each node in
isolation and pin the ``route`` it produces for a given entry state — so a
routing change is caught at the node, not just end-to-end.
"""

from __future__ import annotations

from contract_triage import executors as X
from contract_triage.executors import HumanDecision
from contract_triage.models import (
    EndState,
    GateCheck,
    GateStatus,
    GateType,
    PaperSource,
    PlaybookSection,
    PositionTier,
    Redline,
    ResolutionAction,
)
from contract_triage.state import TriageState

from helpers import classified, emitted, make_item, run_node

# routing inputs (metadata text → deterministic classification)
FAST = dict(summary="Our own standard order form for 40 seats, Professional tier, clean.",
            senders_ask="Standard order form please, ready to go.")
DATA = dict(summary="Our own standard order form, 25 seats. Would sync employee personal data into the platform.",
            senders_ask="Standard order form please.")
NO_DRAFT = dict(summary="Customer email (no draft attached) asking to reduce from 60 to 40 seats mid-term.",
                senders_ask="What are our options?")
TENDER = dict(summary="Council's invitation-to-tender pack: mandatory contract terms, a no-negotiation notice.",
              senders_ask="Confirm we can accept their terms as-is.")
ONLINE = dict(summary="Vendor's online terms of service for a small utility tool. No personal data.",
              senders_ask="Can we approve?")


def _redline(tier: PositionTier, action: ResolutionAction) -> Redline:
    return Redline(clause_ref="X", description="x", playbook_section=PlaybookSection.LIABILITY_CAP,
                   tier=tier, action=action)


# ── intake_gate ──────────────────────────────────────────────────────────────

def test_intake_gate_no_draft_needs_more_info() -> None:
    assert emitted(run_node(X.IntakeGate(id="intake_gate"), classified(**NO_DRAFT))).route == "more_info"


def test_intake_gate_dpia_precondition_blocks() -> None:
    state = classified(summary="Signed-NDA prospect requesting an order form, 25 seats.",
                       related_contracts=["CR-2026-046"])
    assert emitted(run_node(X.IntakeGate(id="intake_gate"), state)).route == "blocked"


def test_intake_gate_clean_intake_proceeds() -> None:
    assert emitted(run_node(X.IntakeGate(id="intake_gate"), classified(**FAST))).route == "ok"


# ── triage (fast path vs full review) ────────────────────────────────────────

def test_triage_clean_own_paper_takes_guard() -> None:
    assert emitted(run_node(X.TriageRouter(id="triage"), classified(**FAST))).route == "guard"


def test_triage_counterparty_paper_fans_out() -> None:
    # BASE_META is a counterparty NDA.
    assert emitted(run_node(X.TriageRouter(id="triage"), classified())).route == "fanout"


# ── guard_check ──────────────────────────────────────────────────────────────

def test_guard_check_clean_approves() -> None:
    assert emitted(run_node(X.GuardCheck(id="guard_check"), classified(**FAST))).route == "approve"


def test_guard_check_personal_data_still_gates() -> None:
    assert emitted(run_node(X.GuardCheck(id="guard_check"), classified(**DATA))).route == "fanout"


# ── gate_outcome ─────────────────────────────────────────────────────────────

def test_gate_outcome_blocks_on_blocking_gate() -> None:
    state = classified()
    state.gate_checks = [GateCheck(gate=GateType.PRIVACY, status=GateStatus.BLOCKED)]
    assert emitted(run_node(X.GateOutcome(id="gate_outcome"), state)).route == "blocked"


def test_gate_outcome_clears_when_no_blocker() -> None:
    state = classified()
    state.gate_checks = [GateCheck(gate=GateType.STATUTORY, status=GateStatus.ACTION_REQUIRED)]
    assert emitted(run_node(X.GateOutcome(id="gate_outcome"), state)).route == "clear"


# ── negotiability ────────────────────────────────────────────────────────────

def test_negotiability_fixed_paper_is_nonneg() -> None:
    assert emitted(run_node(X.Negotiability(id="negotiability"), classified(**TENDER))).route == "nonneg"


def test_negotiability_negotiable_paper() -> None:
    assert emitted(run_node(X.Negotiability(id="negotiability"), classified(**FAST))).route == "negotiable"


# ── gap_analysis → gap_check ─────────────────────────────────────────────────

def test_gap_check_refusal_point_is_business_decision() -> None:
    after_gap = emitted(run_node(X.GapAnalysis(id="gap_analysis"), classified(**TENDER)))
    assert "refusal_point_hit" in after_gap.notes
    assert emitted(run_node(X.GapCheck(id="gap_check"), after_gap)).route == "business_decision"


def test_gap_check_within_playbook_approves() -> None:
    after_gap = emitted(run_node(X.GapAnalysis(id="gap_analysis"), classified(**ONLINE)))
    assert "within_playbook" in after_gap.notes
    assert emitted(run_node(X.GapCheck(id="gap_check"), after_gap)).route == "approve"


# ── disposition (four-way) ───────────────────────────────────────────────────

def test_disposition_off_playbook_escalates() -> None:
    state = classified()
    state.redlines = [_redline(PositionTier.OFF_PLAYBOOK, ResolutionAction.ESCALATED)]
    assert emitted(run_node(X.Disposition(id="disposition"), state)).route == "escalate"


def test_disposition_banned_clause_strikes() -> None:
    state = classified()
    state.redlines = [_redline(PositionTier.REFUSAL_POINT, ResolutionAction.STRUCK)]
    assert emitted(run_node(X.Disposition(id="disposition"), state)).route == "strike"


def test_disposition_fallback_tier() -> None:
    state = classified()
    state.redlines = [_redline(PositionTier.FALLBACK_1, ResolutionAction.FALLBACK_APPLIED)]
    assert emitted(run_node(X.Disposition(id="disposition"), state)).route == "fallback"


def test_disposition_standard_holds() -> None:
    state = classified()
    state.redlines = [_redline(PositionTier.STANDARD, ResolutionAction.HELD)]
    assert emitted(run_node(X.Disposition(id="disposition"), state)).route == "hold"


# ── loop_control (bounded redline loop) ──────────────────────────────────────

def test_loop_control_resolves_in_one_pass() -> None:
    assert emitted(run_node(X.LoopControl(id="loop_control"), classified())).route == "resolved"


def test_loop_control_maxes_out_with_pending_redlines() -> None:
    state = classified()
    state.iteration = state.max_iterations
    state.pending_redlines = [{"clause": "liability"}]
    assert emitted(run_node(X.LoopControl(id="loop_control"), state)).route == "maxed"


# ── approval (provisional outcome by paper/redlines) ─────────────────────────

def test_approval_clean_paper_signs_no_edits() -> None:
    state = classified(**FAST)  # OURS_CLEAN, no redlines
    assert emitted(run_node(X.Approval(id="approval"), state)).end_state == EndState.SIGNED_NO_EDITS


def test_approval_fallback_records_deviation() -> None:
    state = classified()
    state.redlines = [_redline(PositionTier.FALLBACK_1, ResolutionAction.FALLBACK_APPLIED)]
    assert emitted(run_node(X.Approval(id="approval"), state)).end_state == EndState.SIGNED_WITH_DEVIATION


def test_approval_desk_edits_default() -> None:
    state = classified()
    state.redlines = [_redline(PositionTier.STANDARD, ResolutionAction.HELD)]
    assert emitted(run_node(X.Approval(id="approval"), state)).end_state == EndState.SIGNED_DESK_EDITS


# ── human_gate interrupt + resume routing ────────────────────────────────────

def test_human_gate_interrupts_and_sets_end_state() -> None:
    state = classified(**TENDER)
    state.route = "business_decision"
    ctx = run_node(X.HumanGate(id="human_gate"), state)
    assert ctx.requests, "human gate should raise a request_info interrupt"
    assert ctx.requests[-1].end_state == EndState.BUSINESS_DECISION
    assert ctx.requests[-1].interrupt is not None


def _resume(decision: str) -> str:
    node = X.HumanGate(id="human_gate")
    ctx = FakeResume()
    import asyncio

    original = classified(**TENDER)
    asyncio.run(node.resume(original, HumanDecision(decision=decision), ctx))
    return ctx.messages[-1].route


class FakeResume:
    def __init__(self) -> None:
        self.messages: list[TriageState] = []

    async def send_message(self, message: TriageState, **_: object) -> None:
        self.messages.append(message)


def test_human_gate_resume_declined() -> None:
    assert _resume("declined") == "declined"


def test_human_gate_resume_escalated() -> None:
    assert _resume("escalated") == "escalated"


def test_human_gate_resume_resolved() -> None:
    assert _resume("resolved") == "resolved"
