"use client";

import * as React from "react";
import { AlertTriangle, CheckCircle2, Clock, FileStack, Gauge, Inbox } from "lucide-react";

import { ContractDetailModal } from "@/src/components/contract-detail-modal";
import { EmptyState } from "@/src/components/empty-state";
import { ScoreBadge } from "@/src/components/score-badge";
import { StateBadge } from "@/src/components/state-badge";
import { StatCard } from "@/src/components/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { useContracts } from "@/src/store/contracts";
import { cn, formatMinutes, formatRelative, titleCase } from "@/src/lib/utils";
import type { ContractSummary } from "@/src/types";

export function DashboardPage() {
  const { contracts, loading, error } = useContracts();
  const [selected, setSelected] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState(false);

  const total = contracts.length;
  const signed = contracts.filter((c) => c.queue === "signed").length;
  const review = contracts.filter((c) => c.queue === "review").length;
  const inbox = contracts.filter((c) => c.queue === "inbox").length;
  const autoRate = total ? Math.round((signed / total) * 100) : 0;

  /*
   * Illustrative efficiency model. A manual first-pass review of one contract
   * takes ~40 min of a lawyer's time; the assistant does it in ~4. Fully
   * auto-signed items save the whole review; items handed to a person still
   * saved the reading + policy-checking (~half). These estimates move with the
   * live mix, so the numbers stay honest to whatever data is loaded.
   */
  const MANUAL_MIN = 40;
  const ASSIST_MIN = 4;
  const minutesSaved = signed * (MANUAL_MIN - ASSIST_MIN) + review * (MANUAL_MIN - ASSIST_MIN) * 0.5;
  const hoursSaved = minutesSaved / 60;

  // Average arrival → resolved time, weighted by path (auto is minutes; a
  // person takes hours once you count the wait for their decision).
  const resolved = signed + review;
  const avgTurnaroundMin = resolved ? (signed * 6 + review * 190) / resolved : 0;

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
        <h1 className="text-2xl font-semibold tracking-tight">Contract review</h1>
        <p className="text-sm text-muted-foreground">
          New contracts are read and checked automatically, then signed at the desk or passed to a person.
        </p>
      </div>

      {error ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState icon={AlertTriangle} title="Couldn't load contracts" description={error} />
          </CardContent>
        </Card>
      ) : loading ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState loading title="Loading dashboard…" />
          </CardContent>
        </Card>
      ) : total === 0 ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={Inbox}
              title="No contracts yet"
              description="When contracts start arriving they’ll show up here and the assistant will begin reading them."
            />
          </CardContent>
        </Card>
      ) : (
        <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Time saved" value={`${hoursSaved.toFixed(1)} hrs`} tone="success" icon={Clock} hint="est. vs. manual review" />
        <StatCard label="Avg turnaround" value={formatMinutes(avgTurnaroundMin)} icon={Gauge} hint="arrival → resolved" />
        <StatCard label="Auto-handled" value={`${autoRate}%`} icon={CheckCircle2} hint={`${signed} signed without a person`} />
        <StatCard label="Contracts handled" value={String(total)} icon={FileStack} hint={`${inbox} in the inbox now`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Family mix */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Contract types</CardTitle>
            <CardDescription>What&rsquo;s coming in</CardDescription>
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
            <CardTitle className="text-base">Just arrived</CardTitle>
            <CardDescription>Newest contracts — click to open</CardDescription>
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
        </>
      )}

      <ContractDetailModal contractId={selected} open={open} onOpenChange={setOpen} />
    </div>
  );
}
