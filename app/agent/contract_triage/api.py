"""FastAPI surface consumed by the frontend.

The Microsoft Agent Framework workflow (workflow.py) is the engine; this thin
REST layer runs it per contract and serialises the result into the API contract
the Next.js console speaks. The DevUI (devui_app.py) runs alongside for
interactive agent/workflow debugging.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from datetime import date

from . import config  # noqa: F401  — loads .env before anything reads env vars
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .observability import setup_observability
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
    # Seed the object store with the intake PDFs (no-op if MinIO isn't wired up).
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
    metadata = {
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
    pdf_bytes = await file.read() if file is not None else None
    filename = file.filename if file is not None else None
    try:
        return await service.create(metadata, pdf_bytes, filename)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Failed to create contract: {exc}")


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
