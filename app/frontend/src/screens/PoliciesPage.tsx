"use client";

import * as React from "react";
import { BookText } from "lucide-react";

import { EmptyState } from "@/src/components/empty-state";
import { SettingsTabs } from "@/src/components/settings-tabs";
import { InfoHint } from "@/src/components/info-hint";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { listPolicies } from "@/src/lib/api";
import type { Policy } from "@/src/types";

export function PoliciesPage() {
  const [policies, setPolicies] = React.useState<Policy[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    void listPolicies().then((data) => {
      if (!cancelled) {
        setPolicies(data);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <InfoHint>The company rules the assistant checks every contract against.</InfoHint>
      </div>

      <SettingsTabs />

      {loading ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState loading title="Loading policies…" />
          </CardContent>
        </Card>
      ) : policies.length === 0 ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={BookText}
              title="No policies yet"
              description="Once policies are added, they’ll appear here and the assistant will check contracts against them."
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {policies.map((p) => (
            <Card key={p.id}>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <BookText className="h-4 w-4" />
                  </span>
                  <div>
                    <CardTitle className="text-base">{p.title}</CardTitle>
                    <CardDescription className="font-mono text-xs">{p.id}</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{p.summary}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
