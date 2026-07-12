import type { Policy } from "@/src/types";

/** Fixture for GET /api/policies. */
export const policiesFixture: Policy[] = [
  {
    id: "PLAYBOOK",
    title: "Contract Playbook v4",
    summary:
      "The desk's standing negotiating positions across NDAs, order forms, DPAs and supplier agreements — a standard → fallback → refusal ladder for every clause family, from liability caps to termination-for-convenience mechanics. This is the primary reference redlines are mapped against.",
  },
  {
    id: "POL-PRIV-001",
    title: "Data Protection & Privacy Policy",
    summary:
      "Governs when a DPA is required (Art. 28(3)), when a DPIA must complete before signature (Art. 35, high-risk or special-category processing), and the safeguards required for cross-border transfers (Art. 46 — SCCs or the UK IDTA plus a transfer impact assessment).",
  },
  {
    id: "POL-SEC-011",
    title: "Third-Party Security Policy",
    summary:
      "Sets minimum security posture for counterparties with systems access to Northgate data — encryption at rest/in transit, incident notification windows, and audit rights. Feeds the statutory/security validator during triage.",
  },
  {
    id: "POL-FIN-007",
    title: "Insurance & Financial Exposure Policy",
    summary:
      "Sets minimum professional indemnity and cyber cover thresholds relative to contract value, and the finance sign-off threshold above which Legal Director + COO + CFO escalation (Ch.10) is required regardless of playbook fit.",
  },
  {
    id: "POL-HR-003",
    title: "Worker Status & Contractor Policy",
    summary:
      "IR35 and worker-status screening for contractor and SOW-based engagements, including the new-clause review required when a statement of work introduces terms (e.g. IP in AI-generated deliverables) not contemplated by the parent framework agreement.",
  },
  {
    id: "POL-LGL-002",
    title: "Signature Authority Policy",
    summary:
      "Value-band routing for who may execute a contract — Legal Counsel, COO, CFO, or Board — and the escalation tiers (Ch.10) for deviations, refusal-point concessions, uncapped liability, exclusivity, or governing-law departures.",
  },
];
