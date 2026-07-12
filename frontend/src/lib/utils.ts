import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { ContractSummary, EndState, Queue } from "@/src/types";

/**
 * Merge Tailwind class names, resolving conflicting utility classes in
 * favour of the last one supplied. Standard shadcn/ui helper.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** End states that land a contract in the "approved" queue. */
export const APPROVED_END_STATES: readonly EndState[] = [
  "signed_no_edits",
  "signed_desk_edits",
  "signed_with_deviation",
];

/** End states that land a contract in the "quarantined" queue. */
export const QUARANTINED_END_STATES: readonly EndState[] = [
  "escalated",
  "blocked",
  "declined",
  "business_decision",
];

/**
 * Queue-mapping rule shared across the store, dashboard and queue screens:
 *  - approved: end_state in {signed_no_edits, signed_desk_edits, signed_with_deviation}
 *  - quarantined: end_state in {escalated, blocked, declined, business_decision}
 *  - pending: untriaged, or end_state in {more_info_needed, null}
 */
export function queueForContract(
  contract: Pick<ContractSummary, "ai_status" | "end_state">
): Queue {
  const { ai_status, end_state } = contract;

  if (end_state && APPROVED_END_STATES.includes(end_state)) {
    return "approved";
  }
  if (end_state && QUARANTINED_END_STATES.includes(end_state)) {
    return "quarantined";
  }
  // untriaged, processing, more_info_needed, or null end_state
  if (ai_status === "untriaged" || end_state === "more_info_needed" || end_state === null) {
    return "pending";
  }
  return "pending";
}

/** Format an ISO date string as a short, readable date (e.g. "10 Jul 2026"). */
export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Format an ISO date string as a short date + time (e.g. "10 Jul 2026, 09:14"). */
export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Human-readable relative time, e.g. "3h ago", "2d ago". Falls back to a short date. */
export function formatRelative(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";

  const diffMs = now.getTime() - d.getTime();
  const diffSec = Math.round(diffMs / 1000);
  const diffMin = Math.round(diffSec / 60);
  const diffHr = Math.round(diffMin / 60);
  const diffDay = Math.round(diffHr / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return formatDate(iso);
}

/** Convert an enum-ish snake_case string into Title Case for display. */
export function titleCase(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Format a GBP value compactly, e.g. £21,000 or £1.2m. */
export function formatGbp(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  if (value >= 1_000_000) {
    return `£${(value / 1_000_000).toFixed(1)}m`;
  }
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(value);
}
