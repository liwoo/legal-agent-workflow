"""System prompts for the LLM brain — one file per prompt, loaded at import.

Each ``*.md`` in this folder is the system instruction for one agent role. Keeping
them as files (rather than inline string literals) means the prompt text can be
read, diffed and tuned on its own, without touching the Python that wires it up.
The constants below are what :mod:`contract_triage.agents` hands to the model.

    classifier      → the six-axis intake classification + document-grounded review
    redline         → the redline → playbook mapping
    escalation      → the Legal-Director escalation summary (a DevUI helper agent)
    explainer       → the reviewer-facing outcome explanation
    gate_privacy    → the POL-PRIV-001 privacy validator
    gate_statutory  → the statutory-checklist validator
    gate_insurance  → the POL-FIN-007 insurance validator
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).parent


def load(name: str) -> str:
    """Return the text of ``<name>.md`` from this folder (trailing newline trimmed)."""
    return (_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


CLASSIFIER = load("classifier")
REDLINE = load("redline")
ESCALATION = load("escalation")
EXPLAINER = load("explainer")

# Policy-gate briefs, keyed by the gate's slug (see agents.GateType mapping).
GATE_PRIVACY = load("gate_privacy")
GATE_STATUTORY = load("gate_statutory")
GATE_INSURANCE = load("gate_insurance")

__all__ = [
    "load",
    "CLASSIFIER", "REDLINE", "ESCALATION", "EXPLAINER",
    "GATE_PRIVACY", "GATE_STATUTORY", "GATE_INSURANCE",
]
