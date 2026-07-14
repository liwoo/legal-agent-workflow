# How to read this codebase

A follow-the-code walkthrough for someone who has **never used the Microsoft Agent
Framework (MAF)**. We start at the line that runs first and trace the program the way
it actually assembles and executes — every MAF concept is explained the moment the code
reaches it, with a link to the official docs. You should be able to read this top to
bottom, jumping to the named file at each step, and come out understanding the whole thing.

The `io/` layer (FastAPI, SQLite, MinIO, PDF, OpenTelemetry) is ordinary backend code —
we point at it but don't stop.

> The one sentence to hold onto: **this app is a *graph of small functions* (called
> executors) that pass a single object (`TriageState`) from one to the next; MAF is the
> library that wires that graph and runs it.** Everything below is just following that
> object through the graph.

---

## Step 0 — where execution begins: `__main__.py`

Running `python -m contract_triage` calls one function, which hands off to a web server:

```python
# __main__.py
uvicorn.run("contract_triage.io.api:app", host=host, port=port)
```

So the real starting point is the FastAPI app in **`io/api.py`**. (The other entry point,
`devui_app.py`, boots MAF's developer UI instead — same workflow, different front door.
We come back to it at the end.)

## Step 1 — the web layer builds the service: `io/api.py`

`io/api.py` is a thin REST surface. It does two things worth noting and nothing clever:

```python
service = TriageService()                     # ← all the real work lives here

@app.post("/api/contracts/{item_id}/triage")
async def triage_contract(item_id: str):
    return await service.triage(item_id)       # run the agent on one contract
```

Every endpoint just calls a method on `TriageService`. Reading the API is optional; the
interesting file is the service. **Skim the rest of `io/` — it's plumbing.**

## Step 2 — the service runs the workflow: `service.py`

This is where the app meets MAF. When a contract is triaged, the service **builds the
graph and runs it**:

```python
# service.py  (inside triage_events)
wf = build_workflow()                          # assemble the graph  → Step 3
stream = wf.run(_request_for(item), stream=True)   # run it, streaming events
async for event in stream:
    ...                                        # narrate each node as it fires (Step 6)
result = await stream.get_final_response()
```

Two ideas here, both pure MAF:

- **`wf.run(input, stream=True)`** executes the graph and yields *lifecycle events* as
  each node starts/finishes — that's how the console shows a live, node-by-node view.
