import type { ReactNode } from "react";

import { AppFooter } from "@/src/components/app-footer";
import { AppHeader } from "@/src/components/app-header";
import { ContractsProvider } from "@/src/store/contracts";

/**
 * Top-level layout shell for every authenticated/app route: header with
 * nav, the ContractsProvider (single source of truth for contract data),
 * a constrained main content area, and the footer.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ContractsProvider>
      <div className="flex min-h-screen flex-col bg-background">
        <AppHeader />
        <main className="container flex-1 py-8 md:py-12">{children}</main>
        <AppFooter />
      </div>
    </ContractsProvider>
  );
}
