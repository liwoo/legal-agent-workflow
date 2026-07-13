# Evals

20 reviewed contracts held out as an evaluation set, in two parallel copies:

- **`without-edits/CR-XXXX-NNN/`** — the contract as it *arrived* (input). `edit-log.json`
  is empty (`[]`) and `metadata.json` has `status: "received"` with `date_signed` removed.
- **`with-edits/CR-XXXX-NNN/`** — the same contract after human review (gold output).
  `edit-log.json` holds the applied edits with their legal basis, and `metadata.json`
  keeps the final `status` / `date_signed`.

The PDF document is identical in both copies; the edit signal lives in `edit-log.json`
and the `status` metadata. A triage/review workflow runs against `without-edits/` and is
scored against `with-edits/`.

The 20 were chosen as a representative spread across years (2025/2026), contract types
(NDA, order forms, DPAs, supplier/framework agreements, SOWs, amendments, renewals,
reseller/referral/sponsorship), and edit counts (0–4 edits per contract).
