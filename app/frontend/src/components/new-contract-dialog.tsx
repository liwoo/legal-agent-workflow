"use client";

import * as React from "react";
import { FilePlus2, Loader2 } from "lucide-react";

import { Button } from "@/src/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/src/components/ui/dialog";
import { Input } from "@/src/components/ui/input";
import { Label } from "@/src/components/ui/label";
import { useContracts } from "@/src/store/contracts";
import { cn } from "@/src/lib/utils";

const textareaClass =
  "flex min-h-[72px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50";

/**
 * "New Contract" flow: a modal form that captures the intake facts + an optional
 * PDF, posts them to the backend (persist → store PDF → trigger the agent), and
 * folds the freshly triaged contract into the queue on success.
 */
export function NewContractDialog() {
  const { create } = useContracts();
  const [open, setOpen] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const formRef = React.useRef<HTMLFormElement>(null);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const form = new FormData(event.currentTarget);
      // Unchecked checkboxes don't post; normalise to explicit booleans.
      form.set("is_public_body", form.has("is_public_body") ? "true" : "false");
      form.set("is_regulated", form.has("is_regulated") ? "true" : "false");
      // Drop an empty file input so the backend treats it as "no document".
      const file = form.get("file");
      if (file instanceof File && file.size === 0) form.delete("file");

      await create(form);
      formRef.current?.reset();
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && setOpen(next)}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5">
          <FilePlus2 className="h-4 w-4" />
          <span className="hidden sm:inline">New Contract</span>
          <span className="sm:hidden">New</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New contract</DialogTitle>
          <DialogDescription>
            Capture the intake facts and attach the paper. We&apos;ll store it and run the triage
            assistant straight away.
          </DialogDescription>
        </DialogHeader>

        <form ref={formRef} onSubmit={onSubmit} className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="counterparty">
              Counterparty <span className="text-primary">*</span>
            </Label>
            <Input id="counterparty" name="counterparty" required placeholder="Meridian Freight Solutions Ltd" />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="received_from">Received from</Label>
              <Input id="received_from" name="received_from" placeholder="AE (sales)" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="date_received">Date received</Label>
              <Input id="date_received" name="date_received" type="date" />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="summary">What arrived</Label>
            <textarea
              id="summary"
              name="summary"
              className={cn(textareaClass)}
              placeholder="Counterparty's own mutual NDA paper (5 pages, PDF), unsigned…"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="senders_ask">Sender&apos;s ask</Label>
            <textarea
              id="senders_ask"
              name="senders_ask"
              className={cn(textareaClass)}
              placeholder="Can we sign their NDA as-is so we can book the demo next week?"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="sector">Sector</Label>
              <Input id="sector" name="sector" placeholder="logistics" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="related_contracts">Related contracts</Label>
              <Input id="related_contracts" name="related_contracts" placeholder="CR-2026-046, CR-2025-011" />
            </div>
          </div>

          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" name="is_public_body" className="h-4 w-4 accent-primary" />
              Public body
            </label>
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" name="is_regulated" className="h-4 w-4 accent-primary" />
              Regulated counterparty
            </label>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="file">Intake PDF</Label>
            <Input id="file" name="file" type="file" accept="application/pdf" />
            <p className="text-xs text-muted-foreground">
              Optional — if attached, the assistant reads it and fills in any blanks above.
            </p>
          </div>

          {error ? (
            <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Triaging…
                </>
              ) : (
                "Create & triage"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
