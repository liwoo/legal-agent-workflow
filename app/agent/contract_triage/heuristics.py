"""Deterministic classification + playbook judgment.

This is the offline brain: keyword/rule logic grounded in the corpus, the
Playbook ladder and the POL-* gates. It lets the whole graph run with no LLM
(demo mode). When an LLM chat client is configured, ``agents.py`` refines these
first-pass results — but the graph is always runnable and deterministic without
one.
"""

from __future__ import annotations

import re

from .data import inherited_flags, prior_contracts
from .models import (
    DataFlag,
    Direction,
    DocumentFamily,
    GateCheck,
    GateStatus,
    GateType,
    InboxItem,
    IntakeClassification,
    PaperSource,
    PlaybookSection,
    PositionTier,
    Redline,
    ResolutionAction,
    SignatoryLevel,
)


def _text(item: InboxItem) -> str:
    return f"{item.what_arrived} {item.sender_ask}".lower()


# ── Classification ──────────────────────────────────────────────────────────


def _family(t: str) -> DocumentFamily:
    if "sow" in t:
        return DocumentFamily.SOW
    if "tender" in t or "invitation-to-tender" in t:
        return DocumentFamily.TENDER_TERMS
    if "nda" in t:
        return DocumentFamily.MUTUAL_NDA
    if "amendment" in t or "no draft" in t or "reduce from" in t:
        return DocumentFamily.AMENDMENT
    if "order form" in t and "dpa" in t:
        return DocumentFamily.ORDER_FORM
    if "renewal" in t and ("supplier" in t or "services agreement" in t):
        return DocumentFamily.SUPPLIER_RENEWAL
    if "renewal" in t:
        return DocumentFamily.ORDER_FORM_RENEWAL
    if "order form" in t:
        return DocumentFamily.ORDER_FORM
    if "terms of service" in t or "online terms" in t or "supplier" in t or "tool" in t:
        return DocumentFamily.SUPPLIER_AGREEMENT
    return DocumentFamily.OTHER


def _paper_source(t: str) -> PaperSource:
    if "no draft" in t or "email (no draft" in t or ("email" in t and "no draft" in t):
        return PaperSource.NO_DRAFT
    if "tender" in t or "no-negotiation" in t or "online terms" in t or "terms of service" in t:
        return PaperSource.COUNTERPARTY_FIXED
    if "tracked changes" in t or ("our" in t and "redline" in t) or "returned our" in t:
        return PaperSource.OURS_REDLINED
    if "comment bubble" in t or "one visible comment" in t:
        return PaperSource.OURS_REDLINED
    if "our own order form" in t or "our order form" in t or "standard order form" in t:
        return PaperSource.OURS_CLEAN
    if "their version" in t or "counterparty's own" in t or "consortium's" in t or "supplier's" in t:
        return PaperSource.COUNTERPARTY
    return PaperSource.COUNTERPARTY


def _direction(t: str) -> Direction:
    buy_signals = ("supplier", "agency", "qa services", "services agreement", "tool", "vendor's")
    if any(s in t for s in buy_signals):
        return Direction.CUSTOMER
    return Direction.VENDOR


def _data_flags(item: InboxItem, t: str) -> set[DataFlag]:
    flags: set[DataFlag] = set()
    if any(k in t for k in ("personal data", "employee", "verification", "customers", "names", "emails")):
        flags.add(DataFlag.PERSONAL_DATA)
    if any(k in t for k in ("biometric", "special category", "health", "verification event data")):
        flags.add(DataFlag.SPECIAL_CATEGORY)
        flags.add(DataFlag.PERSONAL_DATA)
    if any(k in t for k in ("us-hosted", "us hosted", "cross-border", "transfer", "us-hosted processing", "us processing")):
        flags.add(DataFlag.CROSS_BORDER)
        flags.add(DataFlag.PERSONAL_DATA)
    if any(k in t for k in ("council", "public body", "nhs", "fca")) or item.counterparty.is_public_body:
        flags.add(DataFlag.REGULATED_COUNTERPARTY)
    if any(k in t for k in ("sync", "into the platform", "systems access")):
        flags.add(DataFlag.SYSTEMS_ACCESS)
    if "dpia_required_before_order_form" in _inherited(item):
        flags.add(DataFlag.HIGH_RISK_DPIA)
        flags.add(DataFlag.PERSONAL_DATA)
    return flags


