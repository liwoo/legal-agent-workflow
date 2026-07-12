"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Scale } from "lucide-react";

import { ModeToggle } from "@/src/components/mode-toggle";
import { cn } from "@/src/lib/utils";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/contracts/pending", label: "Pending" },
  { href: "/contracts/approved", label: "Approved" },
  { href: "/contracts/quarantined", label: "Quarantined" },
  { href: "/policies", label: "Policies" },
  { href: "/settings", label: "Settings" },
];

/** Top application header: wordmark, primary nav, theme toggle. Sticky, neutral, no chrome. */
export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75">
      <div className="container flex h-16 items-center justify-between gap-4">
        <Link href="/dashboard" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Scale className="h-4.5 w-4.5" />
          </span>
          <span className="hidden sm:inline">
            Northgate <span className="text-muted-foreground font-normal">· Contract Triage</span>
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => {
            const active =
              link.href === "/dashboard" ? pathname === link.href : pathname?.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                  active && "bg-accent text-accent-foreground"
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <ModeToggle />
        </div>
      </div>

      {/* Compact nav for small screens */}
      <nav aria-label="Primary (mobile)" className="container flex items-center gap-1 overflow-x-auto pb-2 md:hidden">
        {NAV_LINKS.map((link) => {
          const active = link.href === "/dashboard" ? pathname === link.href : pathname?.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                active && "bg-accent text-accent-foreground"
              )}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
