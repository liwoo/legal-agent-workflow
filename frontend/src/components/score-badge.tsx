import { cn } from "@/src/lib/utils";

interface ScoreBadgeProps {
  score: number | null;
  className?: string;
  /** Render a larger, more prominent variant for the detail modal header. */
  size?: "sm" | "lg";
}

/**
 * Displays an AI confidence/triage score (0-100) with color banding:
 * high (>=75) green, medium (45-74) amber, low (<45) red. `null` renders
 * a neutral "not yet scored" state.
 */
export function ScoreBadge({ score, className, size = "sm" }: ScoreBadgeProps) {
  if (score === null) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-md border border-border bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground",
          size === "lg" && "px-3 py-1 text-sm",
          className
        )}
      >
        Not scored
      </span>
    );
  }

  const band =
    score >= 75
      ? { label: "High confidence", classes: "bg-success/10 text-success border-success/30" }
      : score >= 45
        ? { label: "Medium confidence", classes: "bg-warning/10 text-warning border-warning/30" }
        : { label: "Low confidence", classes: "bg-destructive/10 text-destructive border-destructive/30" };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold tabular-nums",
        band.classes,
        size === "lg" && "gap-2 px-3 py-1 text-base",
        className
      )}
      title={band.label}
    >
      {score}
      <span className={cn("font-normal opacity-70", size === "sm" && "text-[10px]", size === "lg" && "text-xs")}>
        /100
      </span>
    </span>
  );
}
