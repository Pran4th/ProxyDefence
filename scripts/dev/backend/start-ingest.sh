#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
. "$REPO_ROOT/scripts/dev/common/load-env.sh" "$REPO_ROOT"

cd "$REPO_ROOT/services/ingest-service"
[ ! -d .venv ] && echo "ERROR: .venv not found. Run scripts/dev/setup/setup.sh first." && exit 1
source .venv/bin/activate
export PYTHONPATH="$REPO_ROOT"
export ENVIRONMENT="development"
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
