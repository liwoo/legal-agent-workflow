"use client";

import * as React from "react";

import {
  createContract,
  getContract,
  listContracts,
  resolveContract,
  triageContract,
} from "@/src/lib/api";
import type { ContractDetail, ContractSummary, Queue, ResolveDecision } from "@/src/types";
import { queueForContract } from "@/src/lib/utils";

interface ContractsContextValue {
  contracts: ContractSummary[];
  loading: boolean;
  error: string | null;
  byQueue: (queue: Queue) => ContractSummary[];
  getById: (id: string) => ContractSummary | undefined;
  triage: (id: string) => Promise<ContractDetail | undefined>;
  resolve: (id: string, decision: ResolveDecision, note?: string) => Promise<ContractDetail | undefined>;
  create: (form: FormData) => Promise<ContractDetail>;
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
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listContracts();
      setContracts(data);
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

  const triage = React.useCallback(async (id: string) => {
    // Optimistic: flip to "processing" immediately.
    setContracts((prev) => prev.map((c) => (c.id === id ? { ...c, ai_status: "processing" } : c)));
    const result = await triageContract(id);
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

  const create = React.useCallback(async (form: FormData) => {
    const result = await createContract(form);
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

  const value = React.useMemo<ContractsContextValue>(
    () => ({ contracts, loading, error, byQueue, getById, triage, resolve, create, refresh }),
    [contracts, loading, error, byQueue, getById, triage, resolve, create, refresh]
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
