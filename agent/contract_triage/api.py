"""FastAPI surface consumed by the frontend.

The Microsoft Agent Framework workflow (workflow.py) is the engine; this thin
REST layer runs it per contract and serialises the result into the API contract
the Next.js console speaks. The DevUI (devui_app.py) runs alongside for
interactive agent/workflow debugging.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .service import TriageService

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


@app.get("/api/contracts/{item_id}")
async def get_contract(item_id: str) -> dict:
    try:
        return service.get(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown contract {item_id}")


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
