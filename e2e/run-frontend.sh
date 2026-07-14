#!/usr/bin/env bash
# Run the Next.js review console, pointed at the local API + DevUI.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Pretty, color-coded failures (only when stderr is a terminal).
if [ -t 2 ]; then R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; D=$'\033[2m'; X=$'\033[0m'; else R=; Y=; B=; D=; X=; fi
die() { printf '\n%s%s✗ %s%s\n' "$B" "$R" "$1" "$X" >&2; shift; for line in "$@"; do printf '%s  %s%s\n' "$D" "$line" "$X" >&2; done; printf '\n' >&2; exit 1; }

# The console (Next.js 14) requires Node >= 20 (see app/frontend/package.json).
# Fail loudly rather than limp along on an unsupported runtime.
if ! command -v node >/dev/null 2>&1; then
  die "node not found." "Install Node >= 20 — https://nodejs.org"
fi
if ! node -e 'process.exit(+process.versions.node.split(".")[0] >= 20 ? 0 : 1)'; then
  die "Node $(node -v) is too old — the console needs Node >= 20." \
      "Upgrade Node and retry, e.g.:  ${Y}nvm install 20 && nvm use 20${X}${D}"
fi

cd "$HERE/../app/frontend"
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
export NEXT_PUBLIC_DEVUI_URL=http://localhost:8080
export PORT=3000
exec npm run dev
