"""SQLite persistence — the durable store behind the FastAPI layer.

The triage workflow is pure/in-memory, but two things are worth surviving a
restart: the serialised triage *results* the console reads, and the *reviewer
decisions* a human makes at the human-gate. This module keeps both in a small
SQLite database so the queues repopulate instantly on boot and decisions aren't
lost when the API process cycles.

Like ``observability.py``, this is **resilient by design**: every call is wrapped
so a missing/locked database never takes the API down — it degrades to the
previous in-memory-only behaviour and logs a warning.

Configuration (injected by the Aspire AppHost):

    TRIAGE_DB_PATH=.data/triage.db   # relative to the API working dir (../agent)
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
CREATE TABLE IF NOT EXISTS triage_results (
    item_id     TEXT PRIMARY KEY,
    detail_json TEXT NOT NULL,
    updated_at  TEXT NOT NULL
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
