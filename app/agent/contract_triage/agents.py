"""LLM brain for the triage workflow.

This is the agent's only brain: these functions make every substantive legal
judgment the graph routes on — classification, the POL-* policy gates, the
redline→playbook mapping and the reviewer explanation — via structured LLM
calls. A chat client (OpenAI or Azure OpenAI) is therefore required; the
decision functions raise if one is not configured. The helper agents are also
registered standalone in DevUI.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic import BaseModel

from .models import (
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


class RedlineLLM(BaseModel):
    clause_ref: str | None
    description: str
    playbook_section: PlaybookSection | None
    tier: PositionTier
    action: ResolutionAction
    legal_basis: list[str]


class RedlinesLLM(BaseModel):
    redlines: list[RedlineLLM]


# ── System instructions ──────────────────────────────────────────────────────

CLASSIFIER_INSTRUCTIONS = (
    "You are the intake-triage brain for Northgate Systems Ltd's in-house legal team. "
    "Read the inbound contract (intake note + document text) and classify it on six "
    "axes: document family, whose paper it is (ours clean, ours redlined, counterparty, "
    "counterparty-fixed such as a tender/online ToS/regulated annex, or no draft), the "
    "direction (are we the vendor selling or the customer buying), the data-protection "
    "profile, the POL-LGL-002 signatory level for its value band, the contract value in "
    "GBP if stated, and any hard deadline. Also raise the controlled intake flags that "
    "apply. Ground every call in what the document actually says; do not invent facts.\n"
    "Additionally, always read two intake facts straight from the document: the "
    "counterparty (the other side's name) and the sender's ask — what they want us to do "
    "with this paper, in one plain sentence. If the intake note already states a sender's "
    "ask, VALIDATE it against the document: set ask_supported=true when it matches, or "
    "ask_supported=false with an ask_note describing what the document actually supports "
    "when the stated ask is wrong, overreaches, or is unsupported. Always fill senders_ask "
    "with your best document-grounded version of the ask."
)

REDLINE_INSTRUCTIONS = (
    "You are Northgate's contract negotiation advisor, working strictly from Northgate's "
    "Playbook v4 and acting to protect Northgate's interests. Read the counterparty's paper "
    "and single out EVERY clause that is unfair, one-sided, or worse for Northgate than our "
    "playbook position — even when the counterparty has not tracked it as a change. A first "
    "draft on their paper is still negotiable: do not wave a term through just because it is "
    "their standard wording. Look in particular for one-sided or uncapped liability and "
    "indemnities, auto-renewal and one-sided termination, unilateral variation, excessive "
    "deposits / fees / penalties or disproportionate remedies, missing mutuality, onerous "
    "audit, exit or notice terms, and unreasonable governing-law or jurisdiction demands. "
    "For each, map it to a playbook section and decide the tier (standard position we hold, "
    "an approved fallback we can apply, a banned clause to strike, a refusal point, or an "
    "off-playbook novel term) and the resolution action. In the description, name the problem "
    "and state the specific better term to negotiate for — our opening ask AND the fallback we "
    "can live with. Cite the playbook section and the legal basis (e.g. UCTA 1977 for "
    "unreasonable terms). Escalate off-playbook or refusal-point items. Return an empty list "
    "only when the paper is our own clean template with no changes."
)

ESCALATION_INSTRUCTIONS = (
    "You summarise an escalation for the Legal Director in two sentences: what is being "
    "asked, why it is off-playbook, and the recommended position. Neutral and factual."
)

_GATE_BRIEF: dict[GateType, str] = {
    GateType.PRIVACY: (
        "You are the POL-PRIV-001 privacy validator. Decide whether UK GDPR processor "
        "terms apply and whether the deal is PASSED, ACTION_REQUIRED (e.g. no DPA "
        "attached, special-category data) or BLOCKED (DPIA outstanding for high-risk "
        "processing, or a cross-border US transfer with no SCC/IDTA safeguard). Cite the "
        "UK GDPR articles. If no personal data is in scope, set applies=false."
    ),
    GateType.STATUTORY: (
        "You are the statutory-checklist validator. It applies only to counterparty "
        "paper. Confirm anti-bribery, anti-slavery, tax-evasion, third-party (C(RTP)A) "
        "and UCTA reasonableness clauses. On counterparty paper set applies=true, status "
        "ACTION_REQUIRED and list the statutes; otherwise set applies=false."
    ),
    GateType.INSURANCE: (
        "You are the POL-FIN-007 insurance validator. Flag ACTION_REQUIRED when the "
        "liability ask (uncapped/unlimited liability, broad indemnities, a cap at or "
        "above ~£100k, or a high contract value) may exceed insured cover and needs "
        "Finance sign-off. Otherwise set applies=false."
    ),
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
    resp = await agent.run(prompt, options={"response_format": schema})
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
) -> tuple[IntakeClassification, list[str], IntakeReview]:
    """LLM classification, merged with ground-truth inherited flags.

    Also returns the document-grounded intake review — the counterparty name and
    the sender's ask the model read from the paper, plus whether any ask supplied
    at intake stands up to the document. The ``classify`` node applies these so a
    bare-PDF contract still triages and a provided ask is validated, not trusted.
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
    return cls, flags, review


async def gate_llm(state, gate: GateType) -> GateCheck | None:
    """LLM verdict for one policy gate; None ⇒ the gate does not apply."""
    inherited = list(state.flags or [])
    prompt = _item_context(state.item, inherited) + _gate_state_suffix(state)
    result = await _structured(_GATE_BRIEF[gate], prompt, GateLLM)
    if not result.applies:
        return None
    return GateCheck(
        gate=gate,
        status=result.status,
        findings=result.findings,
        required_actions=result.required_actions,
        legal_basis=result.legal_basis,
    )


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


async def redlines_llm(state) -> list[Redline]:
    """LLM redline→playbook mapping."""
    inherited = list(state.flags or [])
    prompt = _item_context(state.item, inherited) + _gate_state_suffix(state)
    result = await _structured(REDLINE_INSTRUCTIONS, prompt, RedlinesLLM)
    assert isinstance(result, RedlinesLLM)
    return [
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


# ── Reviewer explanation ─────────────────────────────────────────────────────


async def explain(state) -> str:
    """Produce a reviewer-facing explanation of the triage outcome."""
    client = get_chat_client()
    templated = _templated_explanation(state)
    if client is None:
        return templated
    try:
        agent = client.as_agent(
            id="explainer",
            name="Triage Explainer",
            instructions=(
                "You explain a contract triage decision to a busy in-house lawyer in 2-3 "
                "plain sentences: the classification, the key gate/redline findings, and "
                "the recommended next action. Do not invent facts beyond what is given."
            ),
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
