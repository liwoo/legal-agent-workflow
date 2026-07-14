"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileSignature, type LucideIcon, Inbox, Scale } from "lucide-react";

import { cn } from "@/src/lib/utils";

interface QueueTabsProps {
  counts: {
    inbox: number;
    review: number;
    signed: number;
  };
}

const TABS: { href: string; label: string; key: keyof QueueTabsProps["counts"]; icon: LucideIcon }[] = [
  { href: "/contracts/inbox", label: "Inbox", key: "inbox", icon: Inbox },
  { href: "/contracts/review", label: "Review", key: "review", icon: Scale },
  { href: "/contracts/signed", label: "Ready to sign", key: "signed", icon: FileSignature },
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
        const Icon = tab.icon;
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
            <Icon className="h-4 w-4" />
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
