"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileSignature, type LucideIcon, Inbox, LayoutDashboard, Scale, Settings, Zap } from "lucide-react";

import { ModeToggle } from "@/src/components/mode-toggle";
import { cn } from "@/src/lib/utils";

const NAV_LINKS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/contracts/inbox", label: "Inbox", icon: Inbox },
  { href: "/contracts/review", label: "Review", icon: Scale },
  { href: "/contracts/signed", label: "Signed", icon: FileSignature },
  { href: "/settings", label: "Settings", icon: Settings },
];

/**
 * Top application header: flash-mark wordmark, primary nav, theme toggle.
 * PortSwigger signature — a 3px brand-orange rule underlines the whole header.
 */
export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b-[3px] border-b-primary bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75">
      <div className="container flex h-16 items-center justify-between gap-4">
        <Link href="/dashboard" className="flex items-center gap-2.5 font-bold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Zap className="h-4.5 w-4.5 fill-current" />
          </span>
          <span className="hidden sm:inline">
            Northgate <span className="text-muted-foreground font-normal">· Contract Review</span>
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => {
            const active =
              link.href === "/dashboard" ? pathname === link.href : pathname?.startsWith(link.href);
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
                  active && "font-semibold text-primary"
                )}
              >
                <Icon className="h-4 w-4" />
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
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
                active && "font-semibold text-primary"
              )}
            >
              <Icon className="h-4 w-4" />
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
