"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import type { TriageStep } from "@/src/lib/api";
import { cn } from "@/src/lib/utils";

/**
 * Live, append-only log of a streamed triage run. Each ``step`` from the agent
 * is one line — a coloured dot keyed on its kind (matching the detail modal's
 * Timeline tab) plus the label. The latest line spins while the run is in
 * flight, and the panel auto-scrolls to keep it in view. Shared by the New
 * Contract dialog and the "Re-evaluate" button in the detail modal.
 */
export function TriageRunLog({ steps, running }: { steps: TriageStep[]; running: boolean }) {
  const endRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [steps.length]);

  return (
    <div className="rounded-lg border bg-muted/40 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <Loader2 className={cn("h-3.5 w-3.5", running && "animate-spin")} />
        {running ? "Triage assistant is working…" : "Triage complete"}
      </div>
      <ol className="max-h-48 space-y-1.5 overflow-y-auto pr-1">
        {steps.map((step, i) => {
          const isLast = i === steps.length - 1;
          return (
            <li key={i} className="flex items-start gap-2.5 text-sm">
              {running && isLast ? (
                <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" />
              ) : (
                <span
                  className={cn(
                    "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                    step.kind === "success" && "bg-success",
                    step.kind === "warning" && "bg-warning",
                    step.kind === "critical" && "bg-destructive",
                    (!step.kind || step.kind === "info") && "bg-muted-foreground/50"
                  )}
                />
              )}
              <span className="flex-1">
                {step.label}
                {step.detail ? <span className="text-muted-foreground"> — {step.detail}</span> : null}
              </span>
            </li>
          );
        })}
        {running && steps.length === 0 ? (
          <li className="text-sm text-muted-foreground">Starting the agent…</li>
        ) : null}
        <div ref={endRef} />
      </ol>
    </div>
  );
}
