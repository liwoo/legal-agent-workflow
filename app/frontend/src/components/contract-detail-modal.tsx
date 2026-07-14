"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Archive,
  ArrowUpRight,
  Ban,
  Banknote,
  CalendarClock,
  CheckCircle2,
  Clock,
  FileText,
  Gavel,
  History,
  Mail,
  PenLine,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ContractJourney } from "@/src/components/contract-journey";
import { InfoHint } from "@/src/components/info-hint";
import { ScoreBadge } from "@/src/components/score-badge";
import { StateBadge } from "@/src/components/state-badge";
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
import { Separator } from "@/src/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/src/components/ui/tabs";
import { getApiBaseUrl } from "@/src/lib/api";
import { getContract, useContracts } from "@/src/store/contracts";
import { cn, formatDate, formatDateTime, formatGbp, formatRelative, titleCase } from "@/src/lib/utils";
import type { ContractDetail, GateCheck } from "@/src/types";

interface ContractDetailModalProps {
  contractId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// The in-flight footer action, so every button disables while one runs.
type ActionId = "reevaluate" | "send" | "approve" | "archive";

// Traffic-light UI for each check status — one icon + colour, read at a glance.
const GATE_STATUS_UI: Record<GateCheck["status"], { icon: LucideIcon; label: string; tile: string; text: string }> = {
  passed: { icon: CheckCircle2, label: "Passed", tile: "border-success/30 bg-success/5", text: "text-success" },
  action_required: {
    icon: AlertTriangle,
    label: "Needs action",
    tile: "border-warning/40 bg-warning/5",
    text: "text-warning",
  },
  blocked: { icon: Ban, label: "Blocked", tile: "border-destructive/40 bg-destructive/5", text: "text-destructive" },
};

// Friendly names for the standing policy checks.
const GATE_LABEL: Record<string, string> = {
  privacy: "Data protection",
  dpa: "Data protection",
  statutory: "Statutory checks",
  finance: "Financial cover",
  insurance: "Insurance & cover",
};

const TIER_VARIANT: Record<string, "secondary" | "warning" | "destructive"> = {
  standard: "secondary",
  fallback_1: "warning",
  fallback_2: "warning",
  refusal_point: "destructive",
  off_playbook: "destructive",
};

// Friendly names for redline tiers.
const TIER_LABEL: Record<string, string> = {
  standard: "Standard change",
  fallback_1: "Acceptable fallback",
  fallback_2: "Acceptable fallback",
  refusal_point: "Refusal point",
  off_playbook: "Off-playbook",
  banned: "Not allowed",
};

const gateLabel = (gate: string) => GATE_LABEL[gate] ?? titleCase(gate);
const tierLabel = (tier: string) => TIER_LABEL[tier] ?? titleCase(tier);

// The desk's move on each redline, phrased as a verb for the one-line proposal.
const ACTION_VERB: Record<string, string> = {
  escalated: "escalate",
  struck: "strike",
  substitute_offered: "offer a substitute for",
  fallback_applied: "apply a fallback to",
  held: "hold",
};
// Most-serious-first, so the proposal leads with escalations and holds land last.
const ACTION_ORDER = ["escalated", "struck", "substitute_offered", "fallback_applied", "held"];

// A plain-English predicate for the Summary "Proposal is to …" line, built from
// what the desk did with each redline (escalate / strike / fallback / hold),
// grouped by action so the reviewer reads the shape of the ask in one sentence
// — e.g. "escalate 4 clauses and hold 3". Returns null when nothing was proposed.
function proposalSummary(redlines: ContractDetail["redlines"]): string | null {
  if (!redlines.length) return null;
  const counts = new Map<string, number>();
  for (const r of redlines) counts.set(r.action, (counts.get(r.action) ?? 0) + 1);
  const rank = (a: string) => ACTION_ORDER.indexOf(a) + 1 || 99;
  const segments = [...counts.keys()]
    .sort((a, b) => rank(a) - rank(b))
    .map((action, i) => {
      const n = counts.get(action)!;
      const verb = ACTION_VERB[action] ?? "review";
      // Name the noun once, on the first segment, so it isn't repeated.
      const noun = i === 0 ? (n === 1 ? " clause" : " clauses") : "";
      return `${verb} ${n}${noun}`;
    });
  // segments is non-empty here (redlines was non-empty), so the indexes are safe.
  if (segments.length === 1) return segments[0]!;
  return `${segments.slice(0, -1).join(", ")} and ${segments[segments.length - 1]!}`;
}

// Compose a mailto: draft to the counterparty that reads sensibly for THIS
// case, rather than always claiming to "propose changes". Three situations:
//   • propose  — sending our redlines to the other side for review
//   • approve, with changes — ready to sign subject to desk edits we've made
//   • approve, no changes   — happy to proceed as drafted, ready to countersign
// The recipient is left blank — the reviewer fills in the other side's address.
function contractEmail(detail: ContractDetail, intent: "propose" | "approve"): string {
  const changes = detail.redlines.map((r, i) => {
    const ref = r.clause_ref ?? "Clause";
    return `${i + 1}. ${ref} — ${tierLabel(r.tier)}\n   ${r.description}`;
  });
  const who = `${detail.counterparty} (${detail.id})`;

  let subject: string;
  let lines: string[];
  if (intent === "propose") {
    subject = `Proposed changes — ${who}`;
    lines = [
      "Hi,",
      "",
      `Following our review of ${who}, we'd like to propose the following changes:`,
      "",
      ...changes,
      "",
      "Happy to talk these through.",
    ];
  } else if (changes.length > 0) {
    subject = `Ready to sign, subject to changes — ${who}`;
    lines = [
      "Hi,",
      "",
      `We've completed our review of ${who} and are happy to proceed, subject to the following:`,
      "",
      ...changes,
      "",
      "With these in place we're ready to countersign — let us know if anything needs discussing.",
    ];
  } else {
    subject = `Ready to sign — ${who}`;
    lines = [
      "Hi,",
      "",
      `We've completed our review of ${who} and are happy to proceed as drafted — no changes needed on our side.`,
      "",
      "We're ready to countersign; please let us know the best way to complete signature.",
    ];
  }
  const body = [...lines, "", "Best regards,"].join("\n");
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

// Fold a resolve/approve response into the current detail WITHOUT dropping the
// proposed changes (or checks / follow-ups): a decision changes the outcome, not
// the analysis, so we keep whatever the server returned but never let it blank
// out lists the reviewer is still looking at.
function keepAnalysis(prev: ContractDetail | null, updated: ContractDetail): ContractDetail {
  if (!prev) return updated;
  return {
    ...updated,
    redlines: updated.redlines.length ? updated.redlines : prev.redlines,
    gate_checks: updated.gate_checks.length ? updated.gate_checks : prev.gate_checks,
    forward_obligations: updated.forward_obligations.length
      ? updated.forward_obligations
      : prev.forward_obligations,
  };
}

// Underline tab strip — matches the QueueTabs / SettingsTabs design language.
const TABS_LIST_CLASS = "h-auto w-full justify-start gap-1 rounded-none border-b border-border bg-transparent px-6 py-0";
const TAB_TRIGGER_CLASS =
  "relative -mb-px gap-1.5 rounded-none border-b-2 border-transparent px-3 py-2.5 text-sm font-medium text-muted-foreground data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none";

export function ContractDetailModal({ contractId, open, onOpenChange }: ContractDetailModalProps) {
  const { resolve, triage, archive } = useContracts();
  const [detail, setDetail] = React.useState<ContractDetail | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [busy, setBusy] = React.useState<ActionId | null>(null);

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

  // Approve = resolve as "resolved", keeping the proposed changes on screen
  // (a decision changes the outcome, not the analysis — see keepAnalysis).
  const applyApproval = async () => {
    if (!contractId) return;
    const updated = await resolve(contractId, "resolved");
    if (updated) setDetail((prev) => keepAnalysis(prev, updated));
  };

  // Re-evaluate = a fresh AI run that *replaces* everything (classification,
  // gates, proposed changes, outcome, score) — the one action that deliberately
  // discards the current analysis, so no keepAnalysis here.
  const onReevaluate = async () => {
    if (!contractId) return;
    setBusy("reevaluate");
    const updated = await triage(contractId);
    if (updated) setDetail(updated);
    setBusy(null);
  };

  // Open a pre-filled email to the counterparty proposing our changes.
  const onSendSuggestions = () => {
    if (detail) window.location.href = contractEmail(detail, "propose");
  };

  // Ready-to-sign: approve, then open an email that reads correctly for the case
  // (ready to countersign as-drafted when there are no changes to send).
  const onApproveSuggestions = async () => {
    setBusy("approve");
    if (detail) window.location.href = contractEmail(detail, "approve");
    await applyApproval();
    setBusy(null);
  };

  const onArchive = async () => {
    if (!contractId) return;
    setBusy("archive");
    await archive(contractId);
    setBusy(null);
    onOpenChange(false);
  };

  const proposal = detail ? proposalSummary(detail.redlines) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] max-w-4xl flex-col gap-0 overflow-hidden p-0">
        {loading || !detail ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            {loading ? "Loading contract…" : "Contract not found."}
          </div>
        ) : (
          <>
            <DialogHeader className="shrink-0 border-b border-border p-6 pb-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <FileText className="h-5 w-5" />
                  </span>
                  <div className="space-y-0.5">
                    <DialogTitle className="text-lg leading-tight">{detail.counterparty}</DialogTitle>
                    <DialogDescription className="text-sm">
                      {titleCase(detail.document_family)}
                      {detail.classification?.value_gbp != null ? ` · ${formatGbp(detail.classification.value_gbp)}` : ""}{" "}
                      · arrived {formatRelative(detail.received_at)}
                    </DialogDescription>
                    {detail.document_url ? (
                      // Link to the stable API endpoint, which re-signs a fresh
                      // presigned URL on each open (the embedded one is short-lived).
                      <a
                        href={`${getApiBaseUrl()}/api/contracts/${encodeURIComponent(detail.id)}/document`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 pt-0.5 text-xs font-medium text-primary hover:underline"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        View intake PDF
                      </a>
                    ) : null}
                  </div>
                </div>
                <ScoreBadge score={detail.score} size="lg" />
              </div>
            </DialogHeader>

            {/* The contract's journey — instant, wordless status */}
            <div className="shrink-0 border-b border-border px-8 py-4">
              <ContractJourney aiStatus={detail.ai_status} endState={detail.end_state} />
            </div>

            <Tabs defaultValue="summary" className="flex min-h-0 flex-1 flex-col">
              <TabsList className={cn(TABS_LIST_CLASS, "shrink-0")}>
                <TabsTrigger value="summary" className={TAB_TRIGGER_CLASS}>
                  <Sparkles className="h-4 w-4" />
                  Summary
                </TabsTrigger>
                <TabsTrigger value="checks" className={TAB_TRIGGER_CLASS}>
                  <ShieldCheck className="h-4 w-4" />
                  Policy checks
                </TabsTrigger>
                <TabsTrigger value="changes" className={TAB_TRIGGER_CLASS}>
                  <PenLine className="h-4 w-4" />
                  Proposed changes
                </TabsTrigger>
                <TabsTrigger value="decision" className={TAB_TRIGGER_CLASS}>
                  <Gavel className="h-4 w-4" />
                  Decision
                </TabsTrigger>
                <TabsTrigger value="timeline" className={TAB_TRIGGER_CLASS}>
                  <History className="h-4 w-4" />
                  Timeline
                </TabsTrigger>
              </TabsList>

              {/* Native overflow container: reliably bounded by the flex column
                  so the body scrolls while the header, tab strip and footer stay
                  pinned. */}
              <div className="min-h-0 flex-1 overflow-y-auto">
                {/* a) Summary — what this contract is about, in a nutshell */}
                <TabsContent value="summary" className="mt-0 space-y-5 p-6">
                  <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-4 text-sm">
                    <p>
                      <span className="font-medium text-foreground">What arrived:</span>{" "}
                      <span className="text-muted-foreground">{detail.what_arrived}</span>
                    </p>
                    <p className="text-muted-foreground">
                      <span className="font-medium text-foreground">{detail.sender_role}:</span> “{detail.sender_ask}”
                    </p>
                  </div>

                  {detail.explanation || proposal ? (
                    <div className="rounded-lg border border-primary/30 bg-primary/5 p-4">
                      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary">
                        <Sparkles className="h-3.5 w-3.5" />
                        In a nutshell
                      </div>
                      {detail.explanation ? (
                        <p className="text-sm leading-relaxed text-foreground">{detail.explanation}</p>
                      ) : null}
                      {proposal ? (
                        <p className="mt-2 flex items-start gap-1.5 text-sm text-foreground">
                          <PenLine className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                          <span>
                            <span className="font-medium">Proposal is to</span> {proposal}.
                          </span>
                        </p>
                      ) : null}
                      {detail.recommended_action ? (
                        <p className="mt-2 text-sm font-medium text-primary">→ {detail.recommended_action}</p>
                      ) : null}
                    </div>
                  ) : null}

                  {detail.interrupt ? (
                    <div className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                      <span>
                        <span className="font-medium">Waiting on {detail.interrupt.owner}</span> — {detail.interrupt.reason}
                        {detail.interrupt.sla ? ` · due ${detail.interrupt.sla}` : ""}.
                      </span>
                    </div>
                  ) : null}

                  {detail.classification ? (
                    <section className="flex flex-wrap gap-2">
                      {detail.classification.value_gbp != null ? (
                        <Fact icon={Banknote} value={formatGbp(detail.classification.value_gbp)} />
                      ) : null}
                      {detail.classification.deadline ? (
                        <Fact icon={CalendarClock} value={`Due ${formatDate(detail.classification.deadline)}`} />
                      ) : null}
                      <Fact icon={PenLine} value={`Signed by ${titleCase(detail.classification.signatory_level)}`} />
                      {detail.classification.data_flags.length ? (
                        <Fact icon={ShieldCheck} value="Sensitive data" />
                      ) : null}
                      {detail.prior_contract_ids.map((p) => (
                        <Fact key={p} icon={FileText} value={`Prior: ${p}`} />
                      ))}
                    </section>
                  ) : null}

                  <p className="text-xs text-muted-foreground">
                    New here? <LearnMore anchor="">What these terms mean</LearnMore>
                  </p>
                </TabsContent>

                {/* b) Policy checks — the standing gates, in plain terms */}
                <TabsContent value="checks" className="mt-0 space-y-6 p-6">
                  {detail.gate_checks.length ? (
                    <Section
                      title="Policy checks"
                      icon={ShieldCheck}
                      aside={<LearnMore anchor="gates">What are these?</LearnMore>}
                    >
                      {/* Traffic-light tiles: status readable at a glance, no reading required. */}
                      <div className="grid gap-2 sm:grid-cols-3">
                        {detail.gate_checks.map((g, i) => {
                          const ui = GATE_STATUS_UI[g.status];
                          const Icon = ui.icon;
                          return (
                            <div key={i} className={cn("rounded-lg border p-3", ui.tile)}>
                              <Icon className={cn("h-5 w-5", ui.text)} />
                              <p className="mt-1.5 text-sm font-medium text-foreground">{gateLabel(g.gate)}</p>
                              <p className={cn("text-xs font-medium", ui.text)}>{ui.label}</p>
                            </div>
                          );
                        })}
                      </div>
                      {/* Only spell out the ones that need a human. */}
                      {detail.gate_checks
                        .filter((g) => g.status !== "passed")
                        .map((g, i) => (
                          <div key={i} className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
                            <p className="font-medium text-foreground">{gateLabel(g.gate)}</p>
                            {g.findings.map((line, j) => (
                              <p key={`f${j}`} className="mt-0.5 text-muted-foreground">
                                {line}
                              </p>
                            ))}
                            {g.required_actions.map((line, j) => (
                              <p key={`a${j}`} className="mt-0.5">
                                <span className="font-medium">To do:</span> {line}
                              </p>
                            ))}
                          </div>
                        ))}
                    </Section>
                  ) : (
                    <EmptyTab icon={ShieldCheck} message="No policy checks were recorded for this item." />
                  )}
                </TabsContent>

                {/* c) Proposed changes — the redlines, graded against our playbook */}
                <TabsContent value="changes" className="mt-0 space-y-6 p-6">
                  {detail.redlines.length ? (
                    <Section
                      title="Proposed changes"
                      icon={PenLine}
                      hint="Wording the other side wants to change, graded against our playbook."
                      aside={<LearnMore anchor="redlines">What do the tiers mean?</LearnMore>}
                    >
                      <ul className="space-y-2">
                        {detail.redlines.map((r, i) => (
                          <li key={i} className="space-y-1 rounded-lg border border-border p-3">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-sm font-medium text-foreground">
                                {r.clause_ref ?? "Clause"}
                              </span>
                              <Badge variant={TIER_VARIANT[r.tier] ?? "secondary"}>{tierLabel(r.tier)}</Badge>
                            </div>
                            <p className="text-sm text-muted-foreground">{r.description}</p>
                          </li>
                        ))}
                      </ul>
                    </Section>
                  ) : (
                    <EmptyTab icon={PenLine} message="No changes to the counterparty's wording were proposed." />
                  )}
                </TabsContent>

                {/* d) Decision — what was decided and what happens next */}
                <TabsContent value="decision" className="mt-0 space-y-6 p-6">
                  <div className="space-y-3 rounded-lg border border-border p-4">
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-sm font-medium text-foreground">Outcome</span>
                      <div className="flex items-center gap-2">
                        <StateBadge aiStatus={detail.ai_status} endState={detail.end_state} />
                        <LearnMore anchor="outcomes">Meaning</LearnMore>
                      </div>
                    </div>
                    {detail.recommended_action ? (
                      <p className="text-sm text-muted-foreground">
                        <span className="font-medium text-foreground">What the assistant suggests:</span>{" "}
                        {detail.recommended_action}
                      </p>
                    ) : detail.end_state == null ? (
                      <p className="text-sm text-muted-foreground">
                        No decision yet — this item is still waiting to be read or resolved.
                      </p>
                    ) : null}
                    {detail.interrupt ? (
                      <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                        <span>
                          Handed to <span className="font-medium">{detail.interrupt.owner}</span> —{" "}
                          {detail.interrupt.reason}
                          {detail.interrupt.sla ? ` · due ${detail.interrupt.sla}` : ""}.
                        </span>
                      </div>
                    ) : null}
                  </div>

                  {detail.forward_obligations.length ? (
                    <Section title="Follow-ups" icon={Clock} hint="Things to do after this contract is dealt with.">
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
                </TabsContent>

                {/* e) Timeline & logs — the chronological record */}
                <TabsContent value="timeline" className="mt-0 space-y-6 p-6">
                  {detail.timeline.length ? (
                    <Section title="Timeline & logs" icon={History}>
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
                            <span className="whitespace-nowrap text-xs text-muted-foreground">
                              {formatDateTime(e.at)}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </Section>
                  ) : (
                    <EmptyTab icon={History} message="No timeline events have been logged for this item yet." />
                  )}
                </TabsContent>
              </div>
            </Tabs>

            <Separator className="shrink-0" />
            <DialogFooter className="shrink-0 gap-2 p-4 sm:justify-between">
              <span className="hidden text-xs text-muted-foreground sm:block">
                <span className="font-mono">{detail.id}</span> · from {detail.sender_role}
              </span>
              <div className="flex items-center gap-2">
                {/* Archive — icon only, available in every state */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground"
                  disabled={busy !== null}
                  onClick={onArchive}
                  aria-label="Archive this contract"
                  title="Archive this contract"
                >
                  <Archive className="h-4 w-4" />
                </Button>

                {/* Send the proposed changes to the other side — states that still have changes to send */}
                {detail.redlines.length > 0 && detail.queue !== "signed" ? (
                  <Button variant="outline" size="sm" disabled={busy !== null} onClick={onSendSuggestions}>
                    <Mail className="mr-1.5 h-4 w-4" />
                    Send suggestions for review
                  </Button>
                ) : null}

                {/* Approve — ready-to-sign only; also opens an email that fits the case */}
                {detail.queue === "signed" ? (
                  <Button size="sm" disabled={busy !== null} onClick={onApproveSuggestions}>
                    <CheckCircle2 className="mr-1.5 h-4 w-4" />
                    {detail.redlines.length > 0 ? "Approve suggestions" : "Approve — ready to sign"}
                  </Button>
                ) : null}

                {/* Re-evaluate — fresh AI run that replaces the analysis; every state */}
                <Button
                  variant={detail.queue === "signed" ? "outline" : "default"}
                  size="sm"
                  disabled={busy !== null}
                  onClick={onReevaluate}
                >
                  <RefreshCw className={cn("mr-1.5 h-4 w-4", busy === "reevaluate" && "animate-spin")} />
                  Re-evaluate
                </Button>
              </div>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Fact({ icon: Icon, value }: { icon: LucideIcon; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 text-xs">
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="font-medium text-foreground">{value}</span>
    </span>
  );
}

function EmptyTab({
  icon: Icon,
  message,
}: {
  icon: React.ComponentType<{ className?: string }>;
  message: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-sm text-muted-foreground">
      <Icon className="h-6 w-6 text-muted-foreground/60" />
      <p>{message}</p>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  hint,
  aside,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  hint?: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
          {hint ? <InfoHint>{hint}</InfoHint> : null}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

/**
 * Inline "further reading" link into the /reference explainer. Opens in a new
 * tab so the reader keeps their place in the contract they're looking at.
 * Pass an empty anchor to land at the top of the page.
 */
function LearnMore({ anchor, children }: { anchor: string; children: React.ReactNode }) {
  return (
    <Link
      href={anchor ? `/reference#${anchor}` : "/reference"}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-0.5 whitespace-nowrap text-xs font-medium text-primary underline-offset-2 hover:underline"
    >
      {children}
      <ArrowUpRight className="h-3 w-3" />
    </Link>
  );
}
