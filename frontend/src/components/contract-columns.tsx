"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { ArrowUpDown } from "lucide-react";

import { ScoreBadge } from "@/src/components/score-badge";
import { StateBadge } from "@/src/components/state-badge";
import { Button } from "@/src/components/ui/button";
import { formatDate, titleCase } from "@/src/lib/utils";
import type { ContractSummary } from "@/src/types";

function sortHeader(label: string) {
  const Header = ({ column }: { column: { toggleSorting: (d?: boolean) => void; getIsSorted: () => false | "asc" | "desc" } }) => (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-3 h-8 data-[state=open]:bg-accent"
      onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
    >
      {label}
      <ArrowUpDown className="ml-1.5 h-3.5 w-3.5 opacity-60" />
    </Button>
  );
  Header.displayName = `SortHeader(${label})`;
  return Header;
}

export const contractColumns: ColumnDef<ContractSummary, unknown>[] = [
  {
    accessorKey: "id",
    header: sortHeader("Ref"),
    cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground">{row.original.id}</span>,
  },
  {
    accessorKey: "counterparty",
    header: sortHeader("Counterparty"),
    cell: ({ row }) => (
      <div className="flex flex-col">
        <span className="font-medium text-foreground">{row.original.counterparty}</span>
        <span className="text-xs text-muted-foreground">{titleCase(row.original.document_family)}</span>
      </div>
    ),
  },
  {
    accessorKey: "paper_source",
    header: "Paper",
    cell: ({ row }) => <span className="text-sm text-muted-foreground">{titleCase(row.original.paper_source)}</span>,
  },
  {
    accessorKey: "received_at",
    header: sortHeader("Received"),
    cell: ({ row }) => <span className="text-sm text-muted-foreground">{formatDate(row.original.received_at)}</span>,
  },
  {
    accessorKey: "score",
    header: sortHeader("Confidence"),
    cell: ({ row }) => <ScoreBadge score={row.original.score} />,
    sortingFn: (a, b) => (a.original.score ?? -1) - (b.original.score ?? -1),
  },
  {
    id: "state",
    header: "State",
    cell: ({ row }) => <StateBadge aiStatus={row.original.ai_status} endState={row.original.end_state} />,
  },
];
