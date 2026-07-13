"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookText, type LucideIcon, SlidersHorizontal } from "lucide-react";

import { cn } from "@/src/lib/utils";

const TABS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/settings", label: "General", icon: SlidersHorizontal },
  { href: "/settings/policies", label: "Policies", icon: BookText },
];

/**
 * Sub-navigation for the Settings section, styled as an underline tab strip
 * to match QueueTabs. Policies live under Settings — the playbook the agent
 * gates are grounded in is configuration, not an operational queue.
 */
export function SettingsTabs() {
  const pathname = usePathname();

  return (
    <nav aria-label="Settings sections" className="flex items-center gap-1 border-b border-border">
      {TABS.map((tab) => {
        // "/settings" would match every sub-route with startsWith, so match it exactly.
        const active = tab.href === "/settings" ? pathname === tab.href : pathname?.startsWith(tab.href);
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
            {active ? (
              <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary" aria-hidden="true" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
