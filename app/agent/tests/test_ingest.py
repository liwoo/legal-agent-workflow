"""The ingest node — assemble state from the flat fields, read + derive from PDF."""

from __future__ import annotations

from contract_triage import executors as X

from helpers import BASE_META, SHARED_PDF, emitted, make_item, make_request, run_node, triage_meta


def test_item_from_metadata_maps_intake_schema() -> None:
    item = make_item(related_contracts=["CR-2026-046"])
    assert item.id == BASE_META["id"]
    assert item.counterparty.name == BASE_META["counterparty"]
    assert item.what_arrived == BASE_META["summary"]
    assert item.sender_ask == BASE_META["senders_ask"]
    assert item.sender_role == BASE_META["received_from"]
    assert item.related_contracts == ["CR-2026-046"]
    assert item.pdf_path == SHARED_PDF


def test_ingest_builds_item_from_fields_and_reads_pdf() -> None:
    req = make_request()  # intake fields + the shared PDF path
    state = emitted(run_node(X.Ingest(id="ingest"), req))

    assert state.item.id == BASE_META["id"]
    assert state.item.counterparty.name == BASE_META["counterparty"]
    assert state.item.what_arrived == BASE_META["summary"]
    assert state.item.document_text
    assert "Kestrel Dynamics" in state.item.document_text
    assert state.trace == ["START", "ingest"]
    assert any("Read PDF" in e.label for e in state.timeline)
    # Ingest does not classify — that is the next node's job.
    assert state.classification is None


def test_ingest_derives_blank_fields_from_pdf() -> None:
    # Reviewer supplies only the required fields; everything else is derived.
    req = make_request(summary="", senders_ask="", counterparty="")
    state = emitted(run_node(X.Ingest(id="ingest"), req))

    assert state.item.what_arrived  # derived
    assert "NDA" in state.item.what_arrived
    assert "sign their version" in state.item.sender_ask  # derived
    assert state.item.counterparty.name == "Kestrel Dynamics Ltd"  # derived
    assert any("Derived from PDF" in e.label for e in state.timeline)


def test_ingest_parses_comma_separated_related_contracts() -> None:
    req = make_request(related_contracts=["CR-2026-046", "CR-2025-022"])
    state = emitted(run_node(X.Ingest(id="ingest"), req))
    assert state.item.related_contracts == ["CR-2026-046", "CR-2025-022"]


def test_ingest_tolerates_an_unreadable_pdf() -> None:
    req = make_request(pdf_path="/no/such/file.pdf")
    state = emitted(run_node(X.Ingest(id="ingest"), req))
    assert state.item.document_text == ""
    assert any("PDF unreadable" in e.label for e in state.timeline)
    # Supplied intake facts still stand.
    assert state.item.what_arrived == BASE_META["summary"]


def test_full_run_reads_pdf_end_to_end() -> None:
    state = triage_meta()
    assert state.item.document_text
    assert "CONTRACT INTAKE" in state.item.document_text.upper()


def test_pdf_only_intake_routes_like_the_explicit_metadata() -> None:
    # Same PDF, but no summary/ask/counterparty supplied — derivation should
    # reproduce the counterparty-NDA classification and the same terminal state.
    explicit = triage_meta()
    derived = triage_meta(summary="", senders_ask="", counterparty="")
    assert derived.end_state == explicit.end_state
