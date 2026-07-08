#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT/services/frontend"
[ ! -d node_modules ] && npm install
echo "Starting frontend (Vite dev server)..."
npm run dev
