"""Application service — runs the workflow for the FastAPI layer, serialises the
resulting state into the API contract, and tracks paused (human-gate) runs so a
reviewer decision can resume them.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_framework import Workflow

from . import db, graph_spec
from .executors import HumanDecision
from .models import EndState, InboxItem
from .observability import workflow_span
from .playbook import playbook_repo
from .repository import repo
from .state import TriageRequest, TriageState
from .storage import store
from .workflow import build_workflow

# Friendly per-node labels (node id → display name), mirrored from the graph the
# console renders — used to narrate an executor entering during a streamed run.
_NODE_LABELS: dict[str, str] = {n["id"]: n["label"] for n in graph_spec.WORKFLOW_NODES}


def _states(data: Any) -> Iterator[TriageState]:
    """Yield the ``TriageState`` payload(s) carried by a workflow event.

    ``executor_invoked`` events carry the input message (a ``TriageState`` for
    every node past ingest); ``executor_completed`` events carry a *list* of the
    messages the node sent / outputs it yielded. Both are the shared state, so we
    normalise them into a flat stream of states to read the growing timeline off.
    """
    if isinstance(data, TriageState):
        yield data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, TriageState):
                yield item

# repo root is three levels up: contract_triage → agent → app → <root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_ROOT = _REPO_ROOT / "data"
# Where reviewer-uploaded intake PDFs are kept locally so the ingest node can
# read them (mirrored into the object store for browser presigned URLs).
_UPLOAD_ROOT = Path(os.getenv("CONTRACT_UPLOAD_DIR", ".data/uploads"))


def _resolve_pdf(item_id: str) -> str:
    """Best-effort absolute path to an inbox item's source PDF on disk."""
    for base in (_DATA_ROOT / "test" / item_id, _DATA_ROOT / "contracts" / item_id):
        if base.is_dir():
            pdfs = sorted(base.glob("*.pdf"))
            if pdfs:
                return str(pdfs[0])
    return ""


