#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"
export ENVIRONMENT="test"

if [ $# -eq 1 ]; then
    SVC_DIR="$REPO_ROOT/services/$1"
    PY="$SVC_DIR/.venv/bin/python"
    [ -f "$PY" ] && "$PY" -m pytest "$SVC_DIR/tests" -v || python3 -m pytest "$SVC_DIR/tests" -v
elif [ "${1:-}" = "--infra" ]; then
    echo "Running infrastructure tests..."
    python3 -m pytest tests/ -v
else
    echo "Running all tests..."
    python3 -m pytest tests/ -v
    [ -d "$REPO_ROOT/services/ml-platform/tests" ] && \
        (echo "--- ml-platform tests ---" && \
         (PY="$REPO_ROOT/services/ml-platform/.venv/bin/python"; \
          [ -f "$PY" ] && "$PY" -m pytest "$REPO_ROOT/services/ml-platform/tests" -v || \
          python3 -m pytest "$REPO_ROOT/services/ml-platform/tests" -v))
fi
