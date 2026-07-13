"""The single shared State object that flows through the triage workflow graph.

The agent-graph (docs/agent-graph.mmd) is a stateful LangGraph-style graph:
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
    """Workflow input. DevUI renders one plain text box per field — no JSON.

    Required: a contract ``id``, the ``date_received``, and the ``pdf_path`` — the
    document is always read. The remaining intake facts (``counterparty``,
    ``summary``, ``senders_ask`` …) are optional: leave them blank and the ingest
    node derives them from the PDF.
    """

    # ── required ─────────────────────────────────────────────────────────────
    id: str = Field(description="Contract reference, e.g. CR-2026-050")
    date_received: str = Field(description="Date received, ISO 8601 (YYYY-MM-DD)")
    pdf_path: str = Field(description="Absolute path to the source PDF, always read at ingest")

    # ── optional — derived from the PDF when left blank ──────────────────────
    counterparty: str = Field(default="", description="Counterparty name (derived if blank)")
    summary: str = Field(default="", description="What arrived — the paper and the situation (derived if blank)")
    senders_ask: str = Field(default="", description="The sender's ask, in their words (derived if blank)")
    name: str = Field(default="", description="Contract name (optional)")
    received_from: str = Field(default="", description="Sender role, e.g. 'AE (sales)' (optional)")
    related_contracts: str = Field(
        default="", description="Prior contract ids in the chain, comma-separated (optional)"
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
