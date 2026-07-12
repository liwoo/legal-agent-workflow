"use client";

import * as React from "react";
import { CheckCircle2, FileStack, Inbox, Users } from "lucide-react";

import { ContractDetailModal } from "@/src/components/contract-detail-modal";
import { ScoreBadge } from "@/src/components/score-badge";
import { StateBadge } from "@/src/components/state-badge";
import { StatCard } from "@/src/components/stat-card";
import { WorkflowGraph } from "@/src/components/workflow-graph";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { useContracts } from "@/src/store/contracts";
import { cn, formatRelative, titleCase } from "@/src/lib/utils";
import type { ContractSummary } from "@/src/types";

export function DashboardPage() {
  const { contracts } = useContracts();
  const [selected, setSelected] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState(false);

  const total = contracts.length;
  const approved = contracts.filter((c) => c.queue === "approved").length;
  const quarantined = contracts.filter((c) => c.queue === "quarantined").length;
  const pending = contracts.filter((c) => c.queue === "pending").length;
  const autoRate = total ? Math.round((approved / total) * 100) : 0;

  // family mix for the mini bar chart
  const familyMix = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of contracts) counts.set(c.document_family, (counts.get(c.document_family) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [contracts]);
  const maxFamily = Math.max(1, ...familyMix.map(([, n]) => n));

  const recent = [...contracts]
    .sort((a, b) => new Date(b.received_at).getTime() - new Date(a.received_at).getTime())
    .slice(0, 6);

  const openContract = (c: ContractSummary) => {
    setSelected(c.id);
    setOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Live view of the contract-triage inbox and agent workflow.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="In the inbox" value={String(total)} icon={Inbox} hint={`${pending} pending review`} />
        <StatCard label="Auto-approvable" value={`${autoRate}%`} tone="success" icon={CheckCircle2} hint={`${approved} signed at the desk`} />
        <StatCard label="Need a human" value={String(quarantined)} tone="warning" icon={Users} hint="blocked / escalated / decision" />
        <StatCard label="Contract families" value={String(familyMix.length)} icon={FileStack} hint="distinct paper types" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Family mix */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Contract mix</CardTitle>
            <CardDescription>By document family</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {familyMix.map(([family, n]) => (
              <div key={family} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-foreground">{titleCase(family)}</span>
                  <span className="tabular-nums text-muted-foreground">{n}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${(n / maxFamily) * 100}%` }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Recent activity */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Recent arrivals</CardTitle>
            <CardDescription>Newest items in the inbox</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {recent.map((c) => (
              <button
                key={c.id}
                onClick={() => openContract(c)}
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-accent"
                )}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{c.counterparty}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {c.id} · {titleCase(c.document_family)} · {formatRelative(c.received_at)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <ScoreBadge score={c.score} />
                  <StateBadge aiStatus={c.ai_status} endState={c.end_state} />
                </div>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Agent graph */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Agent workflow</CardTitle>
          <CardDescription>
            The contract-review decision graph every item flows through. Open a contract to see the path it took.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <WorkflowGraph heightClassName="h-[460px]" />
        </CardContent>
      </Card>

      <ContractDetailModal contractId={selected} open={open} onOpenChange={setOpen} />
    </div>
  );
}
