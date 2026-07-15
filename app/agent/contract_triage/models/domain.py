"""Pydantic types for the Northgate contract-triage workflow.

Every enum value and model field is grounded in the corpus:
contracts/*/metadata.json, contracts/*/edit-log.json, the 2025/2026
registers, contract-inbox.md, the Playbook v4 and policies POL-*.
The decision graph these types drive is in decision-framework.md / .mmd.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


# ── Classification axes (knowable at intake, no legal judgment) ──────────


class DocumentFamily(str, Enum):
    """Axis 1 — what kind of paper this is."""

    MUTUAL_NDA = "mutual_nda"                    # 28 in corpus
    ORDER_FORM = "order_form"                    # 24
    ORDER_FORM_RENEWAL = "order_form_renewal"
    DPA = "dpa"                                  # incl. SCC/IDTA addenda
    SUPPLIER_AGREEMENT = "supplier_agreement"    # incl. subscriptions, orders
    SUPPLIER_RENEWAL = "supplier_renewal"
    FRAMEWORK_AGREEMENT = "framework_agreement"
    SOW = "sow"                                  # under a framework
    AMENDMENT = "amendment"
    RESELLER_AGREEMENT = "reseller_agreement"
    REFERRAL_AGREEMENT = "referral_agreement"
    MOU = "mou"                                  # heads of terms / LoI
    CONTRACTOR_AGREEMENT = "contractor_agreement"
    TENDER_TERMS = "tender_terms"                # e.g. CR-2026-058
    SPONSORSHIP = "sponsorship"
    OTHER = "other"


class PaperSource(str, Enum):
    """Axis 2 — whose draft, and can it be negotiated."""

    OURS_CLEAN = "ours_clean"                    # fast-path candidate
    OURS_REDLINED = "ours_redlined"              # e.g. CR-2026-051
    COUNTERPARTY = "counterparty"                # negotiable
    COUNTERPARTY_FIXED = "counterparty_fixed"    # tender / online ToS / regulated annex
    NO_DRAFT = "no_draft"                        # email ask only, e.g. CR-2026-059


class Direction(str, Enum):
    """Axis 3 — Northgate's role; playbook positions invert with it (§3.5, §4.3)."""

    VENDOR = "vendor"      # cap our liability, grant licence
    CUSTOMER = "customer"  # seek supplier floor, take assignment


class DataFlag(str, Enum):
    """Axis 4 — data profile; not mutually exclusive, so used as a set."""

    PERSONAL_DATA = "personal_data"              # DPA required (Art. 28(3))
    SPECIAL_CATEGORY = "special_category"        # Art. 9 — health, biometric
    HIGH_RISK_DPIA = "high_risk_dpia"            # Art. 35 — DPIA before signature
    CROSS_BORDER = "cross_border"                # Art. 46 — SCCs / UK IDTA + TIA
    RESIDENCY_COMMITMENT = "residency_commitment"  # EEA-only / UK-only hosting
    REGULATED_COUNTERPARTY = "regulated_counterparty"  # FCA SYSC 8, NHS, FOIA body
    SYSTEMS_ACCESS = "systems_access"            # counterparty touches our systems/data


class SignatoryLevel(str, Enum):
    """Axis 6 — value band routing per POL-LGL-002."""

    LEGAL_COUNSEL = "legal_counsel"
    COO = "coo"
    CFO = "cfo"
    BOARD = "board"


# ── Playbook & policy references ─────────────────────────────────────────


class PolicyId(str, Enum):
    PLAYBOOK = "PLAYBOOK"
    PRIVACY = "POL-PRIV-001"
    SECURITY = "POL-SEC-011"
    INSURANCE = "POL-FIN-007"
    HR = "POL-HR-003"
    SIGNATURE = "POL-LGL-002"


class PlaybookSection(str, Enum):
    """The negotiable positions cited in the corpus edit logs."""

    NDA_TERM = "1.2"
    CONFIDENTIAL_INFO_DEFINITION = "1.3"
    RESIDUALS_PROHIBITED = "1.4"
    PRICING_STRUCTURES = "2.2"
    PAYMENT_TERMS = "2.4"
    NO_MFN = "2.6"
    LIABILITY_CAP = "3.1"
    EXCLUDED_LOSSES = "3.2"
    SLA_REMEDIES = "3.4"
    VENDOR_LIABILITY_FLOORS = "3.5"
    IP_COMMISSIONED_WORK = "4.3"
    NO_SOURCE_CODE_ESCROW = "4.5"
    GOVERNING_LAW = "5.2"
    RENEWAL_NOTICE = "6.1"
    UPLIFT_CAPS = "6.2"
    TERM_COMMITMENTS_ETF = "6.4"
    EXIT_ASSISTANCE = "6.5"
    AUDIT_RIGHTS = "7.3"
    NO_EXCLUSIVE_APPOINTMENTS = "8.1"
    REFERRAL_COMMISSIONS = "8.3"
    UNILATERAL_VARIATION = "9.1"
    AMENDMENT_SCOPE = "9.2"
    HEADS_OF_TERMS = "9.4"


