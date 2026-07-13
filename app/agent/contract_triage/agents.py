"""Optional LLM layer.

The workflow runs fully offline on the heuristics in ``heuristics.py``. When a
chat client is configured (OpenAI or Azure OpenAI via env), these agents refine
the first-pass results and write the plain-English reviewer explanation. They
are also registered standalone in DevUI so you can poke at them directly.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:  # keep import-safe even if the openai extra is missing
    from agent_framework.openai import OpenAIChatClient
except Exception:  # pragma: no cover
    OpenAIChatClient = None  # type: ignore[assignment]


@lru_cache(maxsize=1)
def get_chat_client() -> Any | None:
    """Return a chat client if credentials are present, else None (demo mode)."""
    if OpenAIChatClient is None:
        return None
    try:
        if os.getenv("AZURE_OPENAI_ENDPOINT"):
            return OpenAIChatClient(
                model=os.getenv("AZURE_OPENAI_CHAT_MODEL", "gpt-4o-mini"),
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            )
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIChatClient()
    except Exception:
        return None
    return None


def llm_available() -> bool:
    return get_chat_client() is not None


CLASSIFIER_INSTRUCTIONS = (
    "You are a contract-intake triage assistant for Northgate Systems Ltd's in-house "
    "legal team. Given a short description of an inbound contract, state its document "
    "family, whose paper it is, the direction (are we vendor or customer), any data-"
    "protection flags, and whether it looks fast-path or needs a full review. Be terse."
)

REDLINE_INSTRUCTIONS = (
    "You are a contract redline advisor working strictly from Northgate's Playbook v4. "
    "For each counterparty change, map it to a playbook section and say whether it is a "
    "standard position, a fallback we can apply, a banned clause to strike, or a refusal "
    "point / novel term that must be escalated. Cite the section and the legal basis."
)

ESCALATION_INSTRUCTIONS = (
    "You summarise an escalation for the Legal Director in two sentences: what is being "
    "asked, why it is off-playbook, and the recommended position. Neutral and factual."
)


def build_agents() -> list[Any]:
    """Standalone agents surfaced in DevUI (empty in demo mode)."""
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
