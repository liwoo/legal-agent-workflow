import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Arimo } from "next/font/google";

import { ThemeProvider } from "@/src/components/theme-provider";
import { description, siteName, tagline } from "@/src/lib/seo";
import "./globals.css";

/*
 * PortSwigger's type system is Arial everywhere (see design/portswigger-audit).
 * Arimo is Google Fonts' metric-compatible equivalent — identical metrics to
 * Arial, so the tight-tracking headline signature lands the same while giving
 * us a self-hosted, deterministic web font. 400/500/700 cover ~99% of usage.
 */
const fontSans = Arimo({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: `${siteName} — ${tagline}`,
    template: `%s · ${siteName}`,
  },
  description,
  applicationName: siteName,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={fontSans.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
