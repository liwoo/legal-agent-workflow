"""Application service — runs the workflow for the FastAPI layer, serialises the
resulting state into the API contract, and tracks paused (human-gate) runs so a
reviewer decision can resume them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_framework import Workflow

from . import db, graph_spec
from .data import get_inbox, get_item, prior_contracts
from .executors import HumanDecision
from .models import EndState, InboxItem
from .observability import workflow_span
from .state import TriageRequest, TriageState
from .storage import store
from .workflow import build_workflow

# repo root is three levels up: contract_triage → agent → app → <root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_ROOT = _REPO_ROOT / "data"


def _resolve_pdf(item_id: str) -> str:
    """Best-effort absolute path to an inbox item's source PDF on disk."""
    for base in (_DATA_ROOT / "test" / item_id, _DATA_ROOT / "contracts" / item_id):
        if base.is_dir():
            pdfs = sorted(base.glob("*.pdf"))
            if pdfs:
                return str(pdfs[0])
    return ""


def _request_for(item: InboxItem) -> TriageRequest:
    """Map a known inbox item onto the flat workflow request."""
    return TriageRequest(
        id=item.id,
        date_received=item.received_at.date().isoformat(),
        pdf_path=_resolve_pdf(item.id),
        counterparty=item.counterparty.name,
        summary=item.what_arrived,
        senders_ask=item.sender_ask,
        received_from=item.sender_role,
        related_contracts=",".join(prior_contracts(item.id)),
    )

_APPROVED = {EndState.SIGNED_NO_EDITS, EndState.SIGNED_DESK_EDITS, EndState.SIGNED_WITH_DEVIATION}
_QUARANTINED = {EndState.ESCALATED, EndState.BLOCKED, EndState.DECLINED, EndState.BUSINESS_DECISION}


def queue_of(end_state: EndState | None) -> str:
    if end_state in _APPROVED:
        return "approved"
    if end_state in _QUARANTINED:
        return "quarantined"
    return "pending"


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


@dataclass
class _Pending:
    workflow: Workflow
    request_id: str
    state: TriageState