class PositionTier(str, Enum):
    """Where a counterparty ask lands on a playbook ladder."""

    STANDARD = "standard"            # matches our default position
    FALLBACK_1 = "fallback_1"
    FALLBACK_2 = "fallback_2"
    REFUSAL_POINT = "refusal_point"  # never conceded at the desk
    OFF_PLAYBOOK = "off_playbook"    # unmapped / novel term


class ResolutionAction(str, Enum):
    """What the desk did with a redline."""

    HELD = "held"                          # standard position retained
    FALLBACK_APPLIED = "fallback_applied"  # approved library wording, recorded
    STRUCK = "struck"                      # banned clause removed on sight
    SUBSTITUTE_OFFERED = "substitute_offered"  # e.g. continuity commitment for escrow
    ESCALATED = "escalated"                # sent to Chapter 10


class PlaybookRule(BaseModel):
    """A playbook position expressed as data: the standard → fallback → refusal ladder."""

    section: PlaybookSection
    title: str
    standard_position: str
    fallbacks: list[str] = Field(default_factory=list)  # empty ⇒ no-fallback clause
    refusal_point: str
    substitute: str | None = None  # what we offer instead when we strike (e.g. §4.5, §2.6)


# ── Gates ─────────────────────────────────────────────────────────────────


class GateType(str, Enum):
    PRIVACY = "privacy"                    # POL-PRIV-001
    SECURITY = "security"                  # POL-SEC-011
    STATUTORY = "statutory"                # bribery / slavery / tax / C(RTP)A / UCTA
    INSURANCE = "insurance"                # POL-FIN-007
    WORKER_STATUS = "worker_status"        # POL-HR-003, IR35
    SIGNATURE_AUTHORITY = "signature_authority"  # POL-LGL-002


class GateStatus(str, Enum):
    PASSED = "passed"
    ACTION_REQUIRED = "action_required"  # clauses to add/amend before signature
    BLOCKED = "blocked"                  # precondition owns the timeline (e.g. DPIA)


class GateCheck(BaseModel):
    gate: GateType
    status: GateStatus
    findings: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    legal_basis: list[str] = Field(default_factory=list)


# ── Escalation (Playbook Ch.10) ───────────────────────────────────────────


class EscalationTier(str, Enum):
    LEGAL_DIRECTOR = "legal_director"          # deviation within tiers
    LD_PLUS_COO = "ld_plus_coo"                # refusal point / uncapped / exclusivity / gov law
    LD_COO_CFO = "ld_coo_cfo"                  # + above POL-FIN-007 threshold


class EscalationDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Escalation(BaseModel):
    playbook_section: PlaybookSection | None = None  # None ⇒ off-playbook novelty
    reason: str
    tier: EscalationTier
    raised_on: date
    sla_due: date  # 2 business days per Ch.10
    decision: EscalationDecision = EscalationDecision.PENDING
    approver: str | None = None
    rationale: str | None = None


class DeviationRecord(BaseModel):
    """Ch.10: every approved deviation is logged or it is unauthorised."""

    point_conceded: str
    playbook_section: PlaybookSection
    approver: str
    rationale: str
    approved_on: date


# ── Redlines & edit log ───────────────────────────────────────────────────


class Redline(BaseModel):
    """One counterparty deviation, mapped and resolved through the playbook ladder."""

    clause_ref: str | None = None
    description: str
    playbook_section: PlaybookSection | None = None  # None ⇒ off-playbook
    tier: PositionTier
    action: ResolutionAction
    legal_basis: list[str] = Field(default_factory=list)
    escalation: Escalation | None = None


class EditLogEntry(BaseModel):
    """Mirrors contracts/*/edit-log.json exactly."""

    edit_number: int
    date: date
    description: str
    legal_basis: str


# ── Forward obligations (why "signed" is not fully terminal) ─────────────


class ObligationType(str, Enum):
    DIARISE_RENEWAL_NOTICE = "diarise_renewal_notice"  # §6.1
    DPIA_BEFORE_ORDER_FORM = "dpia_before_order_form"  # CR-2026-046 pattern
    RECORD_DEVIATION = "record_deviation"              # Ch.10 → Ch.12 review
    FLAG_FOLLOW_ON_PAPER = "flag_follow_on_paper"      # condition on next contract in chain
    INSURANCE_REVIEW = "insurance_review"              # cap promised vs cover held


