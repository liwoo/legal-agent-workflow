import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Ban, FileSignature, Inbox, ScanLine, ShieldCheck, UserRound, XCircle } from "lucide-react";

import { cn } from "@/src/lib/utils";
import type { AiStatus, EndState } from "@/src/types";

type Tone = "success" | "warning" | "danger" | "muted" | "pending";

interface ContractJourneyProps {
  aiStatus?: AiStatus;
  endState?: EndState;
  /** "legend" renders the flow as an explainer with no active contract. */
  mode?: "active" | "legend";
  className?: string;
}

const STEPS: { label: string; icon: LucideIcon }[] = [
  { label: "Arrived", icon: Inbox },
  { label: "Reviewed", icon: ScanLine },
  { label: "Checked", icon: ShieldCheck },
];

/** The final step's label/icon/colour depends on how the contract ended. */
function outcomeStep(endState: EndState): { label: string; icon: LucideIcon; tone: Tone } {
  switch (endState) {
    case "signed_no_edits":
    case "signed_desk_edits":
    case "signed_with_deviation":
      return { label: "Ready to sign", icon: FileSignature, tone: "success" };
    case "escalated":
      return { label: "Escalated", icon: AlertTriangle, tone: "danger" };
    case "blocked":
      return { label: "Blocked", icon: Ban, tone: "danger" };
    case "business_decision":
      return { label: "Your call", icon: UserRound, tone: "warning" };
    case "more_info_needed":
      return { label: "More info", icon: UserRound, tone: "warning" };
    case "declined":
      return { label: "Declined", icon: XCircle, tone: "muted" };
    default:
      return { label: "Outcome", icon: FileSignature, tone: "pending" };
  }
}

const TONE_FILL: Record<Tone, string> = {
  success: "border-success bg-success text-white",
  warning: "border-warning bg-warning text-white",
  danger: "border-destructive bg-destructive text-white",
  muted: "border-muted-foreground bg-muted-foreground text-white",
  pending: "border-primary bg-primary text-primary-foreground",
};

/**
 * A friendly, linear "where is this contract" map — the approachable
 * replacement for the technical agent graph. Every contract walks the same
 * path: Arrived → Reviewed → Checked → an outcome. In legend mode it simply
 * explains that path with no contract attached.
 */
export function ContractJourney({ aiStatus, endState = null, mode = "active", className }: ContractJourneyProps) {
  const legend = mode === "legend";
  const outcome = outcomeStep(endState);
  const steps = [...STEPS, { label: outcome.label, icon: outcome.icon }];

  // Which step is currently active (0-based); -1 in legend mode.
  const current = legend
    ? -1
    : aiStatus === "untriaged"
      ? 0
      : endState == null
        ? aiStatus === "processing"
          ? 1
          : 2
        : 3;

  return (
    <ol className={cn("flex items-start", className)}>
      {steps.map((step, i) => {
        const isOutcome = i === steps.length - 1;
        const done = !legend && i < current;
        const active = !legend && i === current;
        const Icon = step.icon;

        const circle = legend
          ? "border-primary/40 bg-primary/5 text-primary"
          : done
            ? "border-primary bg-primary text-primary-foreground"
            : active
              ? isOutcome
                ? TONE_FILL[outcome.tone]
                : "border-primary bg-primary/10 text-primary"
              : "border-border bg-muted text-muted-foreground/50";

        // The connector leading INTO this step is "travelled" once the prior step is done.
        const travelled = legend || i <= current;

        return (
          <li key={i} className="flex flex-1 flex-col items-center last:flex-none">
            <div className="flex w-full items-center">
              {i > 0 ? (
                <span
                  className={cn("h-0.5 flex-1", travelled ? (legend ? "bg-primary/30" : "bg-primary") : "bg-border")}
                  aria-hidden="true"
                />
              ) : (
                <span className="flex-1" aria-hidden="true" />
              )}
              <span
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                  circle
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              {!isOutcome ? (
                <span
                  className={cn("h-0.5 flex-1", legend ? "bg-primary/30" : i < current ? "bg-primary" : "bg-border")}
                  aria-hidden="true"
                />
              ) : (
                <span className="flex-1" aria-hidden="true" />
              )}
            </div>
            <span
              className={cn(
                "mt-1.5 text-center text-xs",
                active || done || legend ? "font-medium text-foreground" : "text-muted-foreground"
              )}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
