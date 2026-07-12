import { orgName } from "@/src/lib/seo";

/** Minimal, neutral footer — no government/public-sector styling. */
export function AppFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border">
      <div className="container flex flex-col items-center justify-between gap-2 py-6 text-xs text-muted-foreground sm:flex-row">
        <p>
          © {year} {orgName} — internal tool
        </p>
        <p>Simulated data for internal review purposes only.</p>
      </div>
    </footer>
  );
}
