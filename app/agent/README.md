# Contract-Triage Agent (Microsoft Agent Framework)

A stateful [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
**workflow** that implements the abstract contract-review decision graph in
[`../../docs/agent-graph.mmd`](../../docs/agent-graph.mmd). Every node reads/writes one shared
`TriageState`; routers branch on it; three policy validators fan out and are
gathered; a single re-entrant **human gate** interrupts the run for a reviewer
decision and resumes on their response.

It ships two surfaces:

- **FastAPI** (`contract_triage.api`) — the REST the Next.js console consumes.
- **DevUI** (`contract_triage.devui_app`) — the Agent Framework developer UI to
  run, inspect and step through the workflow (and drive the human-gate
  interrupt) at `http://localhost:8080`.

The agent is **fully LLM-first**: the model (`agents.py`) makes every
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

```
contract_triage/
  models.py       # vendored copy of ../../docs/models.py — the Pydantic domain types
  state.py        # TriageState (the shared message) + request/result envelopes
  data.py         # the 10 inbox items + inherited prior-contract flags
  agents.py       # the LLM brain: classification, gates, redlines, explanation (+ DevUI agents)
  config.py       # loads .env so OPENAI_API_KEY is picked up standalone or under `make up`
  executors.py    # one Executor per node in agent-graph.mmd
  workflow.py     # WorkflowBuilder wiring: switch-case routers, fan-out/in, HITL
  graph_spec.py   # static nodes/edges for GET /api/workflow/graph
  service.py      # runs the workflow, serialises to the API contract, HITL registry
  api.py          # FastAPI app
  devui_app.py    # DevUI serve() entrypoint
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

- `models.py` is a copy of `../../docs/models.py` so the agent is a
  self-contained, deployable package; keep them in sync if the domain types change.
- The human gate is a genuine Agent Framework `request_info` interrupt. In the
  app flow a paused run lands the contract in the reviewer's queue; `/resolve`
  resumes it (resolved → sign, declined → DECLINED, escalated → ESCALATED). To
  keep the loop bounded, resume routes to `approval` rather than back to
  `classify` as the abstract diagram shows.
