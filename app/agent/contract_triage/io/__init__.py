"""IO layer — the app's boundaries: the HTTP surface and every external system.

``api`` is the FastAPI app (the REST the console consumes; its ASGI target is
``contract_triage.io.api:app``). The rest is persistence / external systems:
``db`` (SQLite results/decisions), ``repository`` (the contracts register),
``storage`` (S3/MinIO documents), ``playbook`` (the grounded negotiating
positions), ``pdf`` (intake ingestion), ``data`` (the in-code inbox seed) and
``observability`` (OTEL → Langfuse).

Each module is resilient by design: a missing store degrades to a no-op rather
than taking the API down. Import the submodules directly (``from .io import db``).
"""
