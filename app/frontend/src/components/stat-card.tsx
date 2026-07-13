import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/src/components/ui/card";
import { InfoHint } from "@/src/components/info-hint";
import { cn } from "@/src/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  icon?: LucideIcon;
  tone?: "default" | "success" | "warning" | "destructive";
  className?: string;
}

const TONE_CLASSES: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  destructive: "bg-destructive/10 text-destructive",
};

/** A single KPI card for the dashboard — large value, label, optional hint (in a tooltip) and icon. */
export function StatCard({ label, value, hint, icon: Icon, tone = "default", className }: StatCardProps) {
  return (
    <Card className={cn("transition-shadow hover:shadow-md", className)}>
      <CardContent className="flex items-start justify-between gap-4 p-6">
        <div className="flex flex-col gap-1.5">
          <span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
            {label}
            {hint ? <InfoHint>{hint}</InfoHint> : null}
          </span>
          <span className="text-3xl font-semibold tracking-tight text-foreground">{value}</span>
        </div>
        {Icon ? (
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", TONE_CLASSES[tone])}>
            <Icon className="h-5 w-5" />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