@dataclass
class TriageService:
    results: dict[str, dict] = field(default_factory=dict)  # item_id -> ContractDetail
    pending: dict[str, _Pending] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Boot the durable stores and rehydrate any previously-computed results
        # so the queues are populated the moment the API answers — even before
        # the eager re-triage in the FastAPI lifespan finishes.
        db.init_db()
        store.connect()
        self.results.update(db.load_results())

    # ── serialisation ────────────────────────────────────────────────────────
    def _summary_fields(self, item: InboxItem, state: TriageState | None, ai_status: str) -> dict:
        cls = state.classification if state else None
        return {
            "id": item.id,
            "name": f"{item.counterparty.name}",
            "counterparty": item.counterparty.name,
            "document_family": cls.document_family.value if cls else "other",
            "paper_source": cls.paper_source.value if cls else "counterparty",
            "direction": cls.direction.value if cls else "vendor",
            "received_at": _iso(item.received_at),
            "sender_role": item.sender_role,
            "sender_ask": item.sender_ask,
            "what_arrived": item.what_arrived,
            "deadline": _iso(cls.deadline) if cls else None,
            "prior_contract_ids": cls.prior_contract_ids if cls else [],
            "ai_status": ai_status,
            "score": state.score if state else None,
            "end_state": state.end_state.value if state and state.end_state else None,
            "queue": queue_of(state.end_state if state else None),
        }

    def _detail(self, item: InboxItem, state: TriageState, ai_status: str = "triaged") -> dict:
        cls = state.classification
        detail = self._summary_fields(item, state, ai_status)
        detail.update(
            {
                "classification": {
                    "document_family": cls.document_family.value,
                    "paper_source": cls.paper_source.value,
                    "direction": cls.direction.value,
                    "data_flags": sorted(f.value for f in cls.data_flags),
                    "prior_contract_ids": cls.prior_contract_ids,
                    "signatory_level": cls.signatory_level.value,
                    "value_gbp": cls.value_gbp,
                    "deadline": _iso(cls.deadline),
                }
                if cls
                else None,
                "gate_checks": [
                    {
                        "gate": g.gate.value,
                        "status": g.status.value,
                        "findings": g.findings,
                        "required_actions": g.required_actions,
                        "legal_basis": g.legal_basis,
                    }
                    for g in state.gate_checks
                ],
                "redlines": [
                    {
                        "clause_ref": r.clause_ref,
                        "description": r.description,
                        "playbook_section": r.playbook_section.value if r.playbook_section else None,
                        "tier": r.tier.value,
                        "action": r.action.value,
                        "legal_basis": r.legal_basis,
                    }
                    for r in state.redlines
                ],
                "forward_obligations": [
                    {"type": o.type.value, "note": o.note, "due": _iso(o.due)}
                    for o in state.forward_obligations
                ],
                "explanation": state.explanation,
                "recommended_action": state.recommended_action,
                "interrupt": (
                    {
                        "reason": state.interrupt.reason,
                        "owner": state.interrupt.owner,
                        "sla": state.interrupt.sla,
                        "request_id": state.interrupt.request_id,
                    }
                    if state.interrupt
                    else None
                ),
                "path_node_ids": state.trace,
                "timeline": [
                    {"at": _iso(e.at), "label": e.label, "detail": e.detail, "kind": e.kind}
                    for e in state.timeline
                ],
                "document_url": store.presigned_url(item.id),
            }
        )
        return detail

    # ── operations ───────────────────────────────────────────────────────────
    async def triage(self, item_id: str) -> dict:
        item = get_item(item_id)
        if item is None:
            raise KeyError(item_id)
        wf = build_workflow()
        with workflow_span(
            "triage_contract",
            **{"contract.id": item_id, "contract.counterparty": item.counterparty.name},
        ):
            result = await wf.run(_request_for(item))
        reqs = result.get_request_info_events()
        if reqs:
            event = reqs[0]
            state: TriageState = event.data
            state.interrupt.request_id = event.request_id
            self.pending[item_id] = _Pending(workflow=wf, request_id=event.request_id, state=state)
            detail = self._detail(item, state)
        else:
            state = result.get_outputs()[0]
            self.pending.pop(item_id, None)
            detail = self._detail(item, state)
        self.results[item_id] = detail
        db.save_result(item_id, detail)
        return detail

    async def resolve(self, item_id: str, decision: str, note: str | None = None) -> dict:
        item = get_item(item_id)
        if item is None:
            raise KeyError(item_id)
        pend = self.pending.get(item_id)
        if pend is None:
            # nothing paused — treat as a fresh triage
            return await self.triage(item_id)
        with workflow_span(
            "resolve_contract",
            **{"contract.id": item_id, "decision": decision},
        ):
            result = await pend.workflow.run(
                responses={pend.request_id: HumanDecision(decision=decision, note=note)}
            )
        outputs = result.get_outputs()
        state = outputs[0] if outputs else pend.state
        self.pending.pop(item_id, None)
        detail = self._detail(item, state)
        self.results[item_id] = detail
        db.save_result(item_id, detail)
        db.save_decision(item_id, decision, note)
        return detail

    def get(self, item_id: str) -> dict:
        item = get_item(item_id)
        if item is None:
            raise KeyError(item_id)
        if item_id in self.results:
            return self.results[item_id]
        # untriaged view
        detail = self._summary_fields(item, None, "untriaged")
        detail.update(
            {
                "classification": None, "gate_checks": [], "redlines": [],
                "forward_obligations": [], "explanation": None, "recommended_action": None,
                "interrupt": None, "path_node_ids": [], "timeline": [],
                "document_url": store.presigned_url(item.id),
            }
        )
        return detail

    def list_contracts(self) -> list[dict]:
        out = []
        for item in get_inbox():
            if item.id in self.results:
                out.append({k: self.results[item.id][k] for k in _SUMMARY_KEYS})
            else:
                out.append(self._summary_fields(item, None, "untriaged"))
        return out

    async def triage_all(self) -> None:
        """Eagerly triage the inbox so the dashboard/queues are populated."""
        for item in get_inbox():
            try:
                await self.triage(item.id)
            except Exception:  # keep startup resilient
                pass

    def workflow_graph(self) -> dict:
        return graph_spec.graph()


_SUMMARY_KEYS = [
    "id", "name", "counterparty", "document_family", "paper_source", "direction",
    "received_at", "sender_role", "sender_ask", "what_arrived", "deadline",
    "prior_contract_ids", "ai_status", "score", "end_state", "queue",
]
