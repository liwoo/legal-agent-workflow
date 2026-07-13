"""Object storage — the S3-compatible blob store behind the contract documents.

Every inbox item arrives with an intake PDF. Rather than serve those off the
local filesystem, the API keeps them in a MinIO bucket and hands the browser a
short-lived *presigned* URL, exactly as a production system would with S3. The
Aspire AppHost runs an ephemeral (volume-less) MinIO container, so the store is
seeded fresh from ``../test`` on every boot.

Resilient by design (see ``observability.py`` / ``db.py``): if MinIO is not
configured or the ``minio`` SDK is missing, every call degrades to a no-op and
the console simply shows no document link — the rest of the API is unaffected.

Configuration (injected by the Aspire AppHost):

    CONTRACT_STORE_ENDPOINT=localhost:9092      # host:port, no scheme
    CONTRACT_STORE_ACCESS_KEY=contract-store
    CONTRACT_STORE_SECRET_KEY=contract-store-secret
    CONTRACT_STORE_BUCKET=contracts
    CONTRACT_STORE_SECURE=false                 # http, not https
    CONTRACT_STORE_SEED_DIR=../test             # dir of <ITEM_ID>/*.pdf to seed
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from pathlib import Path

_log = logging.getLogger(__name__)

_PRESIGN_TTL = timedelta(hours=1)


def _truthy(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class ContractStore:
    """Thin wrapper over a MinIO/S3 bucket of contract intake documents.

    Lazily connects on first use; ``self._client is None`` means "not configured
    or unavailable", and every public method treats that as a graceful no-op."""

    def __init__(self) -> None:
        self._client = None
        self._bucket = os.getenv("CONTRACT_STORE_BUCKET", "contracts")
        self._connected = False

    # ── connection ───────────────────────────────────────────────────────────
    def _connect(self) -> None:
        endpoint = os.getenv("CONTRACT_STORE_ENDPOINT")
        if not endpoint:
            return
        try:
            from minio import Minio
        except Exception as exc:  # pragma: no cover - optional dep
            _log.warning("CONTRACT_STORE_ENDPOINT set but 'minio' SDK missing (%s)", exc)
            return
        try:
            self._client = Minio(
                endpoint,
                access_key=os.getenv("CONTRACT_STORE_ACCESS_KEY", ""),
                secret_key=os.getenv("CONTRACT_STORE_SECRET_KEY", ""),
                secure=_truthy("CONTRACT_STORE_SECURE"),
            )
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
            _log.info("Contract store ready → %s/%s", endpoint, self._bucket)
        except Exception as exc:  # pragma: no cover - defensive
            _log.warning("Contract store unavailable (%s); documents disabled", exc)
            self._client = None

    def connect(self) -> bool:
        """Establish the connection + bucket once. Returns True when usable."""
        if not self._connected:
            self._connect()
            self._connected = True
        return self._client is not None

    # ── keys ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _key(item_id: str) -> str:
        return f"{item_id}/intake.pdf"

    # ── seeding ──────────────────────────────────────────────────────────────
    def seed(self) -> int:
        """Upload the intake PDFs under CONTRACT_STORE_SEED_DIR (idempotent).

        Layout expected: ``<seed_dir>/<ITEM_ID>/*.pdf``. Returns the number of
        objects uploaded this call (0 if already seeded or store unavailable)."""
        if not self.connect():
            return 0
        seed_dir = Path(os.getenv("CONTRACT_STORE_SEED_DIR", "../test"))
        if not seed_dir.is_dir():
            _log.warning("seed dir %s not found; nothing to seed", seed_dir)
            return 0
        uploaded = 0
        for item_dir in sorted(p for p in seed_dir.iterdir() if p.is_dir()):
            pdf = next(iter(sorted(item_dir.glob("*.pdf"))), None)
            if pdf is None:
                continue
            key = self._key(item_dir.name)
            try:
                # Skip if already present (ephemeral store, but re-seed is cheap).
                self._client.stat_object(self._bucket, key)
                continue
            except Exception:
                pass
            try:
                self._client.fput_object(
                    self._bucket, key, str(pdf), content_type="application/pdf"
                )
                uploaded += 1
            except Exception as exc:  # pragma: no cover - defensive
                _log.warning("seed of %s failed: %s", key, exc)
        if uploaded:
            _log.info("Seeded %d contract document(s) into %s", uploaded, self._bucket)
        return uploaded

    # ── access ───────────────────────────────────────────────────────────────
    def presigned_url(self, item_id: str) -> str | None:
        """A short-lived GET URL for an item's intake PDF, or None if absent."""
        if not self.connect():
            return None
        key = self._key(item_id)
        try:
            self._client.stat_object(self._bucket, key)
            return self._client.presigned_get_object(self._bucket, key, expires=_PRESIGN_TTL)
        except Exception:
            return None


# Module-level singleton — mirrors the single TriageService the API holds.
store = ContractStore()
