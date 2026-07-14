"use client";

import * as React from "react";
import { AlertTriangle, CheckCircle2, FilePlus2, FileSignature, Inbox, Scale } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ContractDetailModal } from "@/src/components/contract-detail-modal";
import { contractColumns } from "@/src/components/contract-columns";
import { DataTable } from "@/src/components/data-table";
import { EmptyState } from "@/src/components/empty-state";
import { InfoHint } from "@/src/components/info-hint";
import { NewContractDialog } from "@/src/components/new-contract-dialog";
import { QueueTabs } from "@/src/components/queue-tabs";
import { Button } from "@/src/components/ui/button";
import { useContracts } from "@/src/store/contracts";
import type { ContractSummary, Queue } from "@/src/types";

const COPY: Record<Queue, { title: string; blurb: string; empty: string; icon: LucideIcon }> = {
  inbox: {
    title: "Inbox",
    blurb: "New contracts waiting to be read.",
    empty: "Nothing waiting — you're all caught up.",
    icon: Inbox,
  },
  signed: {
    title: "Signed",
    blurb: "Contracts finished and signed at the desk.",
    empty: "Nothing signed yet.",
    icon: FileSignature,
  },
  review: {
    title: "Review",
    blurb: "The assistant passed these to a person to decide.",
    empty: "Nothing needs a person right now.",
    icon: Scale,
  },
};

export function ContractsQueuePage({ queue }: { queue: Queue }) {
  const { byQueue, contracts, loading, error } = useContracts();
  const [selected, setSelected] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState(false);

  const rows = byQueue(queue);
  const counts = {
    inbox: contracts.filter((c) => c.queue === "inbox").length,
    review: contracts.filter((c) => c.queue === "review").length,
    signed: contracts.filter((c) => c.queue === "signed").length,
  };

  const onRowClick = (row: ContractSummary) => {
    setSelected(row.id);
    setOpen(true);
  };

  const copy = COPY[queue];

  // First run: nothing anywhere yet. Turn the inbox into a get-started prompt
  // with a call-to-action that opens the "New Contract" → triage flow.
  const firstRun = contracts.length === 0;

  const emptyState = error ? (
    <EmptyState icon={AlertTriangle} title="Couldn't load contracts" description={error} />
  ) : loading ? (
    <EmptyState loading title="Loading contracts…" />
  ) : queue === "inbox" && firstRun ? (
    <EmptyState
      icon={FilePlus2}
      title="No contracts yet"
      description="Add a contract and the assistant classifies it, runs the policy gates, and routes it to the right queue."
      action={
        <NewContractDialog
          trigger={
            <Button className="gap-1.5">
              <FilePlus2 className="h-4 w-4" />
              Add a contract to triage
            </Button>
          }
        />
      }
    />
  ) : (
    <EmptyState icon={queue === "inbox" ? CheckCircle2 : copy.icon} title={copy.empty} />
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{copy.title}</h1>
        <InfoHint>{copy.blurb}</InfoHint>
      </div>

      <QueueTabs counts={counts} />

      <DataTable
        columns={contractColumns}
        data={loading || error ? [] : rows}
        onRowClick={onRowClick}
        emptyState={emptyState}
      />

      <ContractDetailModal contractId={selected} open={open} onOpenChange={setOpen} />
    </div>
  );
}
