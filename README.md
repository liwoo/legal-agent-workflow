# Contract Triage

An end-to-end demo that turns a legal team's contract-review judgement into a
running application — an agent workflow that reads what lands in the inbox,
decides what to do with it, and knows when to stop and ask a human.

---

## What it is — and the problem it solves

A corporate legal team's inbox is mostly noise dressed up as work. Across **79
processed contracts**, **34% were signed with zero edits** and another **25%**
needed exactly one; genuinely bespoke, escalation-worthy reviews are **~8%**.
The **92%** in between is the same handful of moves on repeat — an uncapped
liability clause pulled back to twelve months' fees, net-60 payment terms pushed
to net-30, an auto-renewal struck out. The cost isn't the hard 8%. It's that a
qualified reviewer must **open every contract to learn which bucket it's in**,
and the routine majority drowns the reviews that actually need a lawyer.

**Contract Triage is the answer to "what if the inbox triaged itself?"** It runs
the review decision graph a senior reviewer carries in their head
([`docs/agent-graph.mmd`](docs/agent-graph.mmd)) as software: each contract is
classified, run through the policy gates, checked against the playbook, and then
**cleared**, **redlined to a known position**, or — when the rules can't settle
it — **paused and handed to a human**, who decides and hands it back. The
reviewer stops reading everything and reads only what's been flagged as worth
their time.

![The review console — queues, contract-type mix, and each incoming contract with its disposition and confidence](docs/screenshots/console-dashboard.png)

## How it works

The whole system is one **deterministic decision graph**. A contract enters as a
flat set of intake facts and flows through nodes that each read and write one
shared `TriageState`:

1. **Intake** — read the source PDF, fill in any blank intake fact from the
   document, and gate obvious non-starters (missing info, out of scope).
2. **Classify** — what *kind* of paper is this? NDA, order form, DPA, SOW,
   amendment; our paper or theirs; what data does it touch; what's it worth. An
   LLM reads the document and returns this as a structured classification; the
   graph around it stays deterministic control flow, so the *path* a contract
   takes is always a pure function of that classification.
3. **Policy-gate fan-out** — three validators (data protection, information
   security, insurance & liability) run in parallel and are gathered back. These
   fire on *facts about the deal*, not on redlines — a customer-paper DPA gates
   whether or not anyone asked to change a word.
4. **Negotiability + bounded redline loop** — for anything negotiable, each
   problem clause is mapped to a fixed **playbook position**: the standard ask,
   the fallback, and the line we refuse to cross. The loop is deliberately
   bounded so it always terminates.
5. **The human gate** — the one re-entrant interrupt. When the graph reaches
   something it shouldn't decide alone (an escalation, a business trade-off), it
   *pauses the run*, drops the contract into the reviewer's queue, and waits.
   The reviewer's decision — resolve, decline, escalate — resumes the exact same
   run from where it stopped.
6. **Approval / disposition** — the contract lands in a terminal state and the
   queue it belongs to: **approved**, **quarantined**, or still **pending**.

The reviewer sees all of this in a console: the queues, a detail view for each
contract — its classification, which gates fired, the proposed redlines with
their legal basis, the forward obligations — and the decision graph with *this*
contract's path lit up. When a run pauses at the human gate, the same view is
where the reviewer resolves, escalates, or declines it.

