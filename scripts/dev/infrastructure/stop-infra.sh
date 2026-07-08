#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
echo "Stopping infrastructure services..."
docker compose down
echo "Infrastructure stopped."
