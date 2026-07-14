import { Loader2 } from "lucide-react";

import { Badge } from "@/src/components/ui/badge";
import { cn, titleCase } from "@/src/lib/utils";
import type { AiStatus, EndState } from "@/src/types";

interface StateBadgeProps {
  aiStatus: AiStatus;
  endState: EndState;
  className?: string;
}

const END_STATE_STYLE: Record<NonNullable<EndState>, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
  signed_no_edits: { label: "Ready — no edits", variant: "success" },
  signed_desk_edits: { label: "Ready — desk edits", variant: "success" },
  signed_with_deviation: { label: "Ready — deviation", variant: "success" },
  escalated: { label: "Escalated", variant: "destructive" },
  blocked: { label: "Blocked", variant: "destructive" },
  more_info_needed: { label: "More info needed", variant: "warning" },
  business_decision: { label: "Business decision", variant: "warning" },
  declined: { label: "Declined", variant: "secondary" },
};

/**
 * Renders the lifecycle state of a contract: either its AI processing
 * status (untriaged / processing) when there's no end state yet, or the
 * resolved end_state with an appropriate color.
 */
export function StateBadge({ aiStatus, endState, className }: StateBadgeProps) {
  if (endState) {
    const style = END_STATE_STYLE[endState];
    return (
      <Badge variant={style.variant} className={cn(className)}>
        {style.label}
      </Badge>
    );
  }

  if (aiStatus === "processing") {
    return (
      <Badge variant="secondary" className={cn("gap-1", className)}>
        <Loader2 className="h-3 w-3 animate-spin" />
        Triaging
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className={cn(className)}>
      {titleCase(aiStatus)}
    </Badge>
  );
}
