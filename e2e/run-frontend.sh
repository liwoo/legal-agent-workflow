#!/usr/bin/env bash
# Run the Next.js review console, pointed at the local API + DevUI.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Next.js 14 needs Node >= 18.17; use nvm's Node 22 if the default is older.
if command -v node >/dev/null && [ "$(node -e 'process.stdout.write(process.versions.node.split(".")[0])')" -lt 20 ]; then
  export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
fi
cd "$HERE/../app/frontend"
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
export NEXT_PUBLIC_DEVUI_URL=http://localhost:8080
export PORT=3000
exec npm run dev
