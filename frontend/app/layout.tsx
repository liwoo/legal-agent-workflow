import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ThemeProvider } from "@/src/components/theme-provider";
import { description, siteName, tagline } from "@/src/lib/seo";
import "./globals.css";

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
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
