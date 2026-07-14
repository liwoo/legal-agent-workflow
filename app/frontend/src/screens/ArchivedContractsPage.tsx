"use client";

import * as React from "react";
import { Archive, RotateCcw } from "lucide-react";

import { EmptyState } from "@/src/components/empty-state";
import { InfoHint } from "@/src/components/info-hint";
import { SettingsTabs } from "@/src/components/settings-tabs";
import { Button } from "@/src/components/ui/button";
import { listArchivedContracts } from "@/src/lib/api";
import { useContracts } from "@/src/store/contracts";
import { formatRelative, titleCase } from "@/src/lib/utils";
import type { ContractSummary } from "@/src/types";

/**
 * Settings → Archived. Lists the contracts the reviewer has archived (which
 * therefore drop out of every queue) and lets them restore one. Merges this
 * session's archive from the store with anything the backend has persisted.
 */
export function ArchivedContractsPage() {
  const { archived, restore } = useContracts();
  const [fetched, setFetched] = React.useState<ContractSummary[]>([]);

  React.useEffect(() => {
    void listArchivedContracts().then(setFetched);
  }, []);

  // De-dupe by id, preferring the store's live copy over the fetched one.
  const byId = new Map<string, ContractSummary>();
  for (const c of fetched) byId.set(c.id, c);
  for (const c of archived) byId.set(c.id, c);
  const rows = [...byId.values()];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Archived</h1>
        <InfoHint>Contracts you&apos;ve archived. They&apos;re out of every queue until you restore one.</InfoHint>
      </div>

      <SettingsTabs />

      {rows.length === 0 ? (
        <EmptyState icon={Archive} title="Nothing archived" description="Archive a contract from its detail view and it lands here." />
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {rows.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{c.counterparty}</p>
                <p className="truncate text-xs text-muted-foreground">
                  <span className="font-mono">{c.id}</span> · {titleCase(c.document_family)} · arrived{" "}
                  {formatRelative(c.received_at)}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => void restore(c.id)}>
                <RotateCcw className="mr-1.5 h-4 w-4" />
                Restore
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
