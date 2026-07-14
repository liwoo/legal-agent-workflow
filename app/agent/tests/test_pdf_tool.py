"""The PDF ingestion tool — read a document from an absolute path."""

from __future__ import annotations

from contract_triage.io.pdf import read_pdf, read_pdf_tool

from helpers import SHARED_PDF


def test_reads_the_shared_pdf() -> None:
    extract = read_pdf(SHARED_PDF)
    assert extract.ok is True
    assert extract.error is None
    assert extract.pages >= 1
    assert extract.char_count > 0
    # It is the CR-2026-050 intake sheet.
    assert "Kestrel Dynamics" in extract.text
    assert "CONTRACT INTAKE" in extract.text.upper()


def test_tool_returns_plain_text() -> None:
    text = read_pdf_tool(SHARED_PDF)
    assert isinstance(text, str)
    assert "Kestrel Dynamics" in text


def test_missing_file_degrades_gracefully() -> None:
    extract = read_pdf("/no/such/file.pdf")
    assert extract.ok is False
    assert extract.text == ""
    assert extract.pages == 0
    assert extract.error is not None


def test_empty_path_degrades_gracefully() -> None:
    extract = read_pdf("")
    assert extract.ok is False
    assert extract.text == ""
