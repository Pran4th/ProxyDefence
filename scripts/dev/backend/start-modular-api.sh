#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
. "$REPO_ROOT/scripts/dev/common/load-env.sh" "$REPO_ROOT"

SVC_DIR="$REPO_ROOT/services/modular-api"
[ ! -d "$SVC_DIR/.venv" ] && echo "ERROR: .venv not found. Run scripts/dev/setup/setup.sh first." && exit 1
cd "$REPO_ROOT"
source "$SVC_DIR/.venv/bin/activate"
export PYTHONPATH="$REPO_ROOT"
export ENVIRONMENT="development"
uvicorn backend.api_service.main:app --host 0.0.0.0 --port 8000 --reload
