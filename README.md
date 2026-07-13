# Contract Triage — Agent Framework + Aspire

An end-to-end demo that turns the abstract contract-review decision graph
([`docs/agent-graph.mmd`](docs/agent-graph.mmd)) into a running application.

The repository is organised into four top-level folders:

- **`host/`** — an **Aspire** AppHost authored in **TypeScript** that
  orchestrates the DevUI, the FastAPI backend, and the frontend, wiring service
  discovery between them.
- **`app/`** — the application components:
  - **`app/agent/`** — a **Microsoft Agent Framework** workflow that implements
    the graph (intake → classify → policy-gate fan-out → negotiability → bounded
    redline loop → approval, with a re-entrant human-in-the-loop interrupt). It
    exposes a **FastAPI** for the UI and the **Agent Framework DevUI** for
    interactive debugging.
  - **`app/frontend/`** — a **Next.js 14** review console (neutral-themed, based
    on the [triaj](https://github.com/liwoo/triaj) triage app): contract queues,
    a rich detail modal, and the agent graph with each contract's path highlighted.
  - **`app/scripts/`** — a plain launcher (`dev.sh`) for running the stack
    without Aspire.
- **`data/`** — the domain corpus: the contract registers, the policy library,
  the reviewed `contracts/` back-catalogue, the `test/` intake fixtures, and the
  held-out `evals/` set.
- **`docs/`** — the decision framework, requirements, the `agent-graph.mmd`
  diagram, the canonical `models.py` domain types, and the design audit.

```
                ┌─────────────────────────── Aspire AppHost (TypeScript) ───────────────────────────┐
                │                                                                                    │
   browser ───► │   frontend (Next.js :3000) ──HTTP──► api (FastAPI :8000) ──► Agent Framework       │
                │            │                                                    workflow (graph)     │
                │            └──link──► devui (Agent Framework DevUI :8080) ──────┘                    │
                └────────────────────────────────────────────────────────────────────────────────────┘
```

The workflow runs **fully offline** on deterministic, corpus-grounded heuristics
— no API key required. Add an OpenAI / Azure OpenAI key to `app/agent/.env` to enable
LLM refinement and natural-language explanations.

## Prerequisites

- **Python 3.10+** and [`uv`](https://docs.astral.sh/uv/)
- **Node ≥ 20.19** (Next.js 14 and the Aspire TypeScript AppHost both require it)
- **Aspire CLI** — `curl -sSL https://aspire.dev/install.sh | bash` (or
  `npm i -g @microsoft/aspire-cli`). Only needed for the one-command path.

## Run it

### Option A — one command via Aspire (recommended)

```bash
# 1. backend deps
cd app/agent && uv venv --python 3.12 && source .venv/bin/activate \
  && uv pip install -e . --prerelease=allow && cd ../..

# 2. frontend deps
cd app/frontend && npm install && cd ../..

# 3. orchestrate everything (DevUI + API + frontend + dashboard)
cd host && npm install && aspire run
```

`aspire run` generates its TypeScript SDK, starts all three resources, and opens
the Aspire dashboard. The frontend receives the backend URL via service
discovery (`NEXT_PUBLIC_API_BASE_URL`).

### Option B — plain scripts (no Aspire)

```bash
cd app/agent && uv venv --python 3.12 && source .venv/bin/activate \
  && uv pip install -e . --prerelease=allow && cd ../..
cd app/frontend && npm install && cd ../..
./app/scripts/dev.sh      # DevUI :8080 · API :8000 · frontend :3000
```

### Endpoints

| Service | URL |
|---|---|
| Review console (frontend) | http://localhost:3000 |
| Triage API (FastAPI)      | http://localhost:8000/api/health |
| Agent Framework DevUI     | http://localhost:8080 |
| Langfuse (traces)         | http://localhost:3001 |

## Observability (Langfuse)

The Aspire AppHost also runs a **self-hosted [Langfuse](https://langfuse.com)**
stack (Postgres, ClickHouse, Redis, MinIO, plus the Langfuse web + worker) and
wires the agent's **Microsoft Agent Framework OpenTelemetry** traces to it. Every
triage run shows up as a trace — the top-level `triage_contract` span, the
`invoke_agent` call, each LLM `chat`, and each tool call — so you can see prompts,
responses, token usage and latency per contract.

- Requires **Docker** (the six Langfuse containers). The agent buffers and retries,
  so the app starts immediately and traces appear once Langfuse is healthy.
- Open http://localhost:3001 and sign in with **`admin@northgate.local` /
  `langfuse-admin`** — the project and API keys are provisioned headlessly, so no
  setup is needed. Traces land in the **Contract Triage** project.
- Only meaningful when an LLM is configured (see below) — offline heuristic runs
  still produce the workflow span but no LLM `chat` spans.
- Credentials are demo defaults in [`host/apphost.mts`](host/apphost.mts);
  `ENABLE_SENSITIVE_DATA=true` captures prompts/responses (dev only). Without
  Aspire (Option B), point the `OTEL_*` vars in `app/agent/.env` at your own
  Langfuse (self-hosted or Cloud) — see
  [`app/agent/.env.example`](app/agent/.env.example).

## How the graph maps to code

| agent-graph.mmd | code |
|---|---|
| shared `State` | `app/agent/contract_triage/state.py` — `TriageState` |
| nodes / routers / validators / HITL | `app/agent/contract_triage/executors.py` |
| graph wiring (switch-case, fan-out/in) | `app/agent/contract_triage/workflow.py` |
| classification + playbook judgment | `app/agent/contract_triage/heuristics.py` |
| the 10 inbox items | `app/agent/contract_triage/data.py` (mirrors `data/contract-inbox.md`) |

See [`app/agent/README.md`](app/agent/README.md),
[`app/frontend/README.md`](app/frontend/README.md) and
[`host/apphost.mts`](host/apphost.mts) for details.

> The Aspire TypeScript AppHost is a young, fast-moving surface; if a builder
> method name differs in your installed Aspire version, `aspire run` regenerates
> the SDK, or use Option B.
