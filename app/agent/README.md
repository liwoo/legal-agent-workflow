# Contract-Triage Agent (Microsoft Agent Framework)

A stateful [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
**workflow** that implements the abstract contract-review decision graph in
[`../../docs/agent-graph.mmd`](../../docs/agent-graph.mmd). Every node reads/writes one shared
`TriageState`; routers branch on it; three policy validators fan out and are
gathered; a single re-entrant **human gate** interrupts the run for a reviewer
decision and resumes on their response.

It ships two surfaces:

- **FastAPI** (`contract_triage.io.api`) — the REST the Next.js console consumes.
- **DevUI** (`contract_triage.devui_app`) — the Agent Framework developer UI to
  run, inspect and step through the workflow (and drive the human-gate
  interrupt) at `http://localhost:8080`.

> **New to the code (or to the Agent Framework)?** Start with the guided,
> top-to-bottom reading tour in
> [`contract_triage/agents/README.md`](contract_triage/agents/README.md) — it
> explains every framework concept in reading order, with links to the MAF docs.

The agent is **fully LLM-first**: the model (`agents/`) makes every
substantive judgment the routers branch on — the six-axis classification, the
POL-* policy gates, the redline→playbook mapping — plus the reviewer
explanation, and the helper agents are surfaced in DevUI. A chat client
(OpenAI/Azure OpenAI) is therefore **required** — set `OPENAI_API_KEY` in
`.env`; without one the decision nodes raise `LLMUnavailableError`. The
`workflow.py` graph is pure control flow (routers, fan-out/in, the human gate);
only the judgments inside the nodes are the model's. The test suite swaps in a
deterministic offline double (`tests/_fake_brain.py`) so the graph is exercised
without live API calls.

## Layout

The package groups by concern: the thin launchers sit at the root, the graph is
split into its **nodes** (`executors/`) and its **wiring** (`edges/`), the
**brain** (LLM calls + prompts) lives under `agents/`, the **types** under
`models/`, and everything that touches the HTTP boundary or a store is under `io/`.

```
contract_triage/
  devui_app.py      # DevUI serve() entrypoint (root entry point)
  __main__.py       # `python -m contract_triage` → uvicorn (serves io.api:app)
  service.py        # runs the workflow, serialises to the API contract, HITL registry
  config.py         # loads .env so OPENAI_API_KEY is picked up standalone or under `make up`

  agents/           # the LLM brain: classification, gates, redlines, explanation (+ DevUI agents)
    __init__.py     #   the model calls + structured-output schemas
    prompts/        #   one *.md file per system prompt (edit the prompts here)
    README.md       #   ← guided, top-to-bottom reading tour of this codebase (start here)

  models/           # the types the whole app speaks
    domain.py       # vendored copy of ../../docs/models.py — the Pydantic domain types
    state.py        # TriageState (the shared message) + request/interrupt envelopes

  executors/        # graph nodes — one Executor per node in agent-graph.mmd, grouped by stage
    intake.py       #   ingest, classify, intake gate, fast-path guard
    gates.py        #   the policy-validator fan-out → gather → outcome
    negotiability.py#   non-negotiable fork / gap analysis
    redline.py      #   the bounded redline loop
    approval.py     #   set signer, sign, terminal SIGNED side-effects
    human_gate.py   #   the re-entrant human interrupt + DECLINED / ESCALATED
    finalize.py     #   shared scoring / explanation / persistence helpers

  edges/            # graph wiring
    workflow.py     #   WorkflowBuilder: switch-case routers, fan-out/in, HITL
    graph_spec.py   #   static nodes/edges for GET /api/workflow/graph

  io/               # HTTP boundary + persistence & external systems (resilient — a missing store is a no-op)
    api.py          #   FastAPI app — the REST surface (ASGI target: contract_triage.io.api:app)
    db.py           #   SQLite results/decisions
    repository.py   #   the contracts register
    storage.py      #   S3/MinIO documents
    playbook.py     #   the grounded negotiating positions
    pdf.py          #   intake PDF ingestion
    data.py         #   the 10 inbox items + inherited prior-contract flags
    observability.py#   OpenTelemetry → Langfuse
```

## Run

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e . --prerelease=allow

# FastAPI backend  → http://localhost:8000
python -m contract_triage            # or: triage-api

# DevUI            → http://localhost:8080
python -m contract_triage.devui_app  # or: triage-devui
```

Normally you run both (plus the frontend) together via `make up` from the repo
root.

## API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/health` | liveness |
| GET  | `/api/contracts` | inbox + triage summaries |
| GET  | `/api/contracts/{id}` | full triage detail |
| POST | `/api/contracts/{id}/triage` | run the workflow |
| POST | `/api/contracts/{id}/resolve` | resume a paused human-gate run (`{decision, note}`) |
| GET  | `/api/workflow/graph` | nodes/edges for the graph view |
| GET  | `/api/policies` | policy register |

## Notes

- `models/domain.py` is a copy of `../../docs/models.py` so the agent is a
  self-contained, deployable package; keep them in sync if the domain types change.
- The human gate is a genuine Agent Framework `request_info` interrupt. In the
  app flow a paused run lands the contract in the reviewer's queue; `/resolve`
  resumes it (resolved → sign, declined → DECLINED, escalated → ESCALATED). To
  keep the loop bounded, resume routes to `approval` rather than back to
  `classify` as the abstract diagram shows.
