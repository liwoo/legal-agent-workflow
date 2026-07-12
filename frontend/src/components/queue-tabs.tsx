"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/src/lib/utils";

interface QueueTabsProps {
  counts: {
    pending: number;
    approved: number;
    quarantined: number;
  };
}

const TABS: { href: string; label: string; key: keyof QueueTabsProps["counts"] }[] = [
  { href: "/contracts/pending", label: "Pending", key: "pending" },
  { href: "/contracts/approved", label: "Approved", key: "approved" },
  { href: "/contracts/quarantined", label: "Quarantined", key: "quarantined" },
];

/**
 * Top-level navigation between the three contract queues, styled as an
 * underline tab strip. Shows a live count badge per queue and highlights
 * the active route.
 */
export function QueueTabs({ counts }: QueueTabsProps) {
  const pathname = usePathname();

  return (
    <nav aria-label="Contract queues" className="flex items-center gap-1 border-b border-border">
      {TABS.map((tab) => {
        const active = pathname?.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
              active && "text-foreground"
            )}
          >
            {tab.label}
            <span
              className={cn(
                "inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-semibold tabular-nums",
                active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              )}
            >
              {counts[tab.key]}
            </span>
            {active ? (
              <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary" aria-hidden="true" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
