import Link from "next/link";
import { HelpCircle } from "lucide-react";

import { orgName } from "@/src/lib/seo";

/**
 * Footer — PortSwigger's chrome keeps this a dark navy band in every theme,
 * segmenting the page end from the white/tinted content above it.
 */
export function AppFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-auto bg-[hsl(239,81%,12%)] text-white/70">
      <div className="container flex flex-col items-center justify-between gap-2 py-6 text-xs sm:flex-row">
        <p>
          © {year} {orgName} — internal tool
        </p>
        <div className="flex items-center gap-4">
          <Link href="/reference" className="inline-flex items-center gap-1.5 transition-colors hover:text-white">
            <HelpCircle className="h-3.5 w-3.5" />
            How it works
          </Link>
          <span>Simulated data for internal review only.</span>
        </div>
      </div>
    </footer>
  );
}
