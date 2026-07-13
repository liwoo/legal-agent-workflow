"""The FastAPI service layer — triage a known inbox item end-to-end."""

from __future__ import annotations

import asyncio

from contract_triage.service import TriageService, _resolve_pdf


def test_resolve_pdf_finds_the_on_disk_intake() -> None:
    path = _resolve_pdf("CR-2026-050")
    assert path.endswith("cr-2026-050-intake.pdf")


def test_service_triages_inbox_item() -> None:
    svc = TriageService()
    detail = asyncio.run(svc.triage("CR-2026-050"))
    assert detail["id"] == "CR-2026-050"
    assert detail["end_state"]  # produced a terminal (or paused) outcome
    assert detail["classification"] is not None


def test_service_blocks_on_inherited_dpia() -> None:
    # CR-2026-052 inherits the DPIA-required precondition from CR-2026-046.
    svc = TriageService()
    detail = asyncio.run(svc.triage("CR-2026-052"))
    assert detail["end_state"] == "blocked"
    assert detail["queue"] == "quarantined"
