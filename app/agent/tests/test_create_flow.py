"""The "New Contract" flow + SQLite repository, end-to-end.

Covers tasks the console depends on: the example inbox is *persisted* into
SQLite (not just held in code), a reviewer-created contract is inserted through
the repository, its PDF is stored, the agent is triggered, and the graph's
terminal node writes the outcome back to SQLite.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from contract_triage.io import db
from contract_triage.io.repository import ContractRepository
from contract_triage.service import TriageService

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from make_sample_contract import build_intake_pdf, SAMPLE_LINES  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point persistence at a throwaway SQLite file + upload dir per test."""
    monkeypatch.setenv("TRIAGE_DB_PATH", str(tmp_path / "triage.db"))
    monkeypatch.setenv("CONTRACT_UPLOAD_DIR", str(tmp_path / "uploads"))
    # service reads _UPLOAD_ROOT at import time; re-point it too.
    import contract_triage.service as svc

    monkeypatch.setattr(svc, "_UPLOAD_ROOT", tmp_path / "uploads")
    db.init_db()
    yield


def test_repository_seeds_examples_into_sqlite() -> None:
    repo = ContractRepository()
    written = repo.seed_examples()
    assert written == 10
    rows = db.list_contracts()
    assert len(rows) == 10
    # The seeded item carries its prior-contract chain, so inherited flags work.
    item = repo.get_item("CR-2026-052")
    assert item is not None
    assert item.related_contracts == ["CR-2026-046"]


def test_create_persists_contract_pdf_and_outcome() -> None:
    svc = TriageService()  # seeds examples in __post_init__
    pdf = build_intake_pdf(SAMPLE_LINES)
    metadata = {
        "counterparty": "Meridian Freight Solutions Ltd",
        "received_from": "AE (sales)",
        "summary": "Counterparty's own mutual NDA paper, unsigned.",
        "senders_ask": "Can we sign their NDA as-is?",
        "related_contracts": [],
        "date_received": "2026-07-13",
    }

    detail = asyncio.run(svc.create(metadata, pdf, "sample-contract.pdf"))

    new_id = detail["id"]
    assert new_id.startswith("CR-")
    assert detail["counterparty"] == "Meridian Freight Solutions Ltd"
    assert detail["classification"] is not None
    assert detail["end_state"]  # the agent reached a terminal/paused outcome

    # 1. intake row persisted as a user contract
    row = db.get_contract(new_id)
    assert row is not None and row["source"] == "user"
    assert row["pdf_path"] and Path(row["pdf_path"]).is_file()

    # 2. the local PDF was written for the ingest node
    assert Path(row["pdf_path"]).read_bytes()[:4] == b"%PDF"

    # 3. the agent's terminal node wrote the outcome back to SQLite
    outcome = db.get_outcome(new_id)
    assert outcome is not None
    assert outcome["end_state"] == detail["end_state"]

    # 4. it shows up in the register alongside the 10 seeded examples
    ids = {c["id"] for c in svc.list_contracts()}
    assert new_id in ids
    assert "CR-2026-050" in ids


def test_create_allocates_sequential_ids() -> None:
    svc = TriageService()
    pdf = build_intake_pdf(SAMPLE_LINES)
    meta = {"counterparty": "Acme Ltd", "summary": "NDA", "senders_ask": "sign?"}
    d1 = asyncio.run(svc.create(dict(meta), pdf))
    d2 = asyncio.run(svc.create(dict(meta), pdf))
    assert d1["id"] != d2["id"]
