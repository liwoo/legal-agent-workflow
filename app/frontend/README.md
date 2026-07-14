# Contract Triage — Review Console (Next.js)

A neutral-themed review console for the Northgate contract-triage workflow.
Structurally modeled on the [triaj](https://github.com/liwoo/triaj) triage app
(queue + detail-modal + workflow-graph), with the government theming stripped
out for a plain commercial-SaaS look.

- **Next.js 14** (App Router) · **TypeScript** · **Tailwind CSS** · **shadcn/ui**
- **@tanstack/react-table** for the queues · **@xyflow/react** for the agent graph
- **next-themes** light/dark · offline-first (falls back to local fixtures when
  the backend is unreachable)

Routing lives in `app/`; components, screens, store and libs live in `src/`
(`experimental.externalDir` enabled in `next.config.mjs`).

## Screens

- **Dashboard** — KPI cards, contract-mix bars, recent arrivals, the agent graph.
- **Pending / Approved / Quarantined** — three TanStack-table queues; a row opens
  the detail modal.
- **Contract detail modal** (the centerpiece) — AI score + explanation, policy-gate
  table, redlines mapped to the playbook, forward obligations, timeline, and the
  agent graph with this contract's path highlighted. Approve / Reject / Escalate
  call the backend `/resolve` (which resumes the human-gate interrupt).
- **Policies** and **Settings** (backend connectivity, theme, about).

## Run

Requires **Node ≥ 20**.

```bash
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE_URL` to the FastAPI backend (see `../agent`). With no
backend reachable the app still renders from the fixtures in `src/data/`.

Normally you run the frontend together with the backend + DevUI via `make up`
from the repo root, which sets `NEXT_PUBLIC_API_BASE_URL` and
`NEXT_PUBLIC_DEVUI_URL` automatically.

## Environment

| Var | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Triage backend base URL (default `http://localhost:8000`) |
| `NEXT_PUBLIC_DEVUI_URL` | Agent Framework DevUI URL (optional, for the link-out) |
