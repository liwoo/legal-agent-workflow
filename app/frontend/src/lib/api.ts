import { contractsFixture, getContractFixtureById } from "@/src/data/contracts";
import { policiesFixture } from "@/src/data/policies";
import type {
  ContractDetail,
  ContractSummary,
  PlaybookSection,
  PlaybookSectionUpdate,
  Policy,
  ResolveDecision,
} from "@/src/types";
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

/**
 * One line in a streamed triage run — mirrors the backend's `step` SSE payload
 * (and the shape of a {@link TimelineEvent}), so the console can render the live
 * loading log with the same colored-dot treatment as the final timeline tab.
 */
export interface TriageStep {
  node?: string;
  label: string;
  detail?: string | null;
  kind?: "info" | "warning" | "critical" | "success";
  at?: string;
}

/** Split an SSE frame ("event: …\ndata: …") into its event name and data body. */
function parseSseFrame(frame: string): { event?: string; data: string } {
  let event: string | undefined;
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  return { event, data: dataLines.join("\n") };
}

/**
 * POST to a streaming (Server-Sent Events) triage endpoint, invoking `onStep`
 * for each `step` event as the agent works, and resolving with the final
 * `ContractDetail` from the terminal `done` event. Throws on an `error` event or
 * if the stream ends without a result.
 *
 * Uses `fetch` + a `ReadableStream` reader (not `EventSource`) so it can POST a
 * multipart body and set headers — which `EventSource` can't.
 */
async function streamTriageRun(
  path: string,
  init: RequestInit,
  onStep: (step: TriageStep) => void
): Promise<ContractDetail> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok || !res.body) {
    throw new Error(`Triage stream failed with status ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let detail: ContractDetail | undefined;
  let errorMessage: string | undefined;

  // SSE frames are separated by a blank line; accumulate bytes and split on it.
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? ""; // keep any partial trailing frame
    for (const frame of frames) {
      if (!frame.trim()) continue;
      const { event, data } = parseSseFrame(frame);
      if (event === "step") {
        onStep(JSON.parse(data) as TriageStep);
      } else if (event === "done") {
        detail = (JSON.parse(data) as { detail: ContractDetail }).detail;
      } else if (event === "error") {
        errorMessage = (JSON.parse(data) as { message: string }).message;
      }
    }
  }

  if (errorMessage) throw new Error(errorMessage);
  if (!detail) throw new Error("Triage stream ended without a result.");
  return { ...detail, queue: queueForContract(detail) };
}

/**
 * Streaming twin of {@link createContract}: posts the "New Contract" form to the
 * SSE endpoint and reports each step of the agent run via `onStep`. Like
 * `createContract`, it throws on failure — creating a contract needs a live
 * backend, so the caller surfaces the error rather than falling back.
 */
export async function createContractStream(
  form: FormData,
  onStep: (step: TriageStep) => void
): Promise<ContractDetail> {
  return streamTriageRun("/api/contracts/stream", { method: "POST", body: form }, onStep);
}

/**
 * Streaming twin of {@link triageContract}. On any streaming failure it falls
 * back to the fixture (mirroring the non-streaming path) so the console stays
 * usable offline.
 */
export async function triageContractStream(
  id: string,
  onStep: (step: TriageStep) => void
): Promise<ContractDetail | undefined> {
  try {
    return await streamTriageRun(
      `/api/contracts/${encodeURIComponent(id)}/triage/stream`,
      { method: "POST" },
      onStep
    );
  } catch {
    const fixture = getContractFixtureById(id);
    if (!fixture) return undefined;
    return { ...fixture, ai_status: "triaged" };
  }
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

/**
 * Archive a contract so it drops out of every queue. Best-effort: if the
 * backend doesn't support it (or is unreachable), the store still tracks the
 * archive client-side, so this resolves quietly rather than throwing.
 */
export async function archiveContract(id: string): Promise<void> {
  try {
    await fetchJson(`/api/contracts/${encodeURIComponent(id)}/archive`, { method: "POST" });
  } catch {
    /* offline / not wired — archive is tracked client-side by the store */
  }
}

/** Return an archived contract to its queue. Best-effort, mirrors archive. */
export async function unarchiveContract(id: string): Promise<void> {
  try {
    await fetchJson(`/api/contracts/${encodeURIComponent(id)}/unarchive`, { method: "POST" });
  } catch {
    /* offline / not wired — handled client-side by the store */
  }
}

/** The archived contracts, for Settings → Archived. Empty when unreachable. */
export async function listArchivedContracts(): Promise<ContractSummary[]> {
  try {
    const data = await fetchJson<ContractSummary[]>("/api/contracts/archived");
    return data.map((c) => ({ ...c, queue: queueForContract(c) }));
  } catch {
    return [];
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

/**
 * The desk's playbook sections — the negotiating positions the redline agent
 * maps against. Returns [] if the backend is unreachable (editing the playbook
 * inherently needs a live API), so the screen shows an empty/notice state.
 */
export async function listPlaybook(): Promise<PlaybookSection[]> {
  try {
    return await fetchJson<PlaybookSection[]>("/api/playbook");
  } catch {
    return [];
  }
}

/**
 * Save a reviewer's edit to one playbook section. Throws on failure — persisting
 * a playbook change requires a live backend, so the caller surfaces the error.
 */
export async function updatePlaybookSection(
  section: string,
  update: PlaybookSectionUpdate
): Promise<PlaybookSection> {
  return fetchJson<PlaybookSection>(
    `/api/playbook/sections/${encodeURIComponent(section)}`,
    { method: "PUT", body: JSON.stringify(update) }
  );
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
