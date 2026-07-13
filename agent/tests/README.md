# Agent tests

Node-targeted tests for the contract-triage workflow. Every case is seeded from
**one** physical fixture — the `test/CR-2026-050` intake PDF and its
`metadata.json` — and steers the graph by overriding the intake metadata text.

The split is deliberate:

- **the PDF is always read** — `ingest` reads it from an absolute path via the
  PDF tool (`contract_triage/pdf.py`) and stores the text on the state, so the
  document is genuinely exercised on disk;
- **the metadata drives the branch** — classification is a pure function of the
  intake text (`summary` / `senders_ask` / counterparty flags /
  `related_contracts`), so each node can be targeted deterministically without
  touching the PDF.

## Entry state

`TriageRequest` is a flat set of intake string fields — one plain text box per
field in the DevUI form, no JSON:

- **Required:** `id`, `date_received`, `pdf_path` (the document is always read).
- **Optional, derived from the PDF when blank:** `counterparty`, `summary`,
  `senders_ask`, `name`, `received_from`, `related_contracts`.

The ingest node assembles these into the `InboxItem`, reads the PDF, and fills
any blank intake fact from the document (`pdf.derive_intake`).
`helpers.make_request(**overrides)` builds a request from the shared intake facts
(always supplying the required three); `helpers.triage_meta(**overrides)` runs the
whole graph from it. Pass `summary=""`, `senders_ask=""`, `counterparty=""` to
exercise PDF-only derivation.

## Files

| File | What it pins |
|---|---|
| `test_pdf_tool.py` | the PDF reader: reads the shared PDF, degrades gracefully on a missing path |
| `test_ingest.py`   | metadata → entry `InboxItem`, PDF read into `document_text` |
| `test_nodes.py`    | each router in isolation — the `route`/outcome it sets for a given entry state |
| `test_routing.py`  | full traversals — the terminal end-state *and* which nodes it did/didn't touch |

## Run

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]" --prerelease=allow
pytest
```

## Coverage of the graph

Every router branch is pinned at least once. `test_routing.py` asserts the
"ends here, not there" contrasts:

- `intake_gate` → `more_info` / `blocked` / proceed (diverts before `triage`)
- `triage` → `guard` (fast path) vs `fanout` (full review)
- `guard_check` → `approve` vs `fanout` (personal data still gates)
- `gate_outcome` → `blocked` (short-circuits `negotiability`) vs `clear`
- `negotiability` → `nonneg` (→ `gap_analysis`) vs `negotiable` (→ redline loop)
- `gap_check` → `business_decision` vs `approve`
- `disposition` → `escalate` / `strike` / `fallback` / `hold`
- `human_gate` resume → `declined` / `escalated` / `resolved`

`loop_control`'s `maxed` branch requires `pending_redlines`, which the
deterministic engine never populates end-to-end, so it is pinned at the node
level in `test_nodes.py` with a crafted entry state.
