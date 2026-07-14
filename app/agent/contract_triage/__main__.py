"""Console entrypoints.

    python -m contract_triage            # run the FastAPI backend (uvicorn)
    python -m contract_triage.devui_app  # run the DevUI
"""

from __future__ import annotations

import os


def run_api() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("contract_triage.io.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_api()
