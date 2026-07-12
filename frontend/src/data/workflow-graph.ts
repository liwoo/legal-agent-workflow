import type { WorkflowEdge, WorkflowGraph, WorkflowNode, WorkflowNodeType } from "@/src/types";

/**
 * Fixture for GET /api/workflow/graph — mirrors agent-graph.mmd exactly
 * (node ids, edge routing, dashed = fan-out / human-in-the-loop resume-exit).
 *
 * Layout: hand-placed x/y (no dagre dependency), laid out top-to-bottom
 * following the flowchart's structure — intake at the top, the fan-out /
 * validator tier in the middle band, the redline loop to the right, and
 * terminals at the bottom.
 */

interface LayoutNode extends WorkflowNode {
  x: number;
  y: number;
}

const COL = 180;
const ROW = 110;

export const workflowNodesLayout: LayoutNode[] = [
  { id: "START", label: "START", type: "terminal", x: 3 * COL, y: 0 * ROW },
  { id: "ingest", label: "Ingest", type: "node", x: 3 * COL, y: 1 * ROW },
  { id: "classify", label: "Classify", type: "node", x: 3 * COL, y: 2 * ROW },
  { id: "intake_gate", label: "Intake gate", type: "router", x: 3 * COL, y: 3 * ROW },

  { id: "human_gate", label: "Human review", type: "hitl", x: 6 * COL, y: 3.5 * ROW },

  { id: "triage", label: "Triage", type: "router", x: 3 * COL, y: 4 * ROW },
  { id: "cheap_guard", label: "Cheap guard", type: "node", x: 1.4 * COL, y: 5 * ROW },
  { id: "guard_check", label: "Guard check", type: "router", x: 1.4 * COL, y: 6 * ROW },

  { id: "fanout", label: "Fan-out", type: "fan", x: 3 * COL, y: 6 * ROW },
  { id: "dpa", label: "DPA validator", type: "validator", x: 1.6 * COL, y: 7 * ROW },
  { id: "statutory", label: "Statutory validator", type: "validator", x: 3 * COL, y: 7 * ROW },
  { id: "finance", label: "Finance validator", type: "validator", x: 4.4 * COL, y: 7 * ROW },
  { id: "gather", label: "Gather", type: "reduce", x: 3 * COL, y: 8 * ROW },

  { id: "gate_outcome", label: "Gate outcome", type: "router", x: 3 * COL, y: 9 * ROW },
  { id: "negotiability", label: "Negotiability", type: "router", x: 3 * COL, y: 10 * ROW },

  { id: "gap_analysis", label: "Gap analysis", type: "node", x: 1.2 * COL, y: 11 * ROW },
  { id: "gap_check", label: "Gap check", type: "router", x: 1.2 * COL, y: 12 * ROW },

  { id: "map_redline", label: "Map redline", type: "node", x: 4.6 * COL, y: 11 * ROW },
  { id: "disposition", label: "Disposition", type: "router", x: 4.6 * COL, y: 12 * ROW },
  { id: "hold", label: "Hold position", type: "node", x: 3.6 * COL, y: 13 * ROW },
  { id: "fallback", label: "Apply fallback", type: "node", x: 4.6 * COL, y: 13 * ROW },
  { id: "strike", label: "Strike clause", type: "node", x: 5.6 * COL, y: 13 * ROW },
  { id: "loop_control", label: "Loop control", type: "router", x: 4.6 * COL, y: 14 * ROW },

  { id: "approval", label: "Approval", type: "router", x: 3 * COL, y: 15 * ROW },
  { id: "execute", label: "Execute", type: "node", x: 3 * COL, y: 16 * ROW },
  { id: "side_effects", label: "Side effects", type: "node", x: 3 * COL, y: 17 * ROW },
  { id: "SIGNED", label: "SIGNED", type: "terminal", x: 3 * COL, y: 18 * ROW },

  { id: "DECLINED", label: "DECLINED", type: "terminal", x: 6 * COL, y: 16 * ROW },
  { id: "ESCALATED", label: "ESCALATED", type: "terminal", x: 6 * COL, y: 18 * ROW },
];