![A contract's detail view — the journey through the graph, the playbook mapping, and the human-gate escalation with resolve / escalate / reject controls](docs/screenshots/contract-detail.png)

The agent is **LLM-first**: the model makes every substantive judgment the graph
routes on — the classification, the policy gates, the redline→playbook mapping —
plus the plain-English explanation, all as structured calls grounded in the
corpus and the playbook. A chat client is therefore **required**: drop an OpenAI
/ Azure OpenAI key into `app/agent/.env` (without one the triage nodes raise
`LLMUnavailableError`). The `workflow.py` graph is pure control flow — routers,
fan-out/in, the human gate — so only the judgments *inside* the nodes are the
model's. The test suite swaps the model for a deterministic, corpus-grounded
double so the graph is exercised offline with no API calls.

## Approach (the tech stack)

The repo is four top-level folders, each a clean layer:

- **`host/`** — an **[Aspire](https://aspire.dev)** AppHost written in
  **TypeScript** that orchestrates everything and wires service discovery
  between the pieces. One command brings up the whole stack.
- **`app/`** — the application itself:
  - **`app/agent/`** — a **[Microsoft Agent Framework](https://github.com/microsoft/agent-framework)**
    workflow (the decision graph above) exposed two ways: a **FastAPI** REST
    surface the console consumes, and the **Agent Framework DevUI** for stepping
    through a run interactively — including driving the human-gate interrupt by
    hand. Python 3.12, managed with **[uv](https://docs.astral.sh/uv/)**.
  - **`app/frontend/`** — a **Next.js 14** review console: contract queues, a
    rich detail modal, and the live agent graph.
  - **`app/scripts/`** — a plain `dev.sh` launcher for running the stack without
    Aspire.
- **`data/`** — the domain corpus: the contract registers, the policy library,
  the reviewed `contracts/` back-catalogue, the `test/` intake fixtures, and the
  held-out `evals/` set.
- **`docs/`** — the decision framework, the requirements, the `agent-graph.mmd`
  diagram, the canonical `models.py` domain types, and the design audit.

Underneath, **SQLite** persists computed triage results (so the queues are warm
the instant the API answers), **MinIO** holds the intake PDFs and hands out
short-lived presigned URLs, and a self-hosted **[Langfuse](https://langfuse.com)**
stack captures the Agent Framework's **OpenTelemetry** traces — every triage run
shows up as a span tree with prompts, responses, token usage and latency.

```
                ┌─────────────────────── Aspire AppHost (TypeScript) ───────────────────────┐
                │                                                                            │
   browser ───► │   frontend (Next.js :3000) ──HTTP──► api (FastAPI :8000) ──► Agent          │
                │            │                                              Framework workflow │
                │            └──link──► devui (Agent Framework DevUI :8080) ──┘                │
                └────────────────────────────────────────────────────────────────────────────┘
```

The graph in `agent-graph.mmd` maps directly onto the code:

| agent-graph.mmd | code |
|---|---|
| shared `State` | `app/agent/contract_triage/state.py` — `TriageState` |
| nodes / routers / validators / HITL | `app/agent/contract_triage/executors.py` |
| graph wiring (switch-case, fan-out/in) | `app/agent/contract_triage/workflow.py` |
| classification + playbook judgment (the LLM brain) | `app/agent/contract_triage/agents.py` |
| the 10 inbox items | `app/agent/contract_triage/data.py` |

And the FastAPI surface the console speaks:

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/health` | liveness |
| `GET`  | `/api/contracts` | inbox + triage summaries |
| `GET`  | `/api/contracts/{id}` | full triage detail |
| `GET`  | `/api/contracts/{id}/document` | redirect to a presigned PDF URL |
| `POST` | `/api/contracts/{id}/triage` | run the workflow for one contract |
| `POST` | `/api/contracts/{id}/resolve` | resume a paused human-gate run (`{decision, note}`) |
| `GET`  | `/api/workflow/graph` | nodes/edges for the graph view |
| `GET`  | `/api/policies` | the policy register |

## How to run

**Prerequisites:** Python 3.10+ and [`uv`](https://docs.astral.sh/uv/) ·
Node ≥ 20.19 · the [Aspire CLI](https://aspire.dev) (`curl -sSL https://aspire.dev/install.sh | bash`,
only for the one-command path) · Docker (only for the Langfuse trace stack).

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

`aspire run` generates its TypeScript SDK, starts every resource, and opens the
Aspire dashboard. The frontend receives the backend URL via service discovery.

### Option B — plain scripts (no Aspire)

```bash
cd app/agent && uv venv --python 3.12 && source .venv/bin/activate \
  && uv pip install -e . --prerelease=allow && cd ../..
cd app/frontend && npm install && cd ../..
./app/scripts/dev.sh      # DevUI :8080 · API :8000 · frontend :3000
```

### Where things live

| Service | URL |
|---|---|
| Review console (frontend) | http://localhost:3000 |
| Triage API (FastAPI)      | http://localhost:8000/api/health |
| Agent Framework DevUI     | http://localhost:8080 |
| Langfuse (traces)         | http://localhost:3001 |

Langfuse signs in with **`admin@northgate.local` / `langfuse-admin`** — the
project and API keys are provisioned headlessly, so traces land in the
**Contract Triage** project with no setup. Because every triage decision is an
LLM call, each run's span tree includes the `chat` spans — prompts, responses,
token usage and latency — under the workflow span.

## Benchmarks — how we know it's grounded

There is no single accuracy number to wave around, because the interesting claim
isn't "the model is X% accurate" — it's "every decision the graph makes traces
back to something that actually happens in the corpus." Three things back that up:

- **The evidence base.** The decision framework
  ([`docs/decision-framework.md`](docs/decision-framework.md)) is derived from
  **79 processed contracts** with full edit logs. The edit distribution (34% /
  25% / 22% / 19% for 0 / 1 / 2 / 3–4 edits) and the playbook-citation frequency
  (50 citations across 39 contracts, dominated by a handful of sections —
  governing law, liability cap, payment terms, renewal) are what shape the
  branches. No branch exists that the corpus doesn't justify; citations run
  throughout.
- **A test suite that pins the graph.** **54 tests** across
  [`app/agent/tests/`](app/agent/tests/) exercise the workflow node-by-node.
  Every router branch is pinned at least once, and `test_routing.py` asserts the
  "ends *here*, not *there*" contrasts (fast-path vs. full review, gate
  short-circuits, the human-gate resume paths). To stay hermetic they swap the
  LLM brain for a deterministic, corpus-grounded double, so no live calls are
  made; the source PDF is still genuinely read off disk on every case, and the
  metadata steers the branch deterministically.
- **A held-out split for scoring.** [`data/evals/`](data/evals/) holds **20
  reviewed contracts** in two parallel copies — `without-edits/` (the contract as
  it arrived, the input) and `with-edits/` (the same contract after human review,
  the gold output). A triage run against the first is scored against the second.
  [`data/test/`](data/test/) is the **10-item live inbox** (`CR-2026-050`…`059`)
  with no gold output — the set the running app triages.

## Caveats

- **It's a demo, and the intelligence is the LLM.** The model makes every
  classification, gate and redline call, prompted against the corpus and the
  playbook — so it generalises beyond fixed rules, but a run now needs a
  reachable API and a key, and its judgments carry the usual model caveats
  (variance, the odd wrong call). The deterministic double lives only in the
  tests, for reproducibility, and is not the runtime source of truth.
- **The eval split is scaffolding, not an automated scoreboard.** The
  `without-edits` → `with-edits` gold split is in place, but there's no committed
  harness that runs the 20 and prints a score — that comparison is left as the
  next step.
- **The human loop is bounded on purpose.** To guarantee termination, a resumed
  human-gate run routes to `approval` rather than looping back to `classify` as
  the abstract diagram shows. And `loop_control`'s `maxed` branch can't be
  reached end-to-end under the deterministic test double, so it's pinned at the
  node level instead.
- **`app/agent/contract_triage/models.py` is a vendored copy** of
  `docs/models.py` so the agent stays a self-contained, deployable package —
  keep the two in sync if the domain types change.
- **Aspire's TypeScript AppHost is young and fast-moving.** If a builder method
  name differs in your installed version, `aspire run` regenerates the SDK, or
  fall back to Option B.
- **The Langfuse credentials are demo defaults** in
  [`host/apphost.mts`](host/apphost.mts), and `ENABLE_SENSITIVE_DATA=true`
  captures prompts and responses — dev only, never point it at anything real.

---

See [`app/agent/README.md`](app/agent/README.md),
[`app/frontend/README.md`](app/frontend/README.md), and
[`host/apphost.mts`](host/apphost.mts) for the layer-level detail.
