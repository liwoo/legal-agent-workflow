"""Graph wiring — how the executors connect.

``workflow`` builds the Agent-Framework ``Workflow`` (nodes + solid/switch-case/
fan-out edges, a 1:1 wiring of docs/agent-graph.mmd); ``graph_spec`` is the static
node/edge description the frontend renders (GET /api/workflow/graph). Both speak
the same executor ids, so a run's ``trace`` highlights the exact route taken.
"""

from __future__ import annotations

from . import graph_spec
from .workflow import build_workflow

__all__ = ["build_workflow", "graph_spec"]
