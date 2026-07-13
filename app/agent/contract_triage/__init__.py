"""Northgate contract-triage agent — a Microsoft Agent Framework workflow that
implements the abstract agent-graph (docs/agent-graph.mmd)."""

from .state import TriageRequest, TriageState
from .workflow import build_workflow

# Module-level entity so DevUI's directory discovery (`devui ./contract_triage`)
# can find the workflow — it looks for a top-level `workflow` (or `agent`) object.
# The in-memory entrypoint (`python -m contract_triage.devui_app`) does not need
# this, but the documented CLI path does.
workflow = build_workflow()

__all__ = ["TriageRequest", "TriageState", "build_workflow", "workflow"]