def _inherited(item: InboxItem) -> list[str]:
    """Flags inherited from the item's prior-contract chain.

    Prefers the chain carried on the item (``related_contracts`` from intake
    metadata); falls back to the built-in inbox index keyed by id.
    """
    prior = item.related_contracts or None
    return inherited_flags(item.id, prior)


_MONEY = re.compile(r"£\s?([\d,]+)\s?(k|m)?", re.I)


def _value(t: str) -> float | None:
    m = _MONEY.search(t)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    return n * (1_000 if unit == "k" else 1_000_000 if unit == "m" else 1)


_DATE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def _deadline(t: str):
    from datetime import date

    m = _DATE.search(t)
    return date.fromisoformat(m.group(1)) if m else None


def _signatory(value: float | None) -> SignatoryLevel:
    # POL-LGL-002 value bands (illustrative thresholds).
    if value is None:
        return SignatoryLevel.LEGAL_COUNSEL
    if value >= 250_000:
        return SignatoryLevel.BOARD
    if value >= 100_000:
        return SignatoryLevel.CFO
    if value >= 25_000:
        return SignatoryLevel.COO
    return SignatoryLevel.LEGAL_COUNSEL


def classify(item: InboxItem) -> tuple[IntakeClassification, list[str]]:
    t = _text(item)
    value = _value(t)
    cls = IntakeClassification(
        document_family=_family(t),
        paper_source=_paper_source(t),
        direction=_direction(t),
        data_flags=_data_flags(item, t),
        prior_contract_ids=item.related_contracts or prior_contracts(item.id),
        signatory_level=_signatory(value),
        value_gbp=value,
        deadline=_deadline(t),
    )
    flags: list[str] = list(_inherited(item))
    if "no draft" in t or cls.paper_source is PaperSource.NO_DRAFT:
        flags.append("no_draft")
    if "unread" in t or "not yet read" in t:
        flags.append("unread_terms")
    if "out of scope" in t or "not contemplated" in t or "ai-generated" in t or "ai imagery" in t:
        flags.append("out_of_scope")
    if cls.paper_source is PaperSource.COUNTERPARTY_FIXED:
        flags.append("non_negotiable")
    if "no dpa" in t or ("dpa" not in t and DataFlag.PERSONAL_DATA in cls.data_flags and "order form + dpa" not in t):
        if "no dpa attached" in t or "no dpa" in t:
            flags.append("no_dpa")
    if "multi-party" in t or "four consortium" in t or "consortium" in t:
        flags.append("multi_party")
    return cls, flags


# ── Policy gates (POL-* validators) ─────────────────────────────────────────


def gate_privacy(state) -> GateCheck | None:
    """POL-PRIV-001 — DPA / breach window / transfer mechanism."""
    flags = state.data_flags
    if DataFlag.PERSONAL_DATA not in flags:
        return None
    findings, actions, basis = [], [], ["UK GDPR Art. 28(3)"]
    status = GateStatus.PASSED
    findings.append("Personal data in scope — Art. 28(3) processor terms required.")
    if DataFlag.HIGH_RISK_DPIA in flags:
        status = GateStatus.BLOCKED
        findings.append("High-risk processing with DPIA outstanding.")
        actions.append("Complete DPIA before any order form (Art. 35).")
        basis.append("UK GDPR Art. 35")
    if DataFlag.CROSS_BORDER in flags:
        if status is not GateStatus.BLOCKED:
            status = GateStatus.BLOCKED
        findings.append("Cross-border transfer (US hosting) with no transfer safeguard.")
        actions.append("Execute SCCs/UK IDTA + transfer risk assessment; obtain a DPA.")
        basis.append("UK GDPR Art. 46")
    if "no_dpa" in state.flags and status is GateStatus.PASSED:
        status = GateStatus.ACTION_REQUIRED
        actions.append("No DPA attached — require signed DPA before signature.")
    if DataFlag.SPECIAL_CATEGORY in flags and status is GateStatus.PASSED:
        status = GateStatus.ACTION_REQUIRED
        findings.append("Special-category data (Art. 9) — confirm lawful basis + safeguards.")
        basis.append("UK GDPR Art. 9")
    return GateCheck(
        gate=GateType.PRIVACY, status=status, findings=findings,
        required_actions=actions, legal_basis=basis,
    )


