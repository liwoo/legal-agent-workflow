import { cn } from "@/src/lib/utils";

interface ScoreBadgeProps {
  score: number | null;
  className?: string;
  /** Render a larger, more prominent variant for the detail modal header. */
  size?: "sm" | "lg";
}

/**
 * How sure the assistant is about its own reading of a contract — NOT a
 * measure of risk or contract value. We lead with a plain-language band
 * (High / Medium / Low) and a colour dot rather than a bare "82%", which
 * newcomers tend to misread as a score of the contract itself. The raw
 * percentage is preserved in the tooltip and still drives table sorting.
 */
export function ScoreBadge({ score, className, size = "sm" }: ScoreBadgeProps) {
  const band =
    score === null
      ? { label: "Not yet assessed", dot: "bg-muted-foreground/40", text: "text-muted-foreground" }
      : score >= 75
        ? { label: "High confidence", dot: "bg-success", text: "text-foreground" }
        : score >= 45
          ? { label: "Medium confidence", dot: "bg-warning", text: "text-foreground" }
          : { label: "Low confidence", dot: "bg-destructive", text: "text-foreground" };

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
      {band.label}
    </span>
  );
}
