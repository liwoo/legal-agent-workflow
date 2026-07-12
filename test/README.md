# Test

The 10 items that landed in the legal inbox 10–12 July 2026 (`CR-2026-050`…`CR-2026-059`),
none of which has been reviewed yet — no triage, no edits. This is the held-out test set:
the workflow runs against it, but there is no gold output to score against (unlike `evals/`).

Each `CR-2026-05N/` folder contains:

- **`metadata.json`** — intake facts only (type, counterparty, date received, sender, the
  sender's ask, related prior contracts, `status: "received"`).
- **`cr-2026-05n-intake.pdf`** — a one-page intake sheet rendering the same facts.

Source of truth for these entries is `../contract-inbox.md`.