class ForwardObligation(BaseModel):
    type: ObligationType
    note: str
    due: date | None = None
    applies_to_counterparty: bool = True  # carries forward along the related-contracts chain


class ConfidenceScore(BaseModel):
    """One decision LLM's self-reported confidence on the call it just made.

    Each decision agent (classifier, each policy gate, redline advisor) fills in
    a 0-10 rating alongside its structured output — captured here so
    :func:`finalize` can average them into the run-level confidence displayed to
    the reviewer. Self-reported ratings are known to be poorly calibrated in
    isolation; averaging across ~5 independent decisions per run smooths the
    signal.
    """

    stage: str  # e.g. "classify", "gate_privacy", "redlines"
    score: int  # 0 (no idea) → 10 (certain)
    note: str | None = None  # optional one-line reason, when the model volunteers one


# ── Intake, outcome, register record ──────────────────────────────────────


class Counterparty(BaseModel):
    name: str
    jurisdiction: str | None = None  # drives §5.2 governing-law expectations
    sector: str | None = None
    is_regulated: bool = False       # FCA / NHS / public body
    is_public_body: bool = False     # FOIA carve-out pattern


class IntakeClassification(BaseModel):
    """The six triage axes — all determinable before reading a single clause."""

    document_family: DocumentFamily
    paper_source: PaperSource
    direction: Direction
    data_flags: set[DataFlag] = Field(default_factory=set)
    prior_contract_ids: list[str] = Field(default_factory=list)
    signatory_level: SignatoryLevel = SignatoryLevel.LEGAL_COUNSEL
    value_gbp: float | None = None
    deadline: date | None = None


class InboxItem(BaseModel):
    """An untriaged arrival — mirrors what is knowable in contract-inbox.md."""

    id: str  # e.g. "CR-2026-050"
    received_at: datetime
    sender_role: str  # AE, CSM, CEO, Head of Engineering, ...
    counterparty: Counterparty
    what_arrived: str
    sender_ask: str
    related_contracts: list[str] = Field(default_factory=list)  # prior-file chain from intake metadata
    pdf_path: str | None = None       # absolute path to the source document, read at ingest
    document_text: str | None = None  # extracted PDF text (filled by the ingest PDF tool)
    classification: IntakeClassification | None = None  # filled by triage


class EndState(str, Enum):
    """Terminal (or overlay-terminal) states — §4 of decision-framework.md."""

    SIGNED_NO_EDITS = "signed_no_edits"              # fast path, 34% of corpus
    SIGNED_DESK_EDITS = "signed_desk_edits"          # majority path
    SIGNED_WITH_DEVIATION = "signed_with_deviation"  # recorded fallback concession
    ESCALATED = "escalated"                          # awaiting Ch.10 decision
    BLOCKED = "blocked"                              # precondition outstanding
    MORE_INFO_NEEDED = "more_info_needed"            # returned to sender
    BUSINESS_DECISION = "business_decision"          # non-negotiable paper: accept or decline
    DECLINED = "declined"                            # walked away


class ContractStatus(str, Enum):
    """Live pipeline status — matches metadata.json `status` plus intake stages."""

    RECEIVED = "received"
    IN_TRIAGE = "in_triage"
    IN_REVIEW = "in_review"      # observed in CR-2026-048
    ESCALATED = "escalated"
    BLOCKED = "blocked"
    AWAITING_INFO = "awaiting_info"
    AWAITING_SIGNATURE = "awaiting_signature"
    SIGNED = "signed"
    DECLINED = "declined"


class ReviewOutcome(BaseModel):
    """Everything the review produced, in one record."""

    end_state: EndState
    gate_checks: list[GateCheck] = Field(default_factory=list)
    redlines: list[Redline] = Field(default_factory=list)
    escalations: list[Escalation] = Field(default_factory=list)
    deviations: list[DeviationRecord] = Field(default_factory=list)
    forward_obligations: list[ForwardObligation] = Field(default_factory=list)
    edit_log: list[EditLogEntry] = Field(default_factory=list)


class ContractRecord(BaseModel):
    """Register entry — mirrors contracts/*/metadata.json, plus triage/outcome."""

    id: str
    name: str
    type: str  # free-text as in metadata.json; classification holds the enum
    parties: list[str]
    date_received: date
    date_signed: date | None = None
    status: ContractStatus
    related_contracts: list[str] = Field(default_factory=list)
    pdf: str | None = None
    classification: IntakeClassification | None = None
    outcome: ReviewOutcome | None = None
