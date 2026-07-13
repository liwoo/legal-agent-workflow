import { contractsFixture, getContractFixtureById } from "@/src/data/contracts";
import { policiesFixture } from "@/src/data/policies";
import type { ContractDetail, ContractSummary, Policy, ResolveDecision } from "@/src/types";
import { queueForContract } from "@/src/lib/utils";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 3000;

/**
 * Fetch with an abort-based timeout. Never throws on a slow/unreachable
 * network — the caller is expected to catch and fall back to fixtures.
 */
async function fetchWithTimeout(
  input: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(input, { ...init, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(timer);
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with status ${res.status}`);
  }
  return (await res.json()) as T;
}

/**
 * Live-checks the API by hitting /api/health with a short timeout.
 * Used by the Settings screen to show a connectivity indicator, and can be
 * used anywhere the UI wants to know whether it's rendering live or
 * fixture data.
 */
export async function apiEnabled(): Promise<boolean> {
  try {
    const data = await fetchJson<{ status: string }>("/api/health", { method: "GET" });
    return data.status === "ok";
  } catch {
    return false;
  }
}

/** Resolve the configured API base URL, for display purposes. */
export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export async function listContracts(): Promise<ContractSummary[]> {
  try {
    const data = await fetchJson<ContractSummary[]>("/api/contracts");
    // The backend labels the queue with its disposition vocabulary
    // (approved / quarantined / pending); the console speaks inbox / signed /
    // review. Derive the console's queue from end_state here so the initial
    // load matches what create/triage/resolve already compute client-side.
    return data.map((c) => ({ ...c, queue: queueForContract(c) }));
  } catch {
    return contractsFixture.map(toSummary);
  }
}

export async function getContract(id: string): Promise<ContractDetail | undefined> {
  try {
    const data = await fetchJson<ContractDetail>(`/api/contracts/${encodeURIComponent(id)}`);
    return { ...data, queue: queueForContract(data) };
  } catch {
    return getContractFixtureById(id);
  }
}

/**
 * Create a contract from the "New Contract" form. Posts a multipart form (so an
 * intake PDF can ride along); the backend persists the intake to SQLite, stores
 * the PDF, and runs the agent synchronously, returning the triaged detail.
 *
 * Unlike the read paths, this throws on failure — creating a contract requires a
 * live backend, so the caller surfaces the error rather than falling back.
 */
export async function createContract(form: FormData): Promise<ContractDetail> {
  const res = await fetchWithTimeout(
    `${API_BASE_URL}/api/contracts`,
    { method: "POST", body: form },
    60000 // the agent runs synchronously; give it room
  );
  if (!res.ok) {
    let detail = `status ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`Failed to create contract: ${detail}`);
  }
  return (await res.json()) as ContractDetail;
}

export async function triageContract(id: string): Promise<ContractDetail | undefined> {
  try {
    const data = await fetchJson<ContractDetail>(`/api/contracts/${encodeURIComponent(id)}/triage`, {
      method: "POST",
    });
    return data;
  } catch {
    // Offline fallback: fixtures are already "triaged", so just return the
    // matching fixture as-is to simulate a completed triage run.
    const fixture = getContractFixtureById(id);
    if (!fixture) return undefined;
    return { ...fixture, ai_status: "triaged" };
  }
}

export async function resolveContract(
  id: string,
  decision: ResolveDecision,
  note?: string
): Promise<ContractDetail | undefined> {
  try {
    const data = await fetchJson<ContractDetail>(`/api/contracts/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    });
    return data;
  } catch {
    const fixture = getContractFixtureById(id);
    if (!fixture) return undefined;
    const end_state =
      decision === "resolved"
        ? "signed_desk_edits"
        : decision === "declined"
          ? "declined"
          : "escalated";
    const updated: ContractDetail = {
      ...fixture,
      end_state,
      ai_status: "triaged",
      interrupt:
        decision === "escalated"
          ? {
              reason: `escalated by reviewer${note ? `: ${note}` : ""}`,
              owner: "Legal Director",
              sla: null,
              request_id: fixture.interrupt?.request_id ?? null,
            }
          : null,
    };
    return { ...updated, queue: queueForContract(updated) };
  }
}

export async function listPolicies(): Promise<Policy[]> {
  try {
    const data = await fetchJson<Policy[]>("/api/policies");
    return data;
  } catch {
    return policiesFixture;
  }
}

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
