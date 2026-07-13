"use client";

import * as React from "react";
import { AlertTriangle, CheckCircle2, Clock, FileText, Gavel, ShieldCheck, XCircle } from "lucide-react";

import { ScoreBadge } from "@/src/components/score-badge";
import { StateBadge } from "@/src/components/state-badge";
import { WorkflowGraph } from "@/src/components/workflow-graph";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/src/components/ui/dialog";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { Separator } from "@/src/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/src/components/ui/table";
import { getContract, useContracts } from "@/src/store/contracts";
import { getApiBaseUrl } from "@/src/lib/api";
import { cn, formatDate, formatDateTime, titleCase } from "@/src/lib/utils";
import type { ContractDetail, GateCheck, ResolveDecision } from "@/src/types";

interface ContractDetailModalProps {
  contractId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const GATE_STATUS_VARIANT: Record<GateCheck["status"], "success" | "warning" | "destructive"> = {
  passed: "success",
  action_required: "warning",
  blocked: "destructive",
};

const TIER_VARIANT: Record<string, "secondary" | "warning" | "destructive"> = {
  standard: "secondary",
  fallback_1: "warning",
  fallback_2: "warning",
  refusal_point: "destructive",
  off_playbook: "destructive",
};

export function ContractDetailModal({ contractId, open, onOpenChange }: ContractDetailModalProps) {
  const { resolve } = useContracts();
  const [detail, setDetail] = React.useState<ContractDetail | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [busy, setBusy] = React.useState<ResolveDecision | null>(null);

  React.useEffect(() => {
    if (!open || !contractId) return;
    let cancelled = false;
    setLoading(true);
    setDetail(null);
    void getContract(contractId).then((d) => {
      if (!cancelled) {
        setDetail(d ?? null);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [open, contractId]);

  const onDecision = async (decision: ResolveDecision) => {
    if (!contractId) return;
    setBusy(decision);
    const updated = await resolve(contractId, decision);
    if (updated) setDetail(updated);
    setBusy(null);
  };

  const canAct = detail?.interrupt != null || detail?.queue !== "approved";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-4xl gap-0 overflow-hidden p-0">
        {loading || !detail ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            {loading ? "Loading contract…" : "Contract not found."}
          </div>
        ) : (
          <>
            <DialogHeader className="space-y-3 border-b border-border p-6 pb-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <DialogTitle className="flex items-center gap-2 text-lg">
                    <FileText className="h-4.5 w-4.5 text-muted-foreground" />
                    {detail.counterparty}
                  </DialogTitle>
                  <DialogDescription className="font-mono text-xs">
                    {detail.id} · {titleCase(detail.document_family)} · {titleCase(detail.paper_source)} ·{" "}
                    {titleCase(detail.direction)}
                  </DialogDescription>
                  {detail.document_url ? (
                    // Link to the stable API endpoint, which re-signs a fresh
                    // presigned URL on each open (the embedded one is short-lived).
                    <a
                      href={`${getApiBaseUrl()}/api/contracts/${encodeURIComponent(detail.id)}/document`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      View intake PDF
                    </a>
                  ) : null}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <ScoreBadge score={detail.score} size="lg" />
                  <StateBadge aiStatus={detail.ai_status} endState={detail.end_state} />
                </div>
              </div>
            </DialogHeader>

            <ScrollArea className="max-h-[calc(92vh-13rem)]">
              <div className="space-y-6 p-6">
                {/* Sender ask + recommendation */}
                <section className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">{detail.sender_role}:</span> “{detail.sender_ask}”
                  </p>
                  {detail.explanation ? (
                    <div className="rounded-lg border border-border bg-muted/40 p-4">
                      <p className="text-sm leading-relaxed text-foreground">{detail.explanation}</p>
                      {detail.recommended_action ? (
                        <p className="mt-2 text-sm font-medium text-primary">→ {detail.recommended_action}</p>
                      ) : null}
                    </div>
                  ) : null}
                  {detail.interrupt ? (
                    <div className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                      <span>
                        <span className="font-medium">Paused for human review</span> — {titleCase(detail.interrupt.reason)}.
                        Owner: {detail.interrupt.owner}
                        {detail.interrupt.sla ? ` · SLA ${detail.interrupt.sla}` : ""}.
                      </span>
                    </div>
                  ) : null}
                </section>

                {/* Classification chips */}
                {detail.classification ? (
                  <section className="flex flex-wrap gap-2">
                    {detail.classification.value_gbp != null ? (
                      <Chip label="Value" value={`£${detail.classification.value_gbp.toLocaleString("en-GB")}`} />
                    ) : null}
                    <Chip label="Signatory" value={titleCase(detail.classification.signatory_level)} />
                    {detail.classification.deadline ? (
                      <Chip label="Deadline" value={formatDate(detail.classification.deadline)} />
                    ) : null}
                    {detail.classification.data_flags.map((f) => (
                      <Badge key={f} variant="outline" className="gap-1">
                        <ShieldCheck className="h-3 w-3" />
                        {titleCase(f)}
                      </Badge>
                    ))}
                    {detail.prior_contract_ids.map((p) => (
                      <Badge key={p} variant="secondary" className="font-mono text-[11px]">
                        prior {p}
                      </Badge>
                    ))}
                  </section>
                ) : null}

                {/* Gate checks */}
                {detail.gate_checks.length ? (
                  <Section title="Policy gates" icon={ShieldCheck}>
                    <Table>
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead>Gate</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Findings / actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.gate_checks.map((g, i) => (
                          <TableRow key={i} className="hover:bg-transparent">
                            <TableCell className="align-top font-medium">{titleCase(g.gate)}</TableCell>
                            <TableCell className="align-top">
                              <Badge variant={GATE_STATUS_VARIANT[g.status]}>{titleCase(g.status)}</Badge>
                            </TableCell>
                            <TableCell className="align-top text-sm text-muted-foreground">
                              <ul className="list-disc space-y-1 pl-4">
                                {[...g.findings, ...g.required_actions].map((line, j) => (
                                  <li key={j}>{line}</li>
                                ))}
                              </ul>
                              {g.legal_basis.length ? (
                                <p className="mt-1.5 text-xs text-muted-foreground/80">{g.legal_basis.join(" · ")}</p>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Section>
                ) : null}

                {/* Redlines */}
                {detail.redlines.length ? (
                  <Section title="Redlines mapped to the playbook" icon={Gavel}>
                    <Table>
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead>Clause</TableHead>
                          <TableHead>Section</TableHead>
                          <TableHead>Tier</TableHead>
                          <TableHead>Action</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.redlines.map((r, i) => (
                          <TableRow key={i} className="hover:bg-transparent">
                            <TableCell className="align-top font-medium">{r.clause_ref ?? "—"}</TableCell>
                            <TableCell className="align-top font-mono text-xs text-muted-foreground">
                              {r.playbook_section ? `§${r.playbook_section}` : "off-playbook"}
                            </TableCell>
                            <TableCell className="align-top">
                              <Badge variant={TIER_VARIANT[r.tier] ?? "secondary"}>{titleCase(r.tier)}</Badge>
                            </TableCell>
                            <TableCell className="align-top text-sm text-muted-foreground">{titleCase(r.action)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Section>
                ) : null}

                {/* Forward obligations */}
                {detail.forward_obligations.length ? (
                  <Section title="Forward obligations" icon={Clock}>
                    <ul className="space-y-2">
                      {detail.forward_obligations.map((o, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          <span>
                            {o.note}
                            {o.due ? <span className="text-muted-foreground"> (due {formatDate(o.due)})</span> : null}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Section>
                ) : null}

                {/* Path through the graph */}
                <Section title="Path through the agent graph" icon={FileText}>
                  <WorkflowGraph highlightedNodeIds={detail.path_node_ids} heightClassName="h-[360px]" />
                </Section>

                {/* Timeline */}
                {detail.timeline.length ? (
                  <Section title="Timeline" icon={Clock}>
                    <ol className="space-y-2.5">
                      {detail.timeline.map((e, i) => (
                        <li key={i} className="flex items-start gap-3 text-sm">
                          <span
                            className={cn(
                              "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                              e.kind === "success" && "bg-success",
                              e.kind === "warning" && "bg-warning",
                              e.kind === "critical" && "bg-destructive",
                              (!e.kind || e.kind === "info") && "bg-muted-foreground/50"
                            )}
                          />
                          <span className="flex-1">
                            {e.label}
                            {e.detail ? <span className="text-muted-foreground"> — {e.detail}</span> : null}
                          </span>
                          <span className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(e.at)}</span>
                        </li>
                      ))}
                    </ol>
                  </Section>
                ) : null}
              </div>
            </ScrollArea>

            <Separator />
            <DialogFooter className="gap-2 p-4 sm:justify-between">
              <span className="hidden text-xs text-muted-foreground sm:block">
                Received {formatDate(detail.received_at)} · from {detail.sender_role}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!canAct || busy !== null}
                  onClick={() => onDecision("declined")}
                >
                  <XCircle className="mr-1.5 h-4 w-4" />
                  Reject
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!canAct || busy !== null}
                  onClick={() => onDecision("escalated")}
                >
                  <AlertTriangle className="mr-1.5 h-4 w-4" />
                  Escalate
                </Button>
                <Button size="sm" disabled={!canAct || busy !== null} onClick={() => onDecision("resolved")}>
                  <CheckCircle2 className="mr-1.5 h-4 w-4" />
                  Approve
                </Button>
              </div>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2 py-0.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </span>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Icon className="h-4 w-4 text-muted-foreground" />
        {title}
      </h3>
      {children}
    </section>
  );
}
