"""LLM brain for the triage workflow.

This is the agent's only brain: these functions make every substantive legal
judgment the graph routes on — classification, the POL-* policy gates, the
redline→playbook mapping and the reviewer explanation — via structured LLM
calls. A chat client (OpenAI or Azure OpenAI) is therefore required; the
decision functions raise if one is not configured. The helper agents are also
registered standalone in DevUI.

The system prompts live as individual files under :mod:`.prompts`; this module
only wires them to the model and converts the structured responses into the
domain types in :mod:`contract_triage.models`.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from functools import lru_cache
from typing import Any

_log = logging.getLogger(__name__)

from pydantic import BaseModel

from ..models import (
    ConfidenceScore,
    DataFlag,
    Direction,
    DocumentFamily,
    GateCheck,
    GateStatus,
    GateType,
    IntakeClassification,
    InboxItem,
    PaperSource,
    PlaybookSection,
    PositionTier,
    Redline,
    ResolutionAction,
    SignatoryLevel,
)
from . import prompts

try:  # keep import-safe even if the openai extra is missing
    from agent_framework.openai import OpenAIChatClient
except Exception:  # pragma: no cover
    OpenAIChatClient = None  # type: ignore[assignment]

# The default model — overridable via OPENAI_CHAT_MODEL / AZURE_OPENAI_CHAT_MODEL.
_DEFAULT_MODEL = "gpt-4o"


@lru_cache(maxsize=1)
def get_chat_client() -> Any | None:
    """Return a chat client if credentials are present, else None."""
    if OpenAIChatClient is None:
        return None
    try:
        if os.getenv("AZURE_OPENAI_ENDPOINT"):
            return OpenAIChatClient(
                model=os.getenv("AZURE_OPENAI_CHAT_MODEL", _DEFAULT_MODEL),
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            )
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIChatClient(model=os.getenv("OPENAI_CHAT_MODEL", _DEFAULT_MODEL))
    except Exception:
        return None
    return None


def llm_available() -> bool:
    return get_chat_client() is not None


# ── Structured-output schemas (LLM-friendly; converted to domain models) ─────


class TriageFlag(str, Enum):
    """The controlled intake flags the model may raise.

    ``dpia_required_before_order_form`` is deliberately NOT here: it is an
    *inherited* blocking precondition carried from a prior contract, merged in
    deterministically. Fresh high-risk processing is expressed via the
    ``high_risk_dpia`` data flag instead, so it routes through the privacy gate
    (which BLOCKS with full findings) rather than short-circuiting at intake.
    """

    NO_DRAFT = "no_draft"                                    # email ask, nothing to review yet
    UNREAD_TERMS = "unread_terms"                            # a clause pack the sender hasn't read
    OUT_OF_SCOPE = "out_of_scope"                            # add-on outside the parent framework
    NON_NEGOTIABLE = "non_negotiable"                        # tender / online ToS / regulated annex
    NO_DPA = "no_dpa"                                        # personal data but no DPA attached
    MULTI_PARTY = "multi_party"                              # consortium / >2 signatories


class ClassificationLLM(BaseModel):
    """The six triage axes plus intake flags, as the LLM returns them."""

    document_family: DocumentFamily
    paper_source: PaperSource
    direction: Direction
    data_flags: list[DataFlag]
    signatory_level: SignatoryLevel
    value_gbp: float | None
    deadline: str | None  # ISO date (YYYY-MM-DD) or null
    flags: list[TriageFlag]
    # Intake facts read straight from the document, so a bare PDF still triages
    # and a reviewer-supplied ask is validated rather than trusted blindly.
    counterparty_name: str | None = None  # the other side's name, from the document
    senders_ask: str | None = None        # what the sender is asking for, in one sentence
    ask_supported: bool = True            # is any provided sender's ask consistent with the document?
    ask_note: str | None = None           # when ask_supported is false, what the document actually supports
    rationale: str
    # Self-reported confidence in this classification, 0 (guessing) → 10 (certain).
    # Averaged with the other decisions in ``finalize`` for the run-level score.
    confidence: int = 5
    confidence_note: str | None = None


class IntakeReview(BaseModel):
    """Derived / validated intake facts the classifier read from the document."""

    counterparty_name: str | None = None
    senders_ask: str | None = None
    ask_supported: bool = True
    ask_note: str | None = None


class GateLLM(BaseModel):
    """A single policy-gate verdict."""

    applies: bool
    status: GateStatus
    findings: list[str]
    required_actions: list[str]
    legal_basis: list[str]
    confidence: int = 5
    confidence_note: str | None = None


class RedlineLLM(BaseModel):
    clause_ref: str | None
    description: str
    playbook_section: PlaybookSection | None
    tier: PositionTier
    action: ResolutionAction
    legal_basis: list[str]


class RedlinesLLM(BaseModel):
    redlines: list[RedlineLLM]
    confidence: int = 5
    confidence_note: str | None = None


# ── System instructions (loaded from prompts/*.md) ───────────────────────────

CLASSIFIER_INSTRUCTIONS = prompts.CLASSIFIER
REDLINE_INSTRUCTIONS = prompts.REDLINE
ESCALATION_INSTRUCTIONS = prompts.ESCALATION
EXPLAINER_INSTRUCTIONS = prompts.EXPLAINER

_GATE_BRIEF: dict[GateType, str] = {
    GateType.PRIVACY: prompts.GATE_PRIVACY,
    GateType.STATUTORY: prompts.GATE_STATUTORY,
    GateType.INSURANCE: prompts.GATE_INSURANCE,
}


def build_agents() -> list[Any]:
    """Standalone agents surfaced in DevUI (empty when no client is configured)."""
    client = get_chat_client()
    if client is None:
        return []
    return [
        client.as_agent(
            id="classifier", name="Intake Classifier", instructions=CLASSIFIER_INSTRUCTIONS
        ),
        client.as_agent(
            id="redline_advisor", name="Redline Advisor", instructions=REDLINE_INSTRUCTIONS
        ),
        client.as_agent(
            id="escalation_summariser",
            name="Escalation Summariser",
            instructions=ESCALATION_INSTRUCTIONS,
        ),
    ]


# ── Structured call plumbing ─────────────────────────────────────────────────

_DOC_LIMIT = 8_000  # chars of PDF text handed to the model


class LLMUnavailableError(RuntimeError):
    """Raised when a decision needs the model but no chat client is configured."""


async def _structured(instructions: str, prompt: str, schema: type[BaseModel]) -> Any:
    """Run a one-shot structured call and return the parsed model.

    Every graph decision (classify, gates, redlines) runs at ``temperature=0``
    so re-triaging the same paper does not silently reroute through a different
    graph path — a warm-day classifier flipping ``counterparty`` to
    ``counterparty_fixed`` used to skip ``map_redline`` entirely on re-eval.

    Raises ``LLMUnavailableError`` if no client is configured, and lets any
    provider/parse error propagate — the agent is LLM-first, so there is no
    deterministic fallback to swallow the failure.
    """
    client = get_chat_client()
    if client is None:
        raise LLMUnavailableError(
            "No chat client configured — set OPENAI_API_KEY (see app/agent/.env)."
        )
    agent = client.as_agent(id="triage", name="Triage", instructions=instructions)
    resp = await agent.run(
        prompt, options={"response_format": schema, "temperature": 0.0}
    )
    value = getattr(resp, "value", None)
    if isinstance(value, schema):
        return value
    # The SDK didn't hydrate .value — parse the raw text.
    text = getattr(resp, "text", None)
    if not text:
        raise ValueError(f"empty structured response for {schema.__name__}")
    return schema.model_validate_json(text)


def _item_context(item: InboxItem, inherited: list[str]) -> str:
    cp = item.counterparty
    doc = (item.document_text or "").strip()
    if len(doc) > _DOC_LIMIT:
        doc = doc[:_DOC_LIMIT] + "\n…[truncated]…"
    lines = [
        f"Contract id: {item.id}",
        f"Counterparty: {cp.name}"
        + (f" (sector: {cp.sector})" if cp.sector else "")
        + (" [public body]" if cp.is_public_body else "")
        + (" [regulated]" if cp.is_regulated else ""),
        f"Received from: {item.sender_role}",
        f"What arrived: {item.what_arrived or '(not stated)'}",
        f"Sender's ask: {item.sender_ask or '(not stated)'}",
    ]
    if item.related_contracts:
        lines.append("Prior contracts in the chain: " + ", ".join(item.related_contracts))
    if inherited:
        lines.append("Inherited flags from prior contracts: " + ", ".join(inherited))
    lines.append("")
    lines.append("Document text:")
    lines.append(doc or "(no readable document text)")
    return "\n".join(lines)


# ── Value-band → signatory (POL-LGL-002 lookup, not a judgment) ──────────────


def _signatory(value: float | None) -> SignatoryLevel:
    if value is None:
        return SignatoryLevel.LEGAL_COUNSEL
    if value >= 250_000:
        return SignatoryLevel.BOARD
    if value >= 100_000:
        return SignatoryLevel.CFO
    if value >= 25_000:
        return SignatoryLevel.COO
    return SignatoryLevel.LEGAL_COUNSEL


def _parse_date(value: str | None):
    from datetime import date

    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


# ── LLM decision functions (the agent's only brain) ──────────────────────────


async def classify_llm(
    item: InboxItem, inherited: list[str], prior_ids: list[str]
) -> tuple[IntakeClassification, list[str], IntakeReview, ConfidenceScore]:
    """LLM classification, merged with ground-truth inherited flags.

    Also returns the document-grounded intake review — the counterparty name and
    the sender's ask the model read from the paper, plus whether any ask supplied
    at intake stands up to the document. The ``classify`` node applies these so a
    bare-PDF contract still triages and a provided ask is validated, not trusted.
    The fourth return value is the classifier's self-reported confidence in its
    call, folded into the run-level score by :func:`finalize`.
    """
    result = await _structured(
        CLASSIFIER_INSTRUCTIONS, _item_context(item, inherited), ClassificationLLM
    )
    assert isinstance(result, ClassificationLLM)

    data_flags = set(result.data_flags)
    flags = [f.value for f in result.flags]

    # Inherited flags are ground truth from the prior-contract chain; the model
    # is told about them but we merge them in deterministically so the DPIA /
    # blocking preconditions always survive.
    for inh in inherited:
        if inh not in flags:
            flags.append(inh)
    if "dpia_required_before_order_form" in flags:
        data_flags |= {DataFlag.HIGH_RISK_DPIA, DataFlag.PERSONAL_DATA}
    if result.paper_source is PaperSource.NO_DRAFT and "no_draft" not in flags:
        flags.append("no_draft")
    if result.paper_source is PaperSource.COUNTERPARTY_FIXED and "non_negotiable" not in flags:
        flags.append("non_negotiable")

    cls = IntakeClassification(
        document_family=result.document_family,
        paper_source=result.paper_source,
        direction=result.direction,
        data_flags=data_flags,
        prior_contract_ids=item.related_contracts or prior_ids,
        signatory_level=_signatory(result.value_gbp) if result.value_gbp is not None
        else result.signatory_level,
        value_gbp=result.value_gbp,
        deadline=_parse_date(result.deadline),
    )
    review = IntakeReview(
        counterparty_name=(result.counterparty_name or "").strip() or None,
        senders_ask=(result.senders_ask or "").strip() or None,
        ask_supported=result.ask_supported,
        ask_note=(result.ask_note or "").strip() or None,
    )
    confidence = ConfidenceScore(
        stage="classify",
        score=_clamp_confidence(result.confidence),
        note=(result.confidence_note or "").strip() or None,
    )
    return cls, flags, review, confidence


async def gate_llm(
    state, gate: GateType
) -> tuple[GateCheck | None, ConfidenceScore | None]:
    """LLM verdict for one policy gate.

    Returns ``(None, None)`` if the gate does not apply — a skipped gate has no
    decision, so it contributes no confidence to the run-level average.
    Otherwise returns the check plus the gate's self-reported confidence in it.
    """
    inherited = list(state.flags or [])
    prompt = _item_context(state.item, inherited) + _gate_state_suffix(state)
    result = await _structured(_GATE_BRIEF[gate], prompt, GateLLM)
    if not result.applies:
        return None, None
    check = GateCheck(
        gate=gate,
        status=result.status,
        findings=result.findings,
        required_actions=result.required_actions,
        legal_basis=result.legal_basis,
    )
    confidence = ConfidenceScore(
        stage=f"gate_{gate.value}",
        score=_clamp_confidence(result.confidence),
        note=(result.confidence_note or "").strip() or None,
    )
    return check, confidence


def _clamp_confidence(score: int | float | None) -> int:
    """Force any model-emitted number into the 0-10 range we display."""
    if score is None:
        return 5
    return max(0, min(10, int(score)))


def _gate_state_suffix(state) -> str:
    cls = state.classification
    if not cls:
        return ""
    return (
        "\n\nClassification so far:"
        f"\n- document family: {cls.document_family.value}"
        f"\n- paper source: {cls.paper_source.value}"
        f"\n- direction: {cls.direction.value}"
        f"\n- data flags: {', '.join(sorted(f.value for f in cls.data_flags)) or 'none'}"
        f"\n- value (GBP): {cls.value_gbp if cls.value_gbp is not None else 'unknown'}"
        f"\n- intake flags: {', '.join(state.flags) or 'none'}"
    )


async def redlines_llm(state) -> tuple[list[Redline], ConfidenceScore]:
    """LLM redline→playbook mapping, grounded in the desk's live playbook.

    The playbook sections are pulled fresh from the repository on every call and
    injected into the instructions, so a runtime edit to a position is reflected
    on the very next contract — the redline advisor maps against the desk's
    *actual* standard/fallback/refusal ladders, not the model's prior.

    Returns the redlines plus the advisor's self-reported confidence in the
    mapping, folded into the run-level score by :func:`finalize`.
    """
    from ..io.playbook import playbook_repo

    inherited = list(state.flags or [])
    prompt = _item_context(state.item, inherited) + _gate_state_suffix(state)
    playbook = playbook_repo.render_for_prompt()
    instructions = (
        f"{REDLINE_INSTRUCTIONS}\n\n{playbook}" if playbook else REDLINE_INSTRUCTIONS
    )
    result = await _structured(instructions, prompt, RedlinesLLM)
    assert isinstance(result, RedlinesLLM)
    redlines = [
        Redline(
            clause_ref=r.clause_ref,
            description=r.description,
            playbook_section=r.playbook_section,
            tier=r.tier,
            action=r.action,
            legal_basis=r.legal_basis,
        )
        for r in result.redlines
    ]
    confidence = ConfidenceScore(
        stage="redlines",
        score=_clamp_confidence(result.confidence),
        note=(result.confidence_note or "").strip() or None,
    )
    return redlines, confidence


# ── Reviewer explanation ─────────────────────────────────────────────────────


async def explain(state) -> str:
    """Produce a reviewer-facing explanation of the triage outcome."""
    client = get_chat_client()
    templated = _templated_explanation(state)
    if client is None:
        return templated
    try:
        agent = client.as_agent(
            id="explainer", name="Triage Explainer", instructions=EXPLAINER_INSTRUCTIONS
        )
        resp = await agent.run(templated)
        text = getattr(resp, "text", None) or str(resp)
        return text.strip() or templated
    except Exception:
        return templated


def _templated_explanation(state) -> str:
    cls = state.classification
    bits = []
    if cls:
        bits.append(
            f"{cls.document_family.value.replace('_', ' ')} on "
            f"{cls.paper_source.value.replace('_', ' ')} ({cls.direction.value})."
        )
    if state.gate_checks:
        blocked = [g for g in state.gate_checks if g.status.value == "blocked"]
        if blocked:
            bits.append("Blocked at a policy gate: " + blocked[0].findings[0])
        elif any(g.status.value == "action_required" for g in state.gate_checks):
            bits.append("Gate actions required before signature.")
        else:
            bits.append("Policy gates clear.")
    if state.redlines:
        bits.append(
            f"{len(state.redlines)} redline(s) mapped to the playbook: "
            + ", ".join(f"{r.clause_ref} ({r.action.value})" for r in state.redlines)
            + "."
        )
    if state.recommended_action:
        bits.append(state.recommended_action)
    return " ".join(bits)
