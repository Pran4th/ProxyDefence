#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "=== Development Environment Reset ==="
echo "This will remove all .venv directories."
read -p "Are you sure? (y/N) " confirm
[ "$confirm" != "y" ] && echo "Cancelled." && exit 0

echo "Stopping infrastructure..."
docker compose down 2>/dev/null

echo "Cleaning caches..."
bash "$REPO_ROOT/scripts/maintenance/clean.sh"

echo "Removing .venv directories..."
find "$REPO_ROOT" -type d -name .venv -exec rm -rf {} + 2>/dev/null

echo "Reset complete."
echo "Run scripts/dev/setup/setup.sh to recreate."
