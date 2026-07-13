"""End-to-end routing: one metadata payload + the shared PDF, run to the finish.

Each case pins a full traversal — the terminal end-state *and* which nodes the
run did (and did not) touch — so "this input ends here, not there" is asserted,
not assumed. Classification is driven purely by the intake metadata, so every
branch is reproducible from the text alone.
"""

from __future__ import annotations

from contract_triage.models import EndState

from helpers import triage_and_resume, triage_meta

# ── intake gate: divert before triage ────────────────────────────────────────

def test_no_draft_returns_for_more_info() -> None:
    state = triage_meta(
        summary="Customer email (no draft attached) asking to reduce from 60 to 40 seats mid-term.",
        senders_ask="What are our options?",
    )
    assert state.end_state == EndState.MORE_INFO_NEEDED
    assert state.interrupt.reason == "more_info"
    assert "human_gate" in state.trace
    assert "triage" not in state.trace  # diverted at intake, never triaged


def test_dpia_precondition_blocks_at_intake() -> None:
    state = triage_meta(
        summary="Signed-NDA prospect requesting an order form, 25 seats, Professional tier.",
        senders_ask="Standard order form please.",
        related_contracts=["CR-2026-046"],
    )
    assert state.end_state == EndState.BLOCKED
    assert state.interrupt.reason == "blocked"
    assert "triage" not in state.trace  # blocked before triage


# ── fast path vs full review ─────────────────────────────────────────────────

def test_clean_own_paper_takes_the_fast_path() -> None:
    state = triage_meta(
        summary="Our own standard order form for 40 seats, Professional tier, clean.",
        senders_ask="Standard order form please, ready to go.",
    )
    assert state.end_state == EndState.SIGNED_NO_EDITS
    assert "cheap_guard" in state.trace
    assert "fanout" not in state.trace       # guard cleared it — no policy fan-out
    assert "map_redline" not in state.trace


def test_personal_data_forces_the_gates_off_the_fast_path() -> None:
    state = triage_meta(
        summary="Our own standard order form, 25 seats. Would sync employee personal data into the platform.",
        senders_ask="Standard order form please.",
    )
    # Took the cheap guard, but the guard refused to shortcut and fanned out.
    assert "cheap_guard" in state.trace
    assert "fanout" in state.trace


# ── policy gate blocks ───────────────────────────────────────────────────────

def test_cross_border_no_dpa_blocks_at_the_gate() -> None:
    state = triage_meta(
        summary="Vendor's own paper: order form for an AI tool. US-hosted processing of personal data; no DPA attached.",
        senders_ask="Approve this week?",
    )
    assert state.end_state == EndState.BLOCKED
    assert state.interrupt.reason == "blocked"
    assert "gate_outcome" in state.trace
    assert "negotiability" not in state.trace  # short-circuited at the gate


# ── non-negotiable paper fork ────────────────────────────────────────────────

def test_public_body_tender_becomes_a_business_decision() -> None:
    state = triage_meta(
        summary="Council's invitation-to-tender pack: mandatory contract terms, a no-negotiation notice.",
        senders_ask="Confirm we can accept their terms as-is.",
    )
    assert state.end_state == EndState.BUSINESS_DECISION
    assert state.interrupt.reason == "business_decision"
    assert "gap_analysis" in state.trace
    assert "map_redline" not in state.trace  # non-negotiable — no redline loop


def test_non_negotiable_but_within_playbook_signs() -> None:
    state = triage_meta(
        summary="Vendor's online terms of service for a small utility tool. No personal data.",
        senders_ask="Can we approve?",
    )
    assert state.end_state == EndState.SIGNED_DESK_EDITS
    assert "gap_check" in state.trace
    assert "human_gate" not in state.trace  # cleared without escalation


# ── redline loop dispositions ────────────────────────────────────────────────

def test_off_playbook_redline_escalates() -> None:
    state = triage_meta(
        summary="Agency's SOW draft, autumn campaign, includes AI-generated imagery not contemplated by the framework IP clause.",
        senders_ask="Same as the last two SOWs.",
    )
    assert state.end_state == EndState.ESCALATED
    assert state.interrupt.reason == "escalate"
    assert "disposition" in state.trace
    assert "human_gate" in state.trace


def test_banned_clause_is_struck_then_signed() -> None:
    state = triage_meta(
        summary="Our order form + MSA returned with tracked changes on indemnity, liability and payment terms.",
        senders_ask="How bad are the changes?",
    )
    assert "strike" in state.trace
    assert state.end_state == EndState.SIGNED_WITH_DEVIATION
    assert "SIGNED" in state.trace


def test_fallback_wording_records_a_deviation() -> None:
    state = triage_meta(
        summary="Our order form returned with tracked changes on the liability cap and payment terms (net 60).",
        senders_ask="How bad are the changes?",
    )
    assert "fallback" in state.trace
    assert state.end_state == EndState.SIGNED_WITH_DEVIATION


def test_standard_position_is_held() -> None:
    state = triage_meta(
        summary="Our MSA returned with tracked changes on the renewal uplift figure only.",
        senders_ask="Fine to proceed?",
    )
    assert "hold" in state.trace
    assert state.end_state == EndState.SIGNED_DESK_EDITS


# ── human-gate resume terminals ──────────────────────────────────────────────

_TENDER = dict(
    summary="Council's invitation-to-tender pack: mandatory contract terms, a no-negotiation notice.",
    senders_ask="Confirm we can accept their terms as-is.",
)


def test_resume_declined_walks_away() -> None:
    state = triage_and_resume("declined", **_TENDER)
    assert state.end_state == EndState.DECLINED
    assert "DECLINED" in state.trace


def test_resume_escalated_ends_escalated() -> None:
    state = triage_and_resume("escalated", **_TENDER)
    assert state.end_state == EndState.ESCALATED
    assert "ESCALATED" in state.trace


def test_resume_resolved_signs() -> None:
    state = triage_and_resume("resolved", **_TENDER)
    assert state.end_state in {
        EndState.SIGNED_NO_EDITS,
        EndState.SIGNED_DESK_EDITS,
        EndState.SIGNED_WITH_DEVIATION,
    }
    assert "SIGNED" in state.trace
