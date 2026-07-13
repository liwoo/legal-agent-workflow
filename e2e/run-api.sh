#!/usr/bin/env bash
# Run the FastAPI triage backend against the compose stack, with OTEL → Langfuse.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/stack.env"
cd "$HERE/../app/agent"
source .venv/bin/activate
exec python -m contract_triage
