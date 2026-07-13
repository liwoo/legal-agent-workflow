import type { LucideIcon } from "lucide-react";
import { Loader2 } from "lucide-react";

import { cn } from "@/src/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  /** Renders a spinner instead of the icon — for the "still loading" phase. */
  loading?: boolean;
  className?: string;
}

/**
 * Consistent placeholder for any view with no data to show — an empty queue,
 * no policies yet, a failed load, or the brief loading phase. Icon in a soft
 * circle, a short title, and an optional one-line description.
 */
export function EmptyState({ icon: Icon, title, description, action, loading, className }: EmptyStateProps) {
  const Glyph = loading ? Loader2 : Icon;
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-14 text-center",
        className
      )}
    >
      {Glyph ? (
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Glyph className={cn("h-5 w-5", loading && "animate-spin")} />
        </span>
      ) : null}
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description ? <p className="mx-auto max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
