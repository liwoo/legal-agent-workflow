import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { FileSignature, Gauge, Inbox, ListChecks, Scale, ShieldCheck } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { InfoHint } from "@/src/components/info-hint";

/**
 * Plain-language explainer for anyone opening the console without prior
 * context. The contract detail modal deep-links into these sections
 * (e.g. /reference#confidence) via small "Learn more" links, so the heavy
 * definitions live here rather than crowding every contract view.
 */

interface RefSection {
  id: string;
  title: string;
  icon: LucideIcon;
  body: React.ReactNode;
}

const SECTIONS: RefSection[] = [
  {
    id: "confidence",
    title: "What “confidence” means",
    icon: Gauge,
    body: (
      <>
        <p>
          Confidence is <strong>how sure the assistant is about its own reading</strong> of a contract — not a
          score of the contract itself, its risk, or its value.
        </p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <span className="font-medium text-success">High</span> — the paper matched a known template and playbook
            cleanly, so the assistant is confident in what it found.
          </li>
          <li>
            <span className="font-medium text-warning">Medium</span> — mostly recognisable, but with wording the
            assistant is less certain about. Worth a glance.
          </li>
          <li>
            <span className="font-medium text-destructive">Low</span> — unusual paper the assistant couldn’t map
            confidently. Read it yourself before trusting the summary.
          </li>
        </ul>
        <p className="text-muted-foreground">
          A low-confidence item is not necessarily a bad contract — it just means a human should look more closely.
        </p>
      </>
    ),
  },
  {
    id: "queues",
    title: "Where a contract lives",
    icon: Inbox,
    body: (
      <>
        <p>Every contract sits in one of three places, depending on how far it has got:</p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <span className="font-medium text-foreground">Inbox</span> — just arrived, or sent back for more
            information. Waiting to be read.
          </li>
          <li>
            <span className="font-medium text-foreground">Review</span> — the assistant stopped and handed it to a
            person, because something needs a human decision (see{" "}
            <Link href="#outcomes" className="text-primary underline-offset-2 hover:underline">
              outcomes
            </Link>
            ).
          </li>
          <li>
            <span className="font-medium text-foreground">Signed</span> — finished and executed at the desk.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "gates",
    title: "Policy checks",
    icon: ShieldCheck,
    body: (
      <>
        <p>
          Before anything is signed, the assistant runs a few standing checks against company policy. Each one comes
          back as <span className="font-medium text-success">Passed</span>,{" "}
          <span className="font-medium text-warning">Needs action</span>, or{" "}
          <span className="font-medium text-destructive">Blocked</span>.
        </p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <span className="font-medium text-foreground">Data protection</span> — is personal or sensitive data
            involved, and is the paperwork (e.g. a DPIA) in place?
          </li>
          <li>
            <span className="font-medium text-foreground">Statutory checks</span> — anti-bribery, modern slavery, tax,
            and unfair-terms rules.
          </li>
          <li>
            <span className="font-medium text-foreground">Financial cover</span> — does what’s being agreed stay within
            our insurance and liability limits?
          </li>
        </ul>
        <p className="text-muted-foreground">
          A single <span className="font-medium text-destructive">Blocked</span> check stops the whole contract until a
          person clears it. The exact rules live in{" "}
          <Link href="/settings/policies" className="text-primary underline-offset-2 hover:underline">
            Settings → Policies
          </Link>
          .
        </p>
      </>
    ),
  },
  {
    id: "redlines",
    title: "Proposed changes (“redlines”)",
    icon: ListChecks,
    body: (
      <>
        <p>
          A redline is a change the other side wants to make to the contract wording. The assistant grades each one
          against our playbook:
        </p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <span className="font-medium text-foreground">Standard change</span> — within what the desk can agree.
          </li>
          <li>
            <span className="font-medium text-foreground">Acceptable fallback</span> — not our first choice, but on the
            approved list of compromises.
          </li>
          <li>
            <span className="font-medium text-foreground">Refusal point</span> — a line we don’t cross without senior
            sign-off; this is what usually triggers an escalation.
          </li>
          <li>
            <span className="font-medium text-foreground">Off-playbook</span> — novel wording with no pre-agreed
            position, so a person has to decide.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "outcomes",
    title: "Outcomes",
    icon: Scale,
    body: (
      <>
        <p>When the assistant finishes, a contract lands on one of these:</p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <span className="font-medium text-success">Signed</span> — executed. It may note “no edits”, “desk edits”,
            or “with a recorded deviation” if a small, logged exception was made.
          </li>
          <li>
            <span className="font-medium text-warning">Needs more info</span> — sent back because something was missing.
          </li>
          <li>
            <span className="font-medium text-warning">Business decision</span> — the terms are fine legally, but
            someone needs to make a commercial call.
          </li>
          <li>
            <span className="font-medium text-destructive">Blocked</span> — a policy check failed; it can’t proceed
            until that’s resolved.
          </li>
          <li>
            <span className="font-medium text-destructive">Escalated</span> — raised to a senior owner (often against a
            deadline / SLA).
          </li>
          <li>
            <span className="font-medium text-muted-foreground">Declined</span> — a reviewer decided not to proceed.
          </li>
        </ul>
      </>
    ),
  },
];

export function ReferencePage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">How this works</h1>
        <InfoHint>A quick plain-language guide to the terms you’ll see around the console.</InfoHint>
      </div>

      <nav aria-label="On this page" className="flex flex-wrap gap-2">
        {SECTIONS.map((s) => (
          <Link
            key={s.id}
            href={`#${s.id}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
          >
            <s.icon className="h-3.5 w-3.5" />
            {s.title}
          </Link>
        ))}
      </nav>

      <div className="space-y-6">
        {SECTIONS.map((s) => (
          <Card key={s.id} id={s.id} className="scroll-mt-24">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <s.icon className="h-4 w-4" />
                </span>
                {s.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-relaxed text-foreground">{s.body}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
