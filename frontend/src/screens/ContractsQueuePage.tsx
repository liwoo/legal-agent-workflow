"use client";

import * as React from "react";

import { ContractDetailModal } from "@/src/components/contract-detail-modal";
import { contractColumns } from "@/src/components/contract-columns";
import { DataTable } from "@/src/components/data-table";
import { QueueTabs } from "@/src/components/queue-tabs";
import { useContracts } from "@/src/store/contracts";
import type { ContractSummary, Queue } from "@/src/types";

const COPY: Record<Queue, { title: string; blurb: string; empty: string }> = {
  pending: {
    title: "Pending review",
    blurb: "Untriaged arrivals and items returned for more information.",
    empty: "No contracts are waiting for triage.",
  },
  approved: {
    title: "Approved",
    blurb: "Signed at the desk — clean, desk-edited, or with a recorded deviation.",
    empty: "Nothing approved yet.",
  },
  quarantined: {
    title: "Quarantined",
    blurb: "Blocked, escalated, or awaiting a business decision — a human must act.",
    empty: "Nothing quarantined — the queue is clear.",
  },
};

export function ContractsQueuePage({ queue }: { queue: Queue }) {
  const { byQueue, contracts } = useContracts();
  const [selected, setSelected] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState(false);

  const rows = byQueue(queue);
  const counts = {
    pending: contracts.filter((c) => c.queue === "pending").length,
    approved: contracts.filter((c) => c.queue === "approved").length,
    quarantined: contracts.filter((c) => c.queue === "quarantined").length,
  };

  const onRowClick = (row: ContractSummary) => {
    setSelected(row.id);
    setOpen(true);
  };

  const copy = COPY[queue];

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{copy.title}</h1>
        <p className="text-sm text-muted-foreground">{copy.blurb}</p>
      </div>

      <QueueTabs counts={counts} />

      <DataTable columns={contractColumns} data={rows} onRowClick={onRowClick} emptyMessage={copy.empty} />

      <ContractDetailModal contractId={selected} open={open} onOpenChange={setOpen} />
    </div>
  );
}