export const workflowNodes: WorkflowNode[] = workflowNodesLayout.map(({ id, label, type }) => ({
  id,
  label,
  type,
}));

export const workflowEdges: WorkflowEdge[] = [
  { source: "START", target: "ingest" },
  { source: "ingest", target: "classify" },
  { source: "classify", target: "intake_gate" },

  { source: "intake_gate", target: "human_gate", label: "no draft" },
  { source: "intake_gate", target: "triage", label: "ok" },

  { source: "triage", target: "cheap_guard", label: "our template" },
  { source: "triage", target: "fanout", label: "redlined/their paper" },

  { source: "cheap_guard", target: "guard_check" },
  { source: "guard_check", target: "approval", label: "clean" },
  { source: "guard_check", target: "fanout", label: "issues" },

  { source: "fanout", target: "dpa", kind: "dashed", label: "parallel" },
  { source: "fanout", target: "statutory", kind: "dashed", label: "parallel" },
  { source: "fanout", target: "finance", kind: "dashed", label: "parallel" },
  { source: "dpa", target: "gather" },
  { source: "statutory", target: "gather" },
  { source: "finance", target: "gather" },

  { source: "gather", target: "gate_outcome" },
  { source: "gate_outcome", target: "human_gate", label: "blocker" },
  { source: "gate_outcome", target: "negotiability", label: "clear" },

  { source: "negotiability", target: "gap_analysis", label: "non-negotiable" },
  { source: "negotiability", target: "map_redline", label: "negotiable" },

  { source: "gap_analysis", target: "gap_check" },
  { source: "gap_check", target: "human_gate", label: "refusal" },
  { source: "gap_check", target: "approval", label: "ok" },

  { source: "map_redline", target: "disposition" },
  { source: "disposition", target: "hold" },
  { source: "disposition", target: "fallback" },
  { source: "disposition", target: "strike" },
  { source: "disposition", target: "human_gate", label: "refusal/novel" },

  { source: "hold", target: "loop_control" },
  { source: "fallback", target: "loop_control" },
  { source: "strike", target: "loop_control" },

  { source: "loop_control", target: "map_redline", label: "unresolved" },
  { source: "loop_control", target: "human_gate", label: "max iter" },
  { source: "loop_control", target: "approval", label: "resolved" },

  { source: "approval", target: "execute" },
  { source: "execute", target: "side_effects" },
  { source: "side_effects", target: "SIGNED" },

  { source: "human_gate", target: "classify", kind: "dashed", label: "resume" },
  { source: "human_gate", target: "DECLINED", kind: "dashed", label: "declined" },
  { source: "human_gate", target: "ESCALATED", kind: "dashed", label: "timeout" },
];

export const workflowGraphFixture: WorkflowGraph = {
  nodes: workflowNodes,
  edges: workflowEdges,
};

/** Semantic legend colors by node type — mirrors agent-graph.mmd classDef palette. */
export const workflowNodeColors: Record<WorkflowNodeType, { bg: string; border: string; text: string }> = {
  terminal: { bg: "#111827", border: "#111827", text: "#f9fafb" },
  node: { bg: "#dbeafe", border: "#2563eb", text: "#1e3a5f" },
  router: { bg: "#fef9c3", border: "#ca8a04", text: "#5c4a03" },
  validator: { bg: "#ede9fe", border: "#7c3aed", text: "#3b2a63" },
  fan: { bg: "#e0f2fe", border: "#0284c7", text: "#075985" },
  reduce: { bg: "#cffafe", border: "#0891b2", text: "#164e63" },
  hitl: { bg: "#fee2e2", border: "#dc2626", text: "#7f1d1d" },
};
