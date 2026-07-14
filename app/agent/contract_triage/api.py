"""FastAPI surface consumed by the frontend.

The Microsoft Agent Framework workflow (workflow.py) is the engine; this thin
REST layer runs it per contract and serialises the result into the API contract
the Next.js console speaks. The DevUI (devui_app.py) runs alongside for
interactive agent/workflow debugging.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from datetime import date

from . import config  # noqa: F401  — loads .env before anything reads env vars
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

from .observability import setup_observability
from .playbook import playbook_repo
from .service import TriageService
from .storage import store

setup_observability()  # ships Agent Framework traces to Langfuse when configured

service = TriageService()

POLICIES = [
    {"id": "PLAYBOOK", "title": "Contract Playbook v4",
     "summary": "Standard → fallback → refusal ladder for every negotiable position."},
    {"id": "POL-PRIV-001", "title": "Data Protection Policy",
     "summary": "DPA (Art. 28(3)), DPIA (Art. 35) and transfer safeguards (Art. 46)."},
    {"id": "POL-SEC-011", "title": "Information Security Policy",
     "summary": "Controls required when a counterparty touches our systems or data."},
    {"id": "POL-FIN-007", "title": "Insurance & Liability Policy",
     "summary": "Liability caps vs. insured cover; Finance sign-off thresholds."},
    {"id": "POL-HR-003", "title": "Worker Status Policy",
     "summary": "IR35 / worker-status checks for contractor agreements."},
    {"id": "POL-LGL-002", "title": "Signature Authority Policy",
     "summary": "Value-band routing of signatories: Counsel → COO → CFO → Board."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The inbox ships empty — reviewers add contracts via the "New Contract" flow.
    # Only when SEED_EXAMPLES=1 do we seed the demo contracts' PDFs and (unless
    # disabled) eagerly triage them so the queues open warm.
    if os.getenv("SEED_EXAMPLES", "0") == "1":
        store.seed()
        if os.getenv("TRIAGE_EAGER", "1") == "1":
            await service.triage_all()
    yield


app = FastAPI(title="Northgate Contract Triage API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResolveRequest(BaseModel):
    decision: str = "resolved"  # resolved | declined | escalated
    note: str | None = None


class PlaybookSectionUpdate(BaseModel):
    """A reviewer edit to one negotiating position (the editable Settings surface)."""

    title: str
    guidance: str
    updated_by: str | None = None


# ── server-sent events (streamed triage runs) ────────────────────────────────
# Headers that keep the stream flowing to the browser un-buffered: no proxy
# buffering (nginx), no caching, keep the connection open.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, data: dict) -> str:
    """Frame one payload as a Server-Sent Event (``event:`` + ``data:`` lines)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _sse_stream(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Adapt the service's step/done event generator into an SSE byte stream,
    turning any run failure into a terminal ``error`` event the console can show."""
    try:
        async for ev in events:
            kind = ev.pop("type")
            yield _sse(kind, ev)
    except Exception as exc:  # surface the failure in-band, then end the stream
        yield _sse("error", {"message": str(exc)})


def _intake_metadata(
    counterparty: str, name: str, sector: str, jurisdiction: str,
    is_public_body: bool, is_regulated: bool, received_from: str,
    summary: str, senders_ask: str, related_contracts: str, date_received: str,
) -> dict:
    """Normalise the "New Contract" form fields into the intake metadata dict."""
    return {
        "counterparty": counterparty.strip(),
        "name": name.strip() or f"{counterparty.strip()}",
        "sector": sector.strip() or None,
        "jurisdiction": jurisdiction.strip() or None,
        "is_public_body": is_public_body,
        "is_regulated": is_regulated,
        "received_from": received_from.strip() or "unknown",
        "summary": summary.strip(),
        "senders_ask": senders_ask.strip(),
        "related_contracts": [s.strip() for s in related_contracts.split(",") if s.strip()],
        "date_received": date_received.strip() or date.today().isoformat(),
    }


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/contracts")
async def list_contracts() -> list[dict]:
    return service.list_contracts()


@app.post("/api/contracts")
async def create_contract(
    counterparty: str = Form(...),
    name: str = Form(""),
    sector: str = Form(""),
    jurisdiction: str = Form(""),
    is_public_body: bool = Form(False),
    is_regulated: bool = Form(False),
    received_from: str = Form(""),
    summary: str = Form(""),
    senders_ask: str = Form(""),
    related_contracts: str = Form(""),
    date_received: str = Form(""),
    file: UploadFile | None = File(None),
) -> dict:
    """Create a contract: persist intake → store PDF → trigger the agent.

    Accepts a multipart form (so an intake PDF can ride along). The agent runs
    synchronously and its terminal nodes write the outcome to SQLite; the freshly
    triaged detail is returned for the console to render."""
    metadata = _intake_metadata(
        counterparty, name, sector, jurisdiction, is_public_body, is_regulated,
        received_from, summary, senders_ask, related_contracts, date_received,
    )
    pdf_bytes = await file.read() if file is not None else None
    filename = file.filename if file is not None else None
    try:
        return await service.create(metadata, pdf_bytes, filename)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Failed to create contract: {exc}")


@app.post("/api/contracts/stream")
async def create_contract_stream(
    counterparty: str = Form(...),
    name: str = Form(""),
    sector: str = Form(""),
    jurisdiction: str = Form(""),
    is_public_body: bool = Form(False),
    is_regulated: bool = Form(False),
    received_from: str = Form(""),
    summary: str = Form(""),
    senders_ask: str = Form(""),
    related_contracts: str = Form(""),
    date_received: str = Form(""),
    file: UploadFile | None = File(None),
) -> StreamingResponse:
    """Streaming twin of ``POST /api/contracts``.

    Same persist → store → triage flow, but streamed as Server-Sent Events so the
    console can render a live, node-by-node view of the agent run instead of a
    single opaque spinner. Ends with a ``done`` event carrying the full detail."""
    metadata = _intake_metadata(
        counterparty, name, sector, jurisdiction, is_public_body, is_regulated,
        received_from, summary, senders_ask, related_contracts, date_received,
    )
    # Read the upload *before* handing off to the streaming generator — the
    # request body must be consumed within the handler.
    pdf_bytes = await file.read() if file is not None else None
    filename = file.filename if file is not None else None
    events = service.create_events(metadata, pdf_bytes, filename)
    return StreamingResponse(_sse_stream(events), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.get("/api/contracts/{item_id}")
async def get_contract(item_id: str) -> dict:
    try:
        return service.get(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown contract {item_id}")


@app.get("/api/contracts/{item_id}/document")
async def get_contract_document(item_id: str) -> RedirectResponse:
    """Redirect to a short-lived presigned URL for the item's intake PDF."""
    url = store.presigned_url(item_id)
    if url is None:
        raise HTTPException(status_code=404, detail=f"No document for {item_id}")
    return RedirectResponse(url)


@app.post("/api/contracts/{item_id}/triage")
async def triage_contract(item_id: str) -> dict:
    try:
        return await service.triage(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown contract {item_id}")


@app.post("/api/contracts/{item_id}/triage/stream")
async def triage_contract_stream(item_id: str) -> StreamingResponse:
    """Streaming twin of ``POST /api/contracts/{id}/triage`` — re-runs the agent
    and streams its node-by-node progress as Server-Sent Events. An unknown id
    surfaces as a terminal ``error`` event rather than a 404, since the response
    has already begun streaming."""
    return StreamingResponse(
        _sse_stream(service.triage_events(item_id)),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@app.post("/api/contracts/{item_id}/resolve")
async def resolve_contract(item_id: str, body: ResolveRequest) -> dict:
    try:
        return await service.resolve(item_id, body.decision, body.note)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown contract {item_id}")


@app.get("/api/workflow/graph")
async def workflow_graph() -> dict:
    return service.workflow_graph()


@app.get("/api/policies")
async def list_policies() -> list[dict]:
    return POLICIES


@app.get("/api/playbook")
async def list_playbook() -> list[dict]:
    """The desk's negotiating positions — the sections the redline node maps against."""
    return playbook_repo.list_sections()


@app.put("/api/playbook/sections/{section}")
async def update_playbook_section(section: str, body: PlaybookSectionUpdate) -> dict:
    """Edit one section. Takes effect on the next contract the redline node maps —
    the position is pulled fresh from here on every run."""
    updated = playbook_repo.update_section(
        section, body.title, body.guidance, body.updated_by
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Unknown playbook section {section}")
    result = playbook_repo.get_section(section)
    if result is None:  # pragma: no cover - defensive
        raise HTTPException(status_code=404, detail=f"Unknown playbook section {section}")
    return result
