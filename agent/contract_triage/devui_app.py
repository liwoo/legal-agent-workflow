"""DevUI entrypoint — the Microsoft Agent Framework developer UI.

Registers the contract-triage workflow (and, when an LLM is configured, the
standalone helper agents) so you can run, inspect, and step through them — plus
drive the human-gate interrupt/resume — at http://localhost:8080.

Run directly:   python -m contract_triage.devui_app
Or via the CLI: devui ./contract_triage --port 8080
"""

from __future__ import annotations

import os

from agent_framework.devui import serve

from . import agents
from .workflow import build_workflow


def main() -> None:
    workflow = build_workflow()
    entities = [workflow, *agents.build_agents()]
    port = int(os.getenv("DEVUI_PORT", os.getenv("PORT", "8080")))
    host = os.getenv("DEVUI_HOST", "127.0.0.1")
    serve(
        entities=entities,
        port=port,
        host=host,
        auto_open=os.getenv("DEVUI_AUTO_OPEN", "0") == "1",
        ui_enabled=True,
        auth_enabled=False,  # local dev
        cors_origins=["*"],
    )


if __name__ == "__main__":
    main()
