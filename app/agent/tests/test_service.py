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


def test_triage_events_streams_steps_then_done() -> None:
    """The streamed run narrates the agent live, then ends with the full detail."""
    svc = TriageService()

    async def collect() -> list[dict]:
        return [ev async for ev in svc.triage_events("CR-2026-050")]

    events = asyncio.run(collect())

    # Exactly one terminal 'done' event, and it comes last.
    assert [e["type"] for e in events].count("done") == 1
    assert events[-1]["type"] == "done"

    # Progress steps arrive before it, each with a human-readable label + kind.
    steps = [e for e in events if e["type"] == "step"]
    assert steps, "expected at least one progress step"
    assert all(s["label"] for s in steps)
    assert all(s["kind"] in {"info", "warning", "critical", "success"} for s in steps)
    # Node-level narration reaches the console (e.g. the classify node running).
    assert any(s["node"] == "classify" for s in steps)
    # Curated timeline labels are surfaced too (ingest logs the PDF read).
    assert any("Classified" in s["label"] for s in steps)

    # The done payload is the same contract the non-streaming path returns.
    done = events[-1]["detail"]
    assert done["id"] == "CR-2026-050"
    assert done["classification"] is not None
    assert done["end_state"]
