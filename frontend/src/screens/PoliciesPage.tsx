"use client";

import * as React from "react";
import { BookText } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { listPolicies } from "@/src/lib/api";
import type { Policy } from "@/src/types";

export function PoliciesPage() {
  const [policies, setPolicies] = React.useState<Policy[]>([]);

  React.useEffect(() => {
    void listPolicies().then(setPolicies);
  }, []);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Policies</h1>
        <p className="text-sm text-muted-foreground">
          The playbook and policy register the agent gates and redline mapping are grounded in.
        </p>
      </div>

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
    </div>
  );
}
