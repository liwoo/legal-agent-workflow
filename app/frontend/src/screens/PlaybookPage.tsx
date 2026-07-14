"use client";

import * as React from "react";
import { Check, Pencil, Scale, X } from "lucide-react";

import { EmptyState } from "@/src/components/empty-state";
import { InfoHint } from "@/src/components/info-hint";
import { SettingsTabs } from "@/src/components/settings-tabs";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { listPlaybook, updatePlaybookSection } from "@/src/lib/api";
import { cn } from "@/src/lib/utils";
import type { PlaybookSection } from "@/src/types";

export function PlaybookPage() {
  const [sections, setSections] = React.useState<PlaybookSection[]>([]);
  const [loading, setLoading] = React.useState(true);

  // Per-section edit state — only one section is edited at a time.
  const [editing, setEditing] = React.useState<string | null>(null);
  const [draftTitle, setDraftTitle] = React.useState("");
  const [draftGuidance, setDraftGuidance] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    void listPlaybook().then((data) => {
      if (!cancelled) {
        setSections(data);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  function startEdit(s: PlaybookSection) {
    setEditing(s.section);
    setDraftTitle(s.title);
    setDraftGuidance(s.guidance);
    setError(null);
  }

  function cancelEdit() {
    setEditing(null);
    setError(null);
  }

  async function save(section: string) {
    setSaving(true);
    setError(null);
    try {
      const updated = await updatePlaybookSection(section, {
        title: draftTitle.trim(),
        guidance: draftGuidance.trim(),
      });
      setSections((prev) => prev.map((s) => (s.section === section ? updated : s)));
      setEditing(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save. Is the backend running?");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <InfoHint>
          The desk&rsquo;s negotiating positions. The assistant maps every proposed contract
          change against these — edit one and it applies to the next contract triaged.
        </InfoHint>
      </div>

      <SettingsTabs />

      {loading ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState loading title="Loading playbook…" />
          </CardContent>
        </Card>
      ) : sections.length === 0 ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={Scale}
              title="Playbook unavailable"
              description="The playbook is served and edited live — start the backend to view and manage the desk's negotiating positions."
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {sections.map((s) => {
            const isEditing = editing === s.section;
            return (
              <Card key={s.section} className={cn(isEditing && "ring-2 ring-primary/40")}>
                <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
                  <div className="flex items-start gap-3">
                    <Badge variant="outline" className="mt-0.5 font-mono text-xs">
                      §{s.section}
                    </Badge>
                    {isEditing ? (
                      <Input
                        value={draftTitle}
                        onChange={(e) => setDraftTitle(e.target.value)}
                        className="h-8 w-72 font-medium"
                        aria-label="Section title"
                      />
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{s.title}</span>
                        {s.source === "user" ? (
                          <Badge variant="secondary" className="text-[10px]">
                            Edited
                          </Badge>
                        ) : null}
                      </div>
                    )}
                  </div>
                  {!isEditing ? (
                    <Button variant="ghost" size="sm" onClick={() => startEdit(s)}>
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </Button>
                  ) : null}
                </CardHeader>
                <CardContent>
                  {isEditing ? (
                    <div className="space-y-3">
                      <textarea
                        value={draftGuidance}
                        onChange={(e) => setDraftGuidance(e.target.value)}
                        rows={7}
                        aria-label="Section guidance"
                        className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm leading-relaxed shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
                      />
                      {error ? <p className="text-sm text-destructive">{error}</p> : null}
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          onClick={() => void save(s.section)}
                          disabled={saving || !draftTitle.trim() || !draftGuidance.trim()}
                        >
                          <Check className="h-3.5 w-3.5" />
                          {saving ? "Saving…" : "Save"}
                        </Button>
                        <Button variant="outline" size="sm" onClick={cancelEdit} disabled={saving}>
                          <X className="h-3.5 w-3.5" />
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                      {s.guidance}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
