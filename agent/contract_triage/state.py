"""The single shared State object that flows through the triage workflow graph.

The agent-graph (../../agent-graph.mmd) is a stateful LangGraph-style graph:
every node reads/writes one shared ``TriageState``; solid edges are
deterministic transitions; routers branch on the state; the human_gate is a
re-entrant interrupt. This module defines that state plus the request/result
envelopes the FastAPI + DevUI layers speak.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .models import (
    DataFlag,
    EndState,
    ForwardObligation,
    GateCheck,
    InboxItem,
    IntakeClassification,
    Redline,
    SignatoryLevel,
)


class TriageRequest(BaseModel):
    """Workflow input. DevUI renders a form from these fields.

    Pass just an ``item_id`` (e.g. ``"CR-2026-052"``) to triage a known inbox
    item, or embed a full ``item`` to triage an ad-hoc arrival.
    """

    item_id: str = Field(description="Inbox item id, e.g. CR-2026-052")
    item: InboxItem | None = Field(
        default=None,
        description="Optional inline item; if omitted it is loaded from the inbox dataset.",
    )


class TimelineEvent(BaseModel):
    at: datetime
    label: str
    detail: str | None = None
    kind: str = "info"  # info | warning | critical | success


class Interrupt(BaseModel):
    """A paused-at-human-gate marker — mirrors the mmd interrupt payload."""

    reason: str  # more_info | blocked | escalate | business_decision
    owner: str
    sla: str | None = None
    request_id: str | None = None


class TriageState(BaseModel):
    """The accumulating shared state — one per contract in flight."""

    item: InboxItem

    # Written by classify:
    classification: IntakeClassification | None = None
    flags: list[str] = Field(default_factory=list)

    # Written by the policy validators / gather:
    gate_checks: list[GateCheck] = Field(default_factory=list)

    # Written by the redline loop:
    redlines: list[Redline] = Field(default_factory=list)
    pending_redlines: list[dict[str, Any]] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 4

    # Outcome:
    end_state: EndState | None = None
    signer: SignatoryLevel | None = None
    forward_obligations: list[ForwardObligation] = Field(default_factory=list)
    interrupt: Interrupt | None = None
    score: int | None = None
    explanation: str | None = None
    recommended_action: str | None = None

    # Bookkeeping:
    route: str | None = None  # transient branch signal read by switch-case edges
    trace: list[str] = Field(default_factory=list)  # node ids visited (for graph highlight)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    # ── helpers ────────────────────────────────────────────────────────────
    def visit(self, node_id: str, label: str | None = None, kind: str = "info") -> None:
        if not self.trace or self.trace[-1] != node_id:
            self.trace.append(node_id)
        if label:
            self.timeline.append(TimelineEvent(at=datetime.now(), label=label, kind=kind))

    @property
    def data_flags(self) -> set[DataFlag]:
        return self.classification.data_flags if self.classification else set()

    def has_blocking_gate(self) -> bool:
        from .models import GateStatus

        return any(g.status is GateStatus.BLOCKED for g in self.gate_checks)

    def has_action_required(self) -> bool:
        from .models import GateStatus

        return any(g.status is GateStatus.ACTION_REQUIRED for g in self.gate_checks)