- The input is a `TriageRequest` (the contract's intake fields). MAF feeds it to the
  graph's **start node**, and from then on the nodes pass a `TriageState` around.

Hold the rest of `service.py` (streaming details, human-gate resume) for Step 6. First,
what did `build_workflow()` actually assemble?

## Step 3 — compiling the graph: `edges/workflow.py`  ← the most important file

This single function *is* the program's structure. Read it slowly; everything else is the
bodies of the nodes it names. It has three phases.

**3a. Create the nodes.** Each node is an *executor* — an object that will process one
message. They're defined in `executors/` (Step 4); here we just instantiate them:

```python
ingest   = X.Ingest(id="ingest")
classify = X.Classify(id="classify")
...
```

**3b. Open the builder.** `WorkflowBuilder` is MAF's graph assembler
([docs](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows)):

```python
b = WorkflowBuilder(
    start_executor=ingest,        # the first node to run
    max_iterations=50,            # safety cap on execution rounds (see below)
    output_from=[side_effects, declined, escalated],  # nodes whose output ends the run
)
```

**3c. Add the edges** — the connections between nodes. This is the whole decision graph,
and MAF gives you exactly the edge types you see used here
([Edges docs](https://learn.microsoft.com/en-us/agent-framework/workflows/edges)):

- **Plain edge** — always goes to the next node:
  ```python
  b.add_edge(ingest, classify)          # after ingest, always classify
  ```
- **Switch-case edge group** — the branch points ("diamonds"). The source node sets a
  value on the state and each `Case` inspects it; the first match wins, else `Default`:
  ```python
  b.add_switch_case_edge_group(intake_gate, [
      Case(lambda s: s.route in ("more_info", "blocked"), human_gate),
      Default(triage),
  ])
  ```
  So a *router node* is just a node whose job is to set `state.route`; the edge does the
  branching. (Look for `state.route = ...` in the executors — that's the node "voting"
  for which `Case` fires.)
- **Fan-out then fan-in** — run several nodes in parallel, then rejoin:
  ```python
  b.add_fan_out_edges(fanout, [dpa, statutory, finance])   # all three run concurrently
  b.add_fan_in_edges([dpa, statutory, finance], gather)    # gather waits for all three
  ```

Finally `return b.build()` produces the runnable `Workflow` the service got in Step 2.

> **Why `max_iterations`?** MAF executes in rounds ("supersteps"): each round delivers the
> pending messages, runs the targeted nodes **concurrently**, waits for all of them, then
> starts the next round. A cap keeps a loop (our redline loop) from spinning forever. See
> the [execution model](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows).

Now you know the shape. `edges/graph_spec.py` next to it is just a static copy of these
nodes/edges as plain data, so the frontend can draw the same picture — ignore it for now.

## Step 4 — what a node actually is: `executors/`

Every node named in Step 3 is an **Executor**: a class with one `@handler` method that
receives a message, does its work, and passes a message on
([Executors docs](https://learn.microsoft.com/en-us/agent-framework/workflows/executors)).
The files map to the stages of the graph (`intake.py`, `gates.py`, `negotiability.py`,
`redline.py`, `approval.py`, `human_gate.py`; `finalize.py` holds shared helpers). Here is
the whole pattern, from the start node:

```python
# executors/intake.py
class Ingest(Executor):
    @handler
    async def run(self, req: TriageRequest, ctx: WorkflowContext[TriageState]) -> None:
        ...                                   # read the PDF, build the state
        state = TriageState(item=item)
        await ctx.send_message(state)         # hand the message to the next node(s)
```

Three things to internalise, because *every* node is a variation of this:

1. **The `@handler` receives the message and the `ctx`.** `ctx` (a `WorkflowContext`) is
   how a node talks back to the framework. `ctx.send_message(x)` = "pass `x` along my
   outgoing edges." Whichever edge fires (plain / switch-case / fan-out) was decided in
   Step 3.
2. **`Ingest` turns a `TriageRequest` into a `TriageState`.** That's the one place the
   message type changes; from here on the message is always the same evolving `TriageState`.
3. **The `ctx: WorkflowContext[...]` annotation declares what the node may emit.** One type
   param = "I send this message type"; two = "I may also *finish* the run with this output
   type." So:
   - `WorkflowContext[TriageState]` — a normal node, passes the state on.
   - `WorkflowContext[Never, TriageState]` — a **terminal** node: it ends the run with
     `ctx.yield_output(state)` instead of `send_message`.

   *(This is also why the executor files don't use `from __future__ import annotations` —
   MAF reads these annotations at import time and needs the real types, not strings.)*

Now walk a few representative nodes and you've seen them all:

- **A router** (`executors/intake.py`, `gates.py`, …): sets `state.route` and forwards.
  The switch-case edge from Step 3 does the branching.
  ```python
  class IntakeGate(Executor):
      @handler
      async def run(self, state, ctx):
          state.route = "more_info" if ... else "ok"
          await ctx.send_message(state)
  ```
- **The parallel validators** (`executors/gates.py`): because MAF runs the three
  concurrently, each works on its **own deep copy** so they don't clobber each other, then
  `Gather` (the fan-in node) receives them as a **list** and merges:
  ```python
  s = state.model_copy(deep=True)          # each validator gets its own copy
  ...
  class Gather(Executor):
      @handler
      async def run(self, items: list[TriageState], ctx):   # ← a list, from the fan-in
          base = items[0]
          base.gate_checks = [g for it in items for g in it.gate_checks]
          await ctx.send_message(base)
  ```
- **A terminal node** (`executors/approval.py`): ends the run.
  ```python
  class SideEffects(Executor):
      @handler
      async def run(self, state, ctx: WorkflowContext[Never, TriageState]):
          await finalize(state)             # score + explain + persist (Step 5 / io)
          await ctx.yield_output(state)     # ← the workflow's result
  ```

## Step 4½ — the one genuinely special node: the human gate

`executors/human_gate.py` is the reason this is more than a state machine. MAF lets a node
**pause the entire workflow to ask an outside party** (a human) and resume later
([Human-in-the-loop docs](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)):

```python
class HumanGate(Executor):
    @handler
    async def run(self, state, ctx):
        ...
        # pauses the run until a HumanDecision is supplied:
        await ctx.request_info(request_data=state, response_type=HumanDecision)

    @response_handler
    async def resume(self, original, decision: HumanDecision, ctx):
        state.route = "resolved" | "declined" | "escalated"   # route the continuation
        await ctx.send_message(state)
```

Back in `service.py` you can now read the other half of the mechanism: after a run, the
service checks whether the workflow paused, remembers it, and resumes it when the reviewer
answers:

```python
if result.get_request_info_events():          # did it pause at the gate?
    ... remember request_id ...
# later, when the reviewer decides:
await pend.workflow.run(responses={pend.request_id: HumanDecision(decision=..., note=...)})
```

That's the full request → pause → resume loop the console's reviewer queue is built on.

## Step 5 — the brain (you are here): `agents/`

The graph is pure control flow; the *judgments* it routes on come from an LLM, and they
all live in this package. The decision nodes call four functions in
[`agents/__init__.py`](__init__.py) — `classify_llm`, `gate_llm`, `redlines_llm`,
`explain`. Each is one structured model call
([Agents in workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/agents-in-workflows)):

```python
agent = client.as_agent(instructions=CLASSIFIER_INSTRUCTIONS)   # a prompt-bound agent
resp  = await agent.run(prompt, options={"response_format": ClassificationLLM})
#                                          ↑ the model must return JSON matching this schema
```

So `Classify` (Step 4) calls `agents.classify_llm(...)`, which asks the model to fill a
Pydantic schema, and the node writes the result onto the state. Same shape for the policy
gates and the redline mapping.

The prompts themselves are **one file each** under [`prompts/`](prompts/) — edit the
wording there without touching the wiring. `build_agents()` also exposes these three
agents standalone so you can poke them in the DevUI.

## Step 6 — the vocabulary everything shares: `models/`

You've seen `TriageState` on every hop; this is where it's defined.

- [`models/state.py`](../models/state.py) — **`TriageState`** (the message that flows
  through the graph, accumulating classification → gate checks → redlines → outcome),
  plus `TriageRequest` (the input) and `Interrupt` (the pause marker). Read the fields and
  re-skim Step 4 — you'll now recognise what each node writes.
- [`models/domain.py`](../models/domain.py) — the enums/records those fields use. Plain
  Pydantic; consult as needed.

## Recap — one contract's journey

```
TriageRequest
   │  io/api.py → service.py: wf = build_workflow(); wf.run(request, stream=True)
   ▼
ingest → classify → intake_gate ─(router)─┐
   │  (executors/, each an Executor.@handler passing a TriageState)
   ▼                                       ├─► human_gate ──(request_info: PAUSE)──► reviewer
triage ─(fast path?)─► cheap_guard         │        └─(response_handler: RESUME)─► approval / declined / escalated
   │                                       │
   └─► fanout ═╦═► dpa       ═╗            (switch-case edges branch on state.route;
              ╠═► statutory  ═╬═► gather    fan-out runs the 3 validators concurrently,
              ╚═► finance    ═╝    │        fan-in gathers them)
                                   ▼
                        negotiability → redline loop → approval → execute → side_effects
                                                                               │ ctx.yield_output
                                                                               ▼
                                                                          TriageState (the result)
```

Read in this order and it's linear: **`io/api.py` → `service.py` → `edges/workflow.py`
(the map) → `executors/` (the nodes) → `agents/` (the judgments) → `models/` (the data).**

## Appendix — the MAF vocabulary in one place

| Code you'll see | Plain meaning | Docs |
|---|---|---|
| `class Foo(Executor)` + `@handler async def run(self, msg, ctx)` | a graph node: receives a message, does work | [Executors](https://learn.microsoft.com/en-us/agent-framework/workflows/executors) |
| `ctx.send_message(state)` | pass the message along my outgoing edge(s) | [Executors](https://learn.microsoft.com/en-us/agent-framework/workflows/executors) |
| `ctx.yield_output(state)` | finish the run with this result | [Executors](https://learn.microsoft.com/en-us/agent-framework/workflows/executors) |
| `WorkflowContext[T]` / `[T, U]` / `[Never, U]` | what a node may emit: send `T` / send `T` or output `U` / terminal-only | [Executors](https://learn.microsoft.com/en-us/agent-framework/workflows/executors) |
| `WorkflowBuilder(start_executor=…, output_from=…)` … `.build()` | assemble the graph | [Builder & execution](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows) |
| `add_edge` / `add_switch_case_edge_group(Case/Default)` / `add_fan_out_edges` / `add_fan_in_edges` | plain / branch / split / join edges | [Edges](https://learn.microsoft.com/en-us/agent-framework/workflows/edges) |
| `ctx.request_info(...)` + `@response_handler` | pause for a human, resume on their answer | [Human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) |
| `client.as_agent(instructions=…).run(…, options={"response_format": Schema})` | an LLM call that returns a typed object | [Agents in workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/agents-in-workflows) |
| `wf.run(x, stream=True)` · `get_final_response()` · `get_request_info_events()` · `get_outputs()` | run a workflow and observe/resume it | [Builder & execution](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows) |
| `serve(entities=[workflow, *agents])` | boot the MAF DevUI (`devui_app.py`) | [Overview](https://learn.microsoft.com/en-us/agent-framework/overview/) |

New to MAF entirely? The [overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
and [workflows landing page](https://learn.microsoft.com/en-us/agent-framework/workflows/)
are the two pages to read alongside this tour. The abstract decision graph this whole
program implements is [`../../../../docs/agent-graph.mmd`](../../../../docs/agent-graph.mmd).
