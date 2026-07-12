#!/usr/bin/env bash
# Fallback launcher — runs the whole stack WITHOUT Aspire (useful if the Aspire
# TypeScript AppHost SDK isn't available on your machine). Starts:
#   DevUI    :8080   FastAPI :8000   Next.js :3000
# Requires: Python venv in ./agent/.venv and `npm install` done in ./frontend.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "▶ starting DevUI (:8080), API (:8000), frontend (:3000) — Ctrl-C to stop"

( cd "$ROOT/agent" && . .venv/bin/activate && PORT=8000 python -m contract_triage ) &
API_PID=$!
( cd "$ROOT/agent" && . .venv/bin/activate && DEVUI_PORT=8080 python -m contract_triage.devui_app ) &
DEVUI_PID=$!
( cd "$ROOT/frontend" && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 NEXT_PUBLIC_DEVUI_URL=http://localhost:8080 npm run dev ) &
FE_PID=$!

trap 'kill $API_PID $DEVUI_PID $FE_PID 2>/dev/null || true' EXIT INT TERM
wait
