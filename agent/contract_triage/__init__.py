"""Northgate contract-triage agent — a Microsoft Agent Framework workflow that
implements the abstract agent-graph (../../agent-graph.mmd)."""

from .state import TriageRequest, TriageState
from .workflow import build_workflow

__all__ = ["TriageRequest", "TriageState", "build_workflow"]
