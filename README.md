# Contract Triage — Agent Framework + Aspire

An end-to-end demo that turns the abstract contract-review decision graph
([`agent-graph.mmd`](agent-graph.mmd)) into a running application:

- **`agent/`** — a **Microsoft Agent Framework** workflow that implements the
  graph (intake → classify → policy-gate fan-out → negotiability → bounded
  redline loop → approval, with a re-entrant human-in-the-loop interrupt). It
  exposes a **FastAPI** for the UI and the **Agent Framework DevUI** for
  interactive debugging.
- **`frontend/`** — a **Next.js 14** review console (neutral-themed, based on the
  [triaj](https://github.com/liwoo/triaj) triage app): contract queues, a rich
  detail modal, and the agent graph with each contract's path highlighted.
- **`apphost/`** — an **Aspire** AppHost authored in **TypeScript** that
  orchestrates the DevUI, the FastAPI backend, and the frontend, wiring service
  discovery between them.

```
                ┌─────────────────────────── Aspire AppHost (TypeScript) ───────────────────────────┐
                │                                                                                    │
   browser ───► │   frontend (Next.js :3000) ──HTTP──► api (FastAPI :8000) ──► Agent Framework       │
                │            │                                                    workflow (graph)     │
                │            └──link──► devui (Agent Framework DevUI :8080) ──────┘                    │
                └────────────────────────────────────────────────────────────────────────────────────┘
```

The workflow runs **fully offline** on deterministic, corpus-grounded heuristics
— no API key required. Add an OpenAI / Azure OpenAI key to `agent/.env` to enable
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
cd agent && uv venv --python 3.12 && source .venv/bin/activate \
  && uv pip install -e . --prerelease=allow && cd ..

# 2. frontend deps
cd frontend && npm install && cd ..

# 3. orchestrate everything (DevUI + API + frontend + dashboard)
cd apphost && npm install && aspire run
```

`aspire run` generates its TypeScript SDK, starts all three resources, and opens
the Aspire dashboard. The frontend receives the backend URL via service
discovery (`NEXT_PUBLIC_API_BASE_URL`).

### Option B — plain scripts (no Aspire)

```bash
cd agent && uv venv --python 3.12 && source .venv/bin/activate \
  && uv pip install -e . --prerelease=allow && cd ..
cd frontend && npm install && cd ..
./scripts/dev.sh          # DevUI :8080 · API :8000 · frontend :3000
```

### Endpoints

| Service | URL |
|---|---|
| Review console (frontend) | http://localhost:3000 |
| Triage API (FastAPI)      | http://localhost:8000/api/health |
| Agent Framework DevUI     | http://localhost:8080 |

## How the graph maps to code

| agent-graph.mmd | code |
|---|---|
| shared `State` | `agent/contract_triage/state.py` — `TriageState` |
| nodes / routers / validators / HITL | `agent/contract_triage/executors.py` |
| graph wiring (switch-case, fan-out/in) | `agent/contract_triage/workflow.py` |
| classification + playbook judgment | `agent/contract_triage/heuristics.py` |
| the 10 inbox items | `agent/contract_triage/data.py` (mirrors `contract-inbox.md`) |

See [`agent/README.md`](agent/README.md), [`frontend/README.md`](frontend/README.md)
and [`apphost/apphost.mts`](apphost/apphost.mts) for details.

> The Aspire TypeScript AppHost is a young, fast-moving surface; if a builder
> method name differs in your installed Aspire version, `aspire run` regenerates
> the SDK, or use Option B.
