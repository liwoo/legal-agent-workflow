"""Contract repository — the SQLite-backed register of intake items.

The workflow used to read its inbox straight from the hard-coded ``data.INBOX``
list. This repository makes the ``contracts`` table (see ``db.py``) the single
source of truth instead. The inbox ships **empty** — reviewers add contracts
through the "New Contract" flow, which *inserts* them here — unless
``SEED_EXAMPLES=1`` asks for the ten canonical demo contracts on boot. Both the
FastAPI layer (which the console reads) and the agent workflow go through this
one repository, so a contract created in the UI is immediately visible to the
graph and vice-versa.

``get_item`` still resolves a known demo id from the in-code ``data`` seed as a
fallback (used by tests and by-id lookups), but ``list_items`` — what fills the
inbox — is purely what the register holds.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from . import data, db
from .data import item_from_metadata
from .models import InboxItem

_log = logging.getLogger(__name__)


def _item_to_metadata(item: InboxItem) -> dict:
    """Serialise a seed :class:`InboxItem` back into the intake schema."""
    return {
        "id": item.id,
        "name": f"{item.counterparty.name}",
        "counterparty": item.counterparty.name,
        "sector": item.counterparty.sector,
        "is_public_body": item.counterparty.is_public_body,
        "is_regulated": item.counterparty.is_regulated,
        "jurisdiction": item.counterparty.jurisdiction,
        "received_at": item.received_at.isoformat(),
        "received_from": item.sender_role,
        "summary": item.what_arrived,
        "senders_ask": item.sender_ask,
        "related_contracts": list(item.related_contracts),
    }


class ContractRepository:
    """CRUD over the ``contracts`` table, returning domain ``InboxItem`` objects."""

    # ── seeding ──────────────────────────────────────────────────────────────
    def seed_examples(self) -> int:
        """Persist the canonical example inbox into SQLite (idempotent).

        Each item carries its prior-contract chain (``data.PRIOR_CHAINS``) so the
        DB row is self-contained and the classifier's inherited-flag logic works
        without consulting the in-code lookup. Returns the number written."""
        if not db.init_db():
            return 0
        written = 0
        for item in data.INBOX:
            meta = _item_to_metadata(item)
            meta["related_contracts"] = data.PRIOR_CHAINS.get(item.id, [])
            db.upsert_contract(item.id, meta, pdf_path=None, source="seed")
            written += 1
        _log.info("Seeded %d example contract(s) into SQLite", written)
        return written

    # ── reads ────────────────────────────────────────────────────────────────
    def list_items(self) -> list[InboxItem]:
        # The register is the single source of truth; an empty register is an
        # empty inbox. (No fallback to the in-code demo seed — the app ships blank
        # unless SEED_EXAMPLES=1 populated the table on boot.)
        rows = db.list_contracts()
        return [item_from_metadata(r["metadata"], r["pdf_path"]) for r in rows]

    def get_item(self, item_id: str) -> InboxItem | None:
        row = db.get_contract(item_id)
        if row is None:
            return data.get_item(item_id)  # fall back to the in-code seed
        return item_from_metadata(row["metadata"], row["pdf_path"])

    def pdf_path(self, item_id: str) -> str | None:
        row = db.get_contract(item_id)
        return row["pdf_path"] if row else None

    # ── writes (the "New Contract" flow) ─────────────────────────────────────
    def create(self, metadata: dict, pdf_path: str | None = None) -> InboxItem:
        """Insert a reviewer-created contract and return its domain item."""
        item_id = metadata.get("id") or self.next_id()
        metadata = {**metadata, "id": item_id}
        db.upsert_contract(item_id, metadata, pdf_path=pdf_path, source="user")
        return item_from_metadata(metadata, pdf_path)

    def next_id(self) -> str:
        """Allocate the next free ``CR-<year>-NNN`` id across seed + user rows."""
        year = datetime.now(timezone.utc).year
        prefix = f"CR-{year}-"
        existing = {i.id for i in self.list_items()}
        seq = 1
        for cid in existing:
            m = re.fullmatch(rf"CR-{year}-(\d+)", cid)
            if m:
                seq = max(seq, int(m.group(1)) + 1)
        return f"{prefix}{seq:03d}"


# Module-level singleton — mirrors the single TriageService / store the API holds.
repo = ContractRepository()
