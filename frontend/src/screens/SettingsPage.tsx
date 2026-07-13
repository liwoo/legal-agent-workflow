"use client";

import * as React from "react";
import { CheckCircle2, XCircle } from "lucide-react";

import { ModeToggle } from "@/src/components/mode-toggle";
import { SettingsTabs } from "@/src/components/settings-tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Separator } from "@/src/components/ui/separator";
import { apiEnabled, getApiBaseUrl } from "@/src/lib/api";
import { description, orgName, siteName } from "@/src/lib/seo";

export function SettingsPage() {
  const [online, setOnline] = React.useState<boolean | null>(null);
  const baseUrl = getApiBaseUrl();

  React.useEffect(() => {
    void apiEnabled().then(setOnline);
  }, []);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Backend connection, appearance, policies, and about.</p>
      </div>

      <SettingsTabs />

      <div className="grid items-start gap-6 sm:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Backend</CardTitle>
          <CardDescription>The Agent Framework FastAPI the console reads from.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Row label="API base URL">
            <code className="rounded bg-muted px-2 py-1 text-xs">{baseUrl}</code>
          </Row>
          <Separator />
          <Row label="Status">
            {online === null ? (
              <span className="text-sm text-muted-foreground">Checking…</span>
            ) : online ? (
              <span className="inline-flex items-center gap-1.5 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" /> Connected (live data)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-sm text-warning">
                <XCircle className="h-4 w-4" /> Offline — showing local fixtures
              </span>
            )}
          </Row>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Appearance</CardTitle>
          <CardDescription>Light, dark, or match your system.</CardDescription>
        </CardHeader>
        <CardContent>
          <Row label="Theme">
            <ModeToggle />
          </Row>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">About</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">{siteName}</p>
          <p>{description}</p>
          <p className="text-xs">© {orgName} — internal tool.</p>
        </CardContent>
      </Card>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {children}
    </div>
  );
}