def _request_for(item: InboxItem) -> TriageRequest:
    """Map an inbox item onto the flat workflow request.

    Uses the item's own ``pdf_path`` when present (reviewer-uploaded contracts),
    otherwise resolves the on-disk seed document by id."""
    return TriageRequest(
        id=item.id,
        date_received=item.received_at.date().isoformat(),
        pdf_path=item.pdf_path or _resolve_pdf(item.id),
        counterparty=item.counterparty.name,
        summary=item.what_arrived,
        senders_ask=item.sender_ask,
        received_from=item.sender_role,
        related_contracts=",".join(item.related_contracts),
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
        # Boot the durable stores, seed the example contracts into SQLite, and
        # rehydrate any previously-computed results so the queues are populated
        # the moment the API answers — even before the eager re-triage in the
        # FastAPI lifespan finishes.
        db.init_db()
        store.connect()
        repo.seed_examples()
        playbook_repo.seed_from_json()  # ground the redline node in the desk's positions
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
    async def triage_events(self, item_id: str) -> AsyncIterator[dict]:
        """Run the workflow with the Agent Framework's **streaming** API, yielding
        a live narrative of the run as it happens.

        The Microsoft Agent Framework surfaces per-node lifecycle events
        (``executor_invoked`` / ``executor_completed``) as the graph executes.
        We turn each into a ``step`` event — an executor entering becomes a
        friendly node label, and any new entry the node appends to the shared
        ``timeline`` becomes a richer, human-readable line. The final ``done``
        event carries the fully serialised detail, identical to the one the
        non-streaming path returns.
        """
        item = repo.get_item(item_id)
        if item is None:
            raise KeyError(item_id)
        wf = build_workflow()
        emitted = 0  # how many timeline entries we've already surfaced
        with workflow_span(
            "triage_contract",
            **{"contract.id": item_id, "contract.counterparty": item.counterparty.name},
        ):
            stream = wf.run(_request_for(item), stream=True)
            async for event in stream:
                etype = getattr(event, "type", None)
                node = getattr(event, "executor_id", None)
                # An executor entering: narrate the node currently running.
                if etype == "executor_invoked" and node and node != "START":
                    yield {
                        "type": "step", "node": node,
                        "label": _NODE_LABELS.get(node, node),
                        "detail": None, "kind": "info",
                        "at": datetime.now().isoformat(),
                    }
                # Surface any curated timeline labels the node just appended.
                for st in _states(getattr(event, "data", None)):
                    if len(st.timeline) > emitted:
                        for e in st.timeline[emitted:]:
                            yield {
                                "type": "step", "node": node,
                                "label": e.label, "detail": e.detail,
                                "kind": e.kind, "at": _iso(e.at),
                            }
                        emitted = len(st.timeline)
            result = await stream.get_final_response()
        reqs = result.get_request_info_events()
        if reqs:
            event = reqs[0]
            state: TriageState = event.data
            state.interrupt.request_id = event.request_id
            self.pending[item_id] = _Pending(workflow=wf, request_id=event.request_id, state=state)
        else:
            state = result.get_outputs()[0]
            self.pending.pop(item_id, None)
        # Serialise the workflow's enriched item (intake facts the ingest node
        # derived from the PDF are filled in there, not on the pre-run item).
        detail = self._detail(state.item, state)
        self.results[item_id] = detail
        db.save_result(item_id, detail)
        yield {"type": "done", "detail": detail}

    async def triage(self, item_id: str) -> dict:
        """Run a triage to completion and return the detail (non-streaming path).

        Shares the single streamed implementation so the two paths can't drift —
        we just drain the event stream and keep the terminal ``done`` payload.
        """
        detail: dict | None = None
        async for ev in self.triage_events(item_id):
            if ev["type"] == "done":
                detail = ev["detail"]
        assert detail is not None  # the stream always ends with a done event
        return detail

    def _persist_intake(
        self, metadata: dict, pdf_bytes: bytes | None, filename: str | None
    ) -> str:
        """Allocate an id, store the intake PDF, and persist the intake row."""
        item_id = metadata.get("id") or repo.next_id()
        metadata = {**metadata, "id": item_id}

        pdf_path: str | None = None
        if pdf_bytes:
            dest = _UPLOAD_ROOT / item_id / "intake.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pdf_bytes)
            pdf_path = str(dest.resolve())
            store.put_object(item_id, pdf_bytes)  # graceful no-op if MinIO is down

        repo.create(metadata, pdf_path)  # persist intake → SQLite
        return item_id

    async def create_events(
        self, metadata: dict, pdf_bytes: bytes | None = None, filename: str | None = None
    ) -> AsyncIterator[dict]:
        """The streaming "New Contract" flow: persist intake → store PDF → stream
        the agent run, yielding the same ``step`` / ``done`` events as
        :meth:`triage_events`."""
        item_id = self._persist_intake(metadata, pdf_bytes, filename)
        async for ev in self.triage_events(item_id):  # run the graph → nodes persist outcome
            yield ev

    async def create(
        self, metadata: dict, pdf_bytes: bytes | None = None, filename: str | None = None
    ) -> dict:
        """The "New Contract" flow, end-to-end:

        1. allocate an id and persist the intake row to **SQLite** (repository),
        2. store the uploaded **PDF** locally (for the ingest node) and mirror it
           into the **object store** (MinIO) for browser presigned URLs,
        3. **trigger the agent** — whose terminal nodes write the outcome back to
           SQLite — and return the resulting detail for the console.
        """
        detail: dict | None = None
        async for ev in self.create_events(metadata, pdf_bytes, filename):
            if ev["type"] == "done":
                detail = ev["detail"]
        assert detail is not None
        return detail

    async def resolve(self, item_id: str, decision: str, note: str | None = None) -> dict:
        item = repo.get_item(item_id)
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
        detail = self._detail(state.item, state)
        self.results[item_id] = detail
        db.save_result(item_id, detail)
        db.save_decision(item_id, decision, note)
        return detail

    def get(self, item_id: str) -> dict:
        item = repo.get_item(item_id)
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
        for item in repo.list_items():
            if item.id in self.results:
                out.append({k: self.results[item.id][k] for k in _SUMMARY_KEYS})
            else:
                out.append(self._summary_fields(item, None, "untriaged"))
        return out

    async def triage_all(self) -> None:
        """Eagerly triage the inbox so the dashboard/queues are populated."""
        for item in repo.list_items():
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
