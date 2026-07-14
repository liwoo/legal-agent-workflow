"""SQLite persistence — the durable store behind the FastAPI layer.

The triage workflow is pure/in-memory, but two things are worth surviving a
restart: the serialised triage *results* the console reads, and the *reviewer
decisions* a human makes at the human-gate. This module keeps both in a small
SQLite database so the queues repopulate instantly on boot and decisions aren't
lost when the API process cycles.

Like ``observability.py``, this is **resilient by design**: every call is wrapped
so a missing/locked database never takes the API down — it degrades to the
previous in-memory-only behaviour and logs a warning.

Configuration (injected by ``make up`` via ``e2e/stack.env``):

    TRIAGE_DB_PATH=.data/triage.db   # relative to the API working dir (../app/agent)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)
_lock = threading.Lock()  # serialise writes; SQLite is single-writer

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    item_id       TEXT PRIMARY KEY,
    metadata_json TEXT NOT NULL,   -- the intake payload (item_from_metadata schema)
    pdf_path      TEXT,            -- absolute local path the ingest node reads
    source        TEXT NOT NULL DEFAULT 'seed',  -- seed | user
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS triage_results (
    item_id     TEXT PRIMARY KEY,
    detail_json TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS triage_outcomes (
    item_id             TEXT PRIMARY KEY,
    end_state           TEXT,
    score               INTEGER,
    signer              TEXT,
    gate_count          INTEGER,
    blocking            INTEGER,
    redline_count       INTEGER,
    obligation_count    INTEGER,
    recommended_action  TEXT,
    outcome_json        TEXT,
    updated_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviewer_decisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id    TEXT NOT NULL,
    decision   TEXT NOT NULL,
    note       TEXT,
    decided_at TEXT NOT NULL
);
"""


def _db_path() -> Path:
    return Path(os.getenv("TRIAGE_DB_PATH", ".data/triage.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> bool:
    """Create the database and tables if they don't exist. Idempotent.

    Returns ``True`` on success, ``False`` if the store is unavailable (in which
    case the service falls back to holding everything in memory only)."""
    try:
        with _lock, _connect() as conn:
            conn.executescript(_SCHEMA)
        _log.info("SQLite ready → %s", _db_path())
        return True
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("SQLite unavailable (%s); persistence disabled", exc)
        return False


# ── contracts (the intake register — seeded examples + user-created) ─────────
def upsert_contract(
    item_id: str,
    metadata: dict,
    pdf_path: str | None = None,
    source: str = "seed",
) -> None:
    """Insert or update a contract's intake record.

    Seeded examples are written with ``source='seed'`` and never clobber a
    user-created row; user contracts use ``source='user'``.
    """
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO contracts (item_id, metadata_json, pdf_path, source, created_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET "
                "metadata_json = excluded.metadata_json, "
                "pdf_path = COALESCE(excluded.pdf_path, contracts.pdf_path), "
                "source = excluded.source",
                (item_id, json.dumps(metadata), pdf_path, source, _now()),
            )
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("upsert_contract(%s) failed: %s", item_id, exc)


def contract_exists(item_id: str) -> bool:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM contracts WHERE item_id = ?", (item_id,)
            ).fetchone()
        return row is not None
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("contract_exists(%s) failed: %s", item_id, exc)
        return False


def get_contract(item_id: str) -> dict | None:
    """Return one contract's ``{metadata, pdf_path, source}`` or None."""
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT metadata_json, pdf_path, source FROM contracts WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "metadata": json.loads(row["metadata_json"]),
            "pdf_path": row["pdf_path"],
            "source": row["source"],
        }
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("get_contract(%s) failed: %s", item_id, exc)
        return None


def list_contracts() -> list[dict]:
    """Return every contract's ``{metadata, pdf_path, source}``, insertion order."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT metadata_json, pdf_path, source FROM contracts ORDER BY created_at, item_id"
            ).fetchall()
        return [
            {
                "metadata": json.loads(row["metadata_json"]),
                "pdf_path": row["pdf_path"],
                "source": row["source"],
            }
            for row in rows
        ]
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("list_contracts failed: %s", exc)
        return []


# ── triage outcomes (written by the agent's terminal nodes) ──────────────────
def save_outcome(item_id: str, outcome: dict) -> None:
    """Upsert the compact outcome a terminal node produced.

    Called from the workflow's finalisation (``executors.finalize``) so the
    agent itself — not just the API layer — records what it decided."""
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO triage_outcomes (item_id, end_state, score, signer, gate_count, "
                "blocking, redline_count, obligation_count, recommended_action, outcome_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET "
                "end_state = excluded.end_state, score = excluded.score, signer = excluded.signer, "
                "gate_count = excluded.gate_count, blocking = excluded.blocking, "
                "redline_count = excluded.redline_count, obligation_count = excluded.obligation_count, "
                "recommended_action = excluded.recommended_action, outcome_json = excluded.outcome_json, "
                "updated_at = excluded.updated_at",
                (
                    item_id,
                    outcome.get("end_state"),
                    outcome.get("score"),
                    outcome.get("signer"),
                    outcome.get("gate_count"),
                    1 if outcome.get("blocking") else 0,
                    outcome.get("redline_count"),
                    outcome.get("obligation_count"),
                    outcome.get("recommended_action"),
                    json.dumps(outcome),
                    _now(),
                ),
            )
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("save_outcome(%s) failed: %s", item_id, exc)


def get_outcome(item_id: str) -> dict | None:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT outcome_json FROM triage_outcomes WHERE item_id = ?", (item_id,)
            ).fetchone()
        return json.loads(row["outcome_json"]) if row else None
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("get_outcome(%s) failed: %s", item_id, exc)
        return None


def save_result(item_id: str, detail: dict) -> None:
    """Upsert the serialised ContractDetail for an item."""
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO triage_results (item_id, detail_json, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET "
                "detail_json = excluded.detail_json, updated_at = excluded.updated_at",
                (item_id, json.dumps(detail), _now()),
            )
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("save_result(%s) failed: %s", item_id, exc)


def load_results() -> dict[str, dict]:
    """Return all persisted results keyed by item id (empty if none/unavailable)."""
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT item_id, detail_json FROM triage_results").fetchall()
        return {row["item_id"]: json.loads(row["detail_json"]) for row in rows}
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("load_results failed: %s", exc)
        return {}


def save_decision(item_id: str, decision: str, note: str | None) -> None:
    """Append a reviewer's human-gate decision to the audit log."""
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO reviewer_decisions (item_id, decision, note, decided_at) "
                "VALUES (?, ?, ?, ?)",
                (item_id, decision, note, _now()),
            )
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("save_decision(%s) failed: %s", item_id, exc)


def list_decisions(item_id: str | None = None) -> list[dict]:
    """Return reviewer decisions, newest first, optionally filtered by item."""
    try:
        with _connect() as conn:
            if item_id is None:
                rows = conn.execute(
                    "SELECT item_id, decision, note, decided_at FROM reviewer_decisions "
                    "ORDER BY id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT item_id, decision, note, decided_at FROM reviewer_decisions "
                    "WHERE item_id = ? ORDER BY id DESC",
                    (item_id,),
                ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("list_decisions failed: %s", exc)
        return []
