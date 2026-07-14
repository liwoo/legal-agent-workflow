"""Playbook repository — the negotiating positions the redline node is grounded in.

The desk's Playbook v4 ships as ``data/policies/PLAYBOOK.json`` (rich chapter
prose). This module makes SQLite the *runtime* source of truth for it: the 23
negotiable sections cited in the corpus (the ``PlaybookSection`` enum) are
*seeded* from that JSON on boot, and can then be *edited* at runtime without a
redeploy — an edit takes effect on the very next contract the redline node maps.

Two consumers go through this one repository:
  * ``agents.redlines_llm`` — renders the sections into the redline prompt so the
    model maps each counterparty change against the desk's *actual* positions
    (see ``render_for_prompt``); and
  * the FastAPI layer — reads/edits sections for the Settings surface.

Resilient by design (mirrors ``repository.py`` / ``db.py``): if SQLite is
unavailable, reads fall back to parsing ``PLAYBOOK.json`` directly, so grounding
still works — it just can't persist edits across a restart.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from . import db
from ..models import PlaybookSection

_log = logging.getLogger(__name__)

# io → contract_triage → agent → app → <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PLAYBOOK_JSON = _REPO_ROOT / "data" / "policies" / "PLAYBOOK.json"

# The negotiable section numbers we ground on = the enum, so the DB rows line up
# 1:1 with the sections the redline mapping is allowed to cite.
_NEGOTIABLE = {s.value for s in PlaybookSection}

_SECTION_RE = re.compile(r"^(\d+\.\d+)\s+(.*)$")


def _parse_json_sections() -> list[dict]:
    """Extract the negotiable sections from PLAYBOOK.json as
    ``{section, chapter, title, guidance}``, in document order.

    Each chapter's ``content`` is a flat run of ``subhead``/``para`` blocks; a
    subhead like ``"3.1 Limitation of Liability — fallback tiers"`` opens a
    section and the paragraphs that follow (until the next subhead) are its
    guidance. We keep only subheads whose number is a negotiable section.
    """
    try:
        doc = json.loads(_PLAYBOOK_JSON.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("could not read PLAYBOOK.json (%s); playbook grounding disabled", exc)
        return []

    out: list[dict] = []
    for chapter in doc.get("chapters", []):
        number = chapter.get("number")
        current: dict | None = None
        paras: list[str] = []

        def _flush() -> None:
            if current is not None:
                current["guidance"] = "\n\n".join(paras).strip()
                out.append(current)

        for block in chapter.get("content", []):
            btype, text = block.get("type"), (block.get("text") or "").strip()
            if btype == "subhead":
                m = _SECTION_RE.match(text)
                if m and m.group(1) in _NEGOTIABLE:
                    _flush()
                    current, paras = {
                        "section": m.group(1),
                        "chapter": number,
                        "title": m.group(2).strip(),
                    }, []
                else:
                    # A non-negotiable subhead ends the current section's guidance.
                    _flush()
                    current, paras = None, []
            elif btype == "para" and current is not None:
                paras.append(text)
        _flush()
    return out


@lru_cache(maxsize=1)
def _json_sections_cached() -> tuple[dict, ...]:
    return tuple(_parse_json_sections())


class PlaybookRepository:
    """Read/seed/edit the ``playbook_sections`` table, with a JSON fallback."""

    # ── seeding ──────────────────────────────────────────────────────────────
    def seed_from_json(self) -> int:
        """Seed the negotiable sections from PLAYBOOK.json (idempotent).

        Non-destructive: ``db.seed_playbook_section`` only refreshes rows still
        marked ``source='seed'``, so a reviewer's edits survive a re-seed.
        Returns the number of sections seeded."""
        if not db.init_db():
            return 0
        written = 0
        for s in _json_sections_cached():
            db.seed_playbook_section(s["section"], s["chapter"], s["title"], s["guidance"])
            written += 1
        _log.info("Seeded %d playbook section(s) into SQLite", written)
        return written

    # ── reads ────────────────────────────────────────────────────────────────
    def list_sections(self) -> list[dict]:
        """Every negotiable section, DB-first with a fall back to PLAYBOOK.json."""
        rows = db.list_playbook()
        if rows:
            return rows
        # DB empty/unavailable — parse the JSON so grounding still works.
        return [
            {**s, "source": "seed", "updated_at": None, "updated_by": None}
            for s in _json_sections_cached()
        ]

    def get_section(self, section: str) -> dict | None:
        row = db.get_playbook_section(section)
        if row is not None:
            return row
        for s in _json_sections_cached():
            if s["section"] == section:
                return {**s, "source": "seed", "updated_at": None, "updated_by": None}
        return None

    # ── writes (the editable surface) ────────────────────────────────────────
    def update_section(
        self, section: str, title: str, guidance: str, updated_by: str | None = None
    ) -> bool:
        """Apply a reviewer edit; returns True if the section exists and was saved."""
        return db.update_playbook_section(section, title, guidance, updated_by)

    # ── grounding ────────────────────────────────────────────────────────────
    def render_for_prompt(self) -> str:
        """Render the sections into the block injected into the redline prompt.

        This is what turns the playbook from a human-only document into the text
        the model actually maps redlines against — edit a section and the next
        run reflects it.
        """
        sections = self.list_sections()
        if not sections:
            return ""
        lines = [
            "NORTHGATE PLAYBOOK v4 — the desk's authoritative negotiating positions.",
            "Map every counterparty deviation to exactly one section below and cite it "
            "(e.g. \"Playbook §3.1\"). If a deviation matches no section here, mark it "
            "off_playbook and escalate.",
            "",
        ]
        for s in sections:
            lines.append(f"§{s['section']} — {s['title']}")
            lines.append(s["guidance"])
            lines.append("")
        return "\n".join(lines).strip()


# Module-level singleton — mirrors ``repository.repo`` and the single TriageService.
playbook_repo = PlaybookRepository()
