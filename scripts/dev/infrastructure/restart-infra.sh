#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
echo "Restarting infrastructure..."
docker compose down
docker compose up -d
echo "Infrastructure restarted."