def gate_statutory(state) -> GateCheck | None:
    """Statutory checklist — only on counterparty paper."""
    if state.classification.paper_source not in (
        PaperSource.COUNTERPARTY, PaperSource.COUNTERPARTY_FIXED,
    ):
        return None
    return GateCheck(
        gate=GateType.STATUTORY, status=GateStatus.ACTION_REQUIRED,
        findings=["Counterparty paper — statutory checklist applies."],
        required_actions=[
            "Confirm anti-bribery, anti-slavery, tax-evasion, third-party (C(RTP)A) and UCTA reasonableness clauses.",
        ],
        legal_basis=[
            "Bribery Act 2010", "Modern Slavery Act 2015",
            "Criminal Finances Act 2017", "Unfair Contract Terms Act 1977",
        ],
    )


def gate_finance(state) -> GateCheck | None:
    """POL-FIN-007 — liability ask vs insured cover."""
    t = _text(state.item)
    asks_high = any(k in t for k in ("uncapped", "unlimited liability", "indemnif", "£5")) or (
        state.classification.value_gbp is not None and state.classification.value_gbp >= 100_000
    )
    if not asks_high:
        return None
    return GateCheck(
        gate=GateType.INSURANCE, status=GateStatus.ACTION_REQUIRED,
        findings=["Liability ask may exceed insured cover."],
        required_actions=["Obtain Finance sign-off (POL-FIN-007) before commitment."],
        legal_basis=["POL-FIN-007"],
    )


def build_gates(state) -> list[GateCheck]:
    return [g for g in (gate_privacy(state), gate_statutory(state), gate_finance(state)) if g]


# ── Redlines → playbook ladder ──────────────────────────────────────────────

# (keyword, clause_ref, section, tier, action, legal_basis)
_REDLINE_RULES: list[tuple[str, str, PlaybookSection, PositionTier, ResolutionAction, list[str]]] = [
    ("indemn", "Indemnity", PlaybookSection.EXCLUDED_LOSSES, PositionTier.REFUSAL_POINT,
     ResolutionAction.STRUCK, ["Playbook §3.2", "UCTA 1977 s.2"]),
    ("liability", "Liability cap", PlaybookSection.LIABILITY_CAP, PositionTier.FALLBACK_1,
     ResolutionAction.FALLBACK_APPLIED, ["Playbook §3.1"]),
    ("payment", "Payment terms", PlaybookSection.PAYMENT_TERMS, PositionTier.FALLBACK_1,
     ResolutionAction.FALLBACK_APPLIED,
     ["Playbook §2.4", "Late Payment of Commercial Debts (Interest) Act 1998"]),
    ("net 60", "Payment terms", PlaybookSection.PAYMENT_TERMS, PositionTier.FALLBACK_1,
     ResolutionAction.FALLBACK_APPLIED, ["Playbook §2.4"]),
    ("uplift", "Renewal uplift", PlaybookSection.UPLIFT_CAPS, PositionTier.STANDARD,
     ResolutionAction.HELD, ["Playbook §6.2"]),
    ("ai-generated", "AI-generated IP ownership", PlaybookSection.IP_COMMISSIONED_WORK,
     PositionTier.OFF_PLAYBOOK, ResolutionAction.ESCALATED, ["Playbook §4.3"]),
    ("ai imagery", "AI-generated IP ownership", PlaybookSection.IP_COMMISSIONED_WORK,
     PositionTier.OFF_PLAYBOOK, ResolutionAction.ESCALATED, ["Playbook §4.3"]),
]


def extract_redlines(state) -> list[Redline]:
    t = _text(state.item)
    seen: set[str] = set()
    out: list[Redline] = []
    for kw, ref, section, tier, action, basis in _REDLINE_RULES:
        if kw in t and ref not in seen:
            seen.add(ref)
            out.append(
                Redline(clause_ref=ref, description=f"Counterparty change to {ref.lower()}.",
                        playbook_section=section, tier=tier, action=action, legal_basis=basis)
            )
    return out
