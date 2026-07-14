"use client";

import * as React from "react";

import {
  archiveContract,
  createContract,
  createContractStream,
  getContract,
  listContracts,
  resolveContract,
  triageContract,
  triageContractStream,
  unarchiveContract,
  type TriageStep,
} from "@/src/lib/api";
import type { ContractDetail, ContractSummary, Queue, ResolveDecision } from "@/src/types";
import { queueForContract } from "@/src/lib/utils";

interface ContractsContextValue {
  contracts: ContractSummary[];
  /** Contracts the reviewer has archived — surfaced in Settings → Archived. */
  archived: ContractSummary[];
  loading: boolean;
  error: string | null;
  byQueue: (queue: Queue) => ContractSummary[];
  getById: (id: string) => ContractSummary | undefined;
  triage: (id: string, onStep?: (step: TriageStep) => void) => Promise<ContractDetail | undefined>;
  resolve: (id: string, decision: ResolveDecision, note?: string) => Promise<ContractDetail | undefined>;
  create: (form: FormData, onStep?: (step: TriageStep) => void) => Promise<ContractDetail>;
  /** Move a contract out of its queue and into the archive. */
  archive: (id: string) => Promise<void>;
  /** Return an archived contract to its queue. */
  restore: (id: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const ContractsContext = React.createContext<ContractsContextValue | undefined>(undefined);

function toSummary(detail: ContractDetail): ContractSummary {
  const {
    classification: _classification,
    gate_checks: _gate_checks,
    redlines: _redlines,
    forward_obligations: _forward_obligations,
    explanation: _explanation,
    recommended_action: _recommended_action,
    interrupt: _interrupt,
    path_node_ids: _path_node_ids,
    timeline: _timeline,
    ...summary
  } = detail;
  return summary;
}

export function ContractsProvider({ children }: { children: React.ReactNode }) {
  const [contracts, setContracts] = React.useState<ContractSummary[]>([]);
  const [archived, setArchived] = React.useState<ContractSummary[]>([]);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  // Archived ids captured in a ref so refresh() can filter them out without
  // being re-created every time the archive changes (which would re-run the
  // load-on-mount effect). Archived items are held out of every queue.
  const archivedIds = React.useRef<Set<string>>(new Set());
  React.useEffect(() => {
    archivedIds.current = new Set(archived.map((c) => c.id));
  }, [archived]);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listContracts();
      setContracts(data.filter((c) => !archivedIds.current.has(c.id)));
    } catch (err) {
      // listContracts() already falls back to fixtures internally, so this
      // branch should be effectively unreachable — kept for defence in depth.
      setError(err instanceof Error ? err.message : "Failed to load contracts.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const byQueue = React.useCallback(
    (queue: Queue) => contracts.filter((c) => c.queue === queue),
    [contracts]
  );

  const getById = React.useCallback(
    (id: string) => contracts.find((c) => c.id === id),
    [contracts]
  );

  const triage = React.useCallback(async (id: string, onStep?: (step: TriageStep) => void) => {
    // Optimistic: flip to "processing" immediately.
    setContracts((prev) => prev.map((c) => (c.id === id ? { ...c, ai_status: "processing" } : c)));
    // Stream a live view of the run when the caller wants one; otherwise run to
    // completion the plain way.
    const result = onStep
      ? await triageContractStream(id, onStep)
      : await triageContract(id);
    if (result) {
      setContracts((prev) =>
        prev.map((c) => (c.id === id ? toSummary({ ...result, queue: queueForContract(result) }) : c))
      );
    }
    return result;
  }, []);

  const resolve = React.useCallback(async (id: string, decision: ResolveDecision, note?: string) => {
    // Optimistic update: reflect the decision immediately.
    const optimisticEndState =
      decision === "resolved" ? "signed_desk_edits" : decision === "declined" ? "declined" : "escalated";
    setContracts((prev) =>
      prev.map((c) =>
        c.id === id
          ? { ...c, end_state: optimisticEndState, queue: queueForContract({ ...c, end_state: optimisticEndState }) }
          : c
      )
    );

    const result = await resolveContract(id, decision, note);
    if (result) {
      setContracts((prev) =>
        prev.map((c) => (c.id === id ? toSummary({ ...result, queue: queueForContract(result) }) : c))
      );
    }
    return result;
  }, []);

  const create = React.useCallback(async (form: FormData, onStep?: (step: TriageStep) => void) => {
    // Stream the agent run when a step handler is supplied (the New Contract
    // dialog renders it live); fall back to the plain one-shot create otherwise.
    const result = onStep ? await createContractStream(form, onStep) : await createContract(form);
    const summary = toSummary({ ...result, queue: queueForContract(result) });
    setContracts((prev) => {
      const idx = prev.findIndex((c) => c.id === summary.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = summary;
        return next;
      }
      return [summary, ...prev];
    });
    return result;
  }, []);

  const archive = React.useCallback(
    async (id: string) => {
      // Pull the row out of the live queues and remember it in the archive.
      setContracts((prev) => {
        const item = prev.find((c) => c.id === id);
        if (item) setArchived((a) => [item, ...a.filter((x) => x.id !== id)]);
        return prev.filter((c) => c.id !== id);
      });
      // Best-effort persistence; the archive is tracked client-side regardless.
      await archiveContract(id);
    },
    []
  );

  const restore = React.useCallback(
    async (id: string) => {
      setArchived((prev) => {
        const item = prev.find((c) => c.id === id);
        if (item) setContracts((c) => [item, ...c.filter((x) => x.id !== id)]);
        return prev.filter((c) => c.id !== id);
      });
      await unarchiveContract(id);
    },
    []
  );

  const value = React.useMemo<ContractsContextValue>(
    () => ({ contracts, archived, loading, error, byQueue, getById, triage, resolve, create, archive, restore, refresh }),
    [contracts, archived, loading, error, byQueue, getById, triage, resolve, create, archive, restore, refresh]
  );

  return <ContractsContext.Provider value={value}>{children}</ContractsContext.Provider>;
}

export function useContracts(): ContractsContextValue {
  const ctx = React.useContext(ContractsContext);
  if (!ctx) {
    throw new Error("useContracts must be used within a ContractsProvider");
  }
  return ctx;
}

/** Re-exported for screens/components that need full detail (not just summary). */
export { getContract };
