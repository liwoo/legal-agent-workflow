"""Graph nodes — one Executor per node in docs/agent-graph.mmd, grouped by stage.

The message flowing between nodes is the shared ``TriageState``. Routers set
``state.route`` and forward; the switch-case edges (wired in ``edges/workflow.py``)
branch on it. Files here map to the stages of the graph:

    intake        — ingest, classify, intake gate, fast-path guard
    gates         — the policy-validator fan-out → gather → outcome
    negotiability — non-negotiable fork / gap analysis
    redline       — the bounded redline loop
    approval      — set signer, sign, terminal SIGNED side-effects
    human_gate    — the re-entrant human interrupt + DECLINED / ESCALATED
    finalize      — shared scoring / explanation / persistence helpers

Every node class is re-exported here so ``edges/workflow.py`` and the tests can
reach them as ``from contract_triage import executors as X`` / ``X.Ingest``.
"""

from __future__ import annotations

from .approval import Approval, Execute, SideEffects
from .finalize import finalize
from .gates import FanOut, Gather, GateOutcome, ValidatorDPA, ValidatorFinance, ValidatorStatutory
from .human_gate import Declined, Escalated, HumanDecision, HumanGate
from .intake import CheapGuard, Classify, GuardCheck, IntakeGate, Ingest, TriageRouter
from .negotiability import GapAnalysis, GapCheck, Negotiability
from .redline import Disposition, Fallback, Hold, LoopControl, MapRedline, Strike

__all__ = [
    # intake & classification
    "Ingest", "Classify", "IntakeGate", "TriageRouter", "CheapGuard", "GuardCheck",
    # policy gates
    "FanOut", "ValidatorDPA", "ValidatorStatutory", "ValidatorFinance", "Gather", "GateOutcome",
    # negotiability
    "Negotiability", "GapAnalysis", "GapCheck",
    # redline loop
    "MapRedline", "Disposition", "Hold", "Fallback", "Strike", "LoopControl",
    # approval & side-effects
    "Approval", "Execute", "SideEffects",
    # human-in-the-loop
    "HumanGate", "HumanDecision", "Declined", "Escalated",
    # shared
    "finalize",
]
