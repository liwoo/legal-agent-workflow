"""PDF ingestion tool — read an intake/contract PDF from an absolute path.

The ``ingest`` node calls :func:`read_pdf` when a request carries a ``pdf_path``,
so the workflow can be driven from a real document on disk (metadata + PDF)
rather than only the in-memory inbox. It is dependency-light and degrades
gracefully: it tries ``pypdf`` first, then ``pdfminer.six``, and returns an
empty extract (never raises) if neither is installed or the file is unreadable —
the graph must always stay runnable.

``read_pdf_tool`` is the same capability wrapped as a plain callable so it can be
registered as an Agent-Framework tool and surfaced standalone in DevUI.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass
class PdfExtract:
    """Result of reading a PDF: its text plus light provenance."""

    path: str
    text: str
    pages: int
    ok: bool
    error: str | None = None

    @property
    def char_count(self) -> int:
        return len(self.text)


def _read_pypdf(path: str) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [p.extract_text() or "" for p in reader.pages]
    return "\n".join(pages).strip(), len(reader.pages)


def _read_pdfminer(path: str) -> tuple[str, int]:
    from pdfminer.high_level import extract_text

    text = (extract_text(path) or "").strip()
    # pdfminer's high-level API does not cheaply expose a page count; approximate
    # from form-feed separators it inserts between pages.
    pages = text.count("\f") + 1 if text else 0
    return text, pages


def read_pdf(path: str) -> PdfExtract:
    """Extract text from the PDF at ``path``. Never raises — see module docstring."""
    if not path or not os.path.isfile(path):
        return PdfExtract(path=path, text="", pages=0, ok=False, error="file not found")
    last_error: str | None = None
    for reader in (_read_pypdf, _read_pdfminer):
        try:
            text, pages = reader(path)
            return PdfExtract(path=path, text=text, pages=pages, ok=True)
        except Exception as exc:  # pragma: no cover - defensive, try next backend
            last_error = f"{reader.__name__}: {exc}"
    return PdfExtract(path=path, text="", pages=0, ok=False, error=last_error or "no PDF backend")


def read_pdf_tool(pdf_path: str) -> str:
    """Agent-Framework tool: return the plain text of the PDF at ``pdf_path``.

    Absolute path in, extracted text out (empty string if it cannot be read).
    """
    return read_pdf(pdf_path).text


# ── intake derivation ────────────────────────────────────────────────────────
#
# When the reviewer supplies only a PDF (and leaves the intake fields blank), the
# ingest node derives them from the document. These are best-effort readers of an
# intake sheet's structure — "WHAT ARRIVED" / "SENDER'S ASK" sections and a
# "Counterparty:" label — degrading to a leading snippet for free-form PDFs.

_SEP = re.compile(r"^[=\-—_ ]{6,}$")
_SECTION_HEADINGS = {"WHAT ARRIVED", "SENDER'S ASK", "SENDERS ASK", "EDIT HISTORY", "EDIT HISTORY"}


@dataclass
class DerivedIntake:
    what_arrived: str
    sender_ask: str
    counterparty: str


def _labeled(text: str, label: str) -> str:
    m = re.search(rf"^\s*{re.escape(label)}\s*[:\-]\s*(.+?)\s*$", text, re.I | re.M)
    return m.group(1).strip() if m else ""


def _section(text: str, heading: str) -> str:
    out: list[str] = []
    capturing = False
    for line in text.splitlines():
        s = line.strip()
        if not capturing:
            if s.upper() == heading.upper():
                capturing = True
            continue
        if _SEP.match(s) or s.upper() in _SECTION_HEADINGS:
            if out:
                break
            continue  # the separator line directly under the heading
        if s:
            out.append(s)
        elif out:
            break  # blank line after content ends the section
    return " ".join(out).strip().strip('"').strip()


def derive_intake(document_text: str) -> DerivedIntake:
    """Best-effort intake facts pulled from a contract/intake PDF's text."""
    text = document_text or ""
    what = _section(text, "WHAT ARRIVED")
    ask = _section(text, "SENDER'S ASK") or _section(text, "SENDERS ASK")
    cp = _labeled(text, "Counterparty")
    if not what:
        # Free-form document: fall back to the first substantial line.
        for line in text.splitlines():
            s = line.strip()
            if len(s) > 20 and not _SEP.match(s):
                what = s
                break
    return DerivedIntake(what_arrived=what, sender_ask=ask, counterparty=cp)
