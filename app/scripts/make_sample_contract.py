#!/usr/bin/env python3
"""Generate a minimal, dependency-free intake PDF for demos and tests.

The document mirrors the ``data/test/<ID>/*.pdf`` intake-sheet layout — a
``Counterparty:`` label plus ``WHAT ARRIVED`` / ``SENDER'S ASK`` sections — so the
agent's ingest node can derive the intake facts straight from the PDF text.

    python app/scripts/make_sample_contract.py out.pdf

Importable too: ``build_intake_pdf(lines) -> bytes``.
"""

from __future__ import annotations

import sys


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_intake_pdf(lines: list[str]) -> bytes:
    """Return the bytes of a single-page PDF rendering ``lines`` (one per row)."""
    content = ["BT", "/F1 11 Tf", "72 720 Td", "15 TL"]
    for line in lines:
        content.append(f"({_escape(line)}) Tj")
        content.append("T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


SAMPLE_LINES = [
    "NORTHGATE SYSTEMS LTD — CONTRACT INTAKE SHEET",
    "",
    "Counterparty: Meridian Freight Solutions Ltd",
    "Received: 2026-07-13   From: AE (sales)",
    "",
    "WHAT ARRIVED",
    "Counterparty's own mutual NDA paper (5 pages, PDF), unsigned. Prospective",
    "logistics customer ahead of a platform demo and pricing discussion.",
    "",
    "SENDER'S ASK",
    "Can we sign their NDA as-is so we can book the demo next week?",
]


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "sample-contract.pdf"
    with open(out_path, "wb") as fh:
        fh.write(build_intake_pdf(SAMPLE_LINES))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
