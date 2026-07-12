"""Static description of the triage graph for the frontend (GET /api/workflow/graph).

Node ids match the executor ids in executors.py so a contract's ``trace``
(``path_node_ids``) highlights the exact route it took through this graph.
"""

from __future__ import annotations

WORKFLOW_NODES: list[dict] = [
    {"id": "START", "label": "Start", "type": "terminal"},
    {"id": "ingest", "label": "Ingest", "type": "node"},
    {"id": "classify", "label": "Classify", "type": "node"},
    {"id": "intake_gate", "label": "Intake gate", "type": "router"},
    {"id": "triage", "label": "Triage (fast path?)", "type": "router"},
    {"id": "cheap_guard", "label": "Cheap guard", "type": "node"},
    {"id": "guard_check", "label": "Guard clean?", "type": "router"},
    {"id": "fanout", "label": "Fan-out validators", "type": "fan"},
    {"id": "dpa", "label": "DPA validator", "type": "validator"},
    {"id": "statutory", "label": "Statutory validator", "type": "validator"},
    {"id": "finance", "label": "Finance validator", "type": "validator"},
    {"id": "gather", "label": "Gather", "type": "reduce"},
    {"id": "gate_outcome", "label": "Gate outcome", "type": "router"},
    {"id": "negotiability", "label": "Negotiable?", "type": "router"},
    {"id": "gap_analysis", "label": "Gap analysis", "type": "node"},
    {"id": "gap_check", "label": "Refusal hit?", "type": "router"},
    {"id": "map_redline", "label": "Map redline", "type": "node"},
    {"id": "disposition", "label": "Disposition", "type": "router"},
    {"id": "hold", "label": "Hold position", "type": "node"},
    {"id": "fallback", "label": "Apply fallback", "type": "node"},
    {"id": "strike", "label": "Strike + substitute", "type": "node"},
    {"id": "loop_control", "label": "Loop control", "type": "router"},
    {"id": "approval", "label": "Approval (value band)", "type": "router"},
    {"id": "execute", "label": "Execute (sign)", "type": "node"},
    {"id": "side_effects", "label": "Side effects", "type": "node"},
    {"id": "SIGNED", "label": "Signed", "type": "terminal"},
    {"id": "human_gate", "label": "Human gate", "type": "hitl"},
    {"id": "DECLINED", "label": "Declined", "type": "terminal"},
    {"id": "ESCALATED", "label": "Escalated", "type": "terminal"},
]

WORKFLOW_EDGES: list[dict] = [
    {"source": "START", "target": "ingest"},
    {"source": "ingest", "target": "classify"},
    {"source": "classify", "target": "intake_gate"},
    {"source": "intake_gate", "target": "human_gate", "label": "no draft / blocker", "kind": "solid"},
    {"source": "intake_gate", "target": "triage", "label": "ok"},
    {"source": "triage", "target": "cheap_guard", "label": "our template"},
    {"source": "triage", "target": "fanout", "label": "redlined / their paper"},
    {"source": "cheap_guard", "target": "guard_check"},
    {"source": "guard_check", "target": "approval", "label": "clean"},
    {"source": "guard_check", "target": "fanout", "label": "needs gates"},
    {"source": "fanout", "target": "dpa", "kind": "dashed", "label": "parallel"},
    {"source": "fanout", "target": "statutory", "kind": "dashed", "label": "parallel"},
    {"source": "fanout", "target": "finance", "kind": "dashed", "label": "parallel"},
    {"source": "dpa", "target": "gather"},
    {"source": "statutory", "target": "gather"},
    {"source": "finance", "target": "gather"},
    {"source": "gather", "target": "gate_outcome"},
    {"source": "gate_outcome", "target": "human_gate", "label": "blocker"},
    {"source": "gate_outcome", "target": "negotiability", "label": "clear"},
    {"source": "negotiability", "target": "gap_analysis", "label": "non-negotiable"},
    {"source": "negotiability", "target": "map_redline", "label": "negotiable"},
    {"source": "gap_analysis", "target": "gap_check"},
    {"source": "gap_check", "target": "human_gate", "label": "refusal"},
    {"source": "gap_check", "target": "approval", "label": "ok"},
    {"source": "map_redline", "target": "disposition"},
    {"source": "disposition", "target": "hold", "label": "standard"},
    {"source": "disposition", "target": "fallback", "label": "fallback"},
    {"source": "disposition", "target": "strike", "label": "banned"},
    {"source": "disposition", "target": "human_gate", "label": "refusal / novel"},
    {"source": "hold", "target": "loop_control"},
    {"source": "fallback", "target": "loop_control"},
    {"source": "strike", "target": "loop_control"},
    {"source": "loop_control", "target": "map_redline", "label": "unresolved"},
    {"source": "loop_control", "target": "human_gate", "label": "max iter"},
    {"source": "loop_control", "target": "approval", "label": "resolved"},
    {"source": "approval", "target": "execute"},
    {"source": "execute", "target": "side_effects"},
    {"source": "side_effects", "target": "SIGNED"},
    {"source": "human_gate", "target": "approval", "kind": "dashed", "label": "resolved"},
    {"source": "human_gate", "target": "DECLINED", "kind": "dashed", "label": "declined"},
    {"source": "human_gate", "target": "ESCALATED", "kind": "dashed", "label": "timeout / escalate"},
]


def graph() -> dict:
    return {"nodes": WORKFLOW_NODES, "edges": WORKFLOW_EDGES}
