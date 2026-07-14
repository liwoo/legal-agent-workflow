import { cn } from "@/src/lib/utils";

interface ScoreBadgeProps {
  score: number | null;
  className?: string;
  /** Render a larger, more prominent variant for the detail modal header. */
  size?: "sm" | "lg";
}

/**
 * How sure the assistant is about its own reading of a contract — NOT a
 * measure of risk or contract value. We show the raw percentage with a
 * colour dot banding it (green / amber / red) so the confidence level still
 * reads at a glance. The larger modal variant spells out "confidence"; the
 * tooltip disambiguates it from a score of the contract itself.
 */
export function ScoreBadge({ score, className, size = "sm" }: ScoreBadgeProps) {
  const band =
    score === null
      ? { dot: "bg-muted-foreground/40", text: "text-muted-foreground" }
      : score >= 75
        ? { dot: "bg-success", text: "text-foreground" }
        : score >= 45
          ? { dot: "bg-warning", text: "text-foreground" }
          : { dot: "bg-destructive", text: "text-foreground" };

  const label =
    score === null ? "Not yet assessed" : size === "lg" ? `${score}% confidence` : `${score}%`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium",
        band.text,
        size === "lg" && "gap-2 text-sm",
        className
      )}
      title={score === null ? "The assistant has not read this item yet" : `Assistant confidence: ${score}%`}
    >
      <span className={cn("h-2 w-2 shrink-0 rounded-full", band.dot, size === "lg" && "h-2.5 w-2.5")} aria-hidden="true" />
      {label}
    </span>
  );
}
