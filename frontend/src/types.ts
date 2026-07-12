/**
 * Shared TypeScript types for the Northgate Contract Triage frontend.
 * Mirrors the Pydantic models in models.py and the API contract the
 * (fictional, offline-first) backend implements.
 */

export type Queue = "pending" | "approved" | "quarantined";

export type AiStatus = "untriaged" | "processing" | "triaged";

export type EndState =
  | "signed_no_edits"
  | "signed_desk_edits"
  | "signed_with_deviation"
  | "escalated"
  | "blocked"
  | "more_info_needed"
  | "business_decision"
  | "declined"
  | null;

export interface Classification {
  document_family: string;
  paper_source: string;
  direction: string;
  data_flags: string[];
  prior_contract_ids: string[];
  signatory_level: string;
  value_gbp: number | null;
  deadline: string | null;
}

export interface GateCheck {
  gate: string;
  status: "passed" | "action_required" | "blocked";
  findings: string[];
  required_actions: string[];
  legal_basis: string[];
}

export interface Redline {
  clause_ref: string | null;
  description: string;
  playbook_section: string | null;
  tier: string;
  action: string;
  legal_basis: string[];
}

export interface ForwardObligation {
  type: string;
  note: string;
  due: string | null;
}

export interface TimelineEvent {
  at: string;
  label: string;
  detail?: string;
  kind?: "info" | "warning" | "critical" | "success";
}

export interface Interrupt {
  reason: string;
  owner: string;
  sla: string | null;
  request_id: string | null;
}

export interface ContractSummary {
  id: string;
  name: string;
  counterparty: string;
  document_family: string;
  paper_source: string;
  direction: string;
  received_at: string;
  sender_role: string;
  sender_ask: string;
  what_arrived: string;
  deadline: string | null;
  prior_contract_ids: string[];
  ai_status: AiStatus;
  score: number | null;
  end_state: EndState;
  queue: Queue;
}

export interface ContractDetail extends ContractSummary {
  classification: Classification | null;
  gate_checks: GateCheck[];
  redlines: Redline[];
  forward_obligations: ForwardObligation[];
  explanation: string | null;
  recommended_action: string | null;
  interrupt: Interrupt | null;
  path_node_ids: string[];
  timeline: TimelineEvent[];
}

export type WorkflowNodeType =
  | "terminal"
  | "node"
  | "router"
  | "validator"
  | "fan"
  | "reduce"
  | "hitl";

export interface WorkflowNode {
  id: string;
  label: string;
  type: WorkflowNodeType;
}

export interface WorkflowEdge {
  source: string;
  target: string;
  label?: string;
  kind?: "solid" | "dashed";
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface Policy {
  id: string;
  title: string;
  summary: string;
}

export type ResolveDecision = "resolved" | "declined" | "escalated";

export interface ResolveRequest {
  decision: ResolveDecision;
  note?: string;
}
