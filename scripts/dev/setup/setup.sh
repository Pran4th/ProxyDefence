#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "=== ProxyDefence Development Setup ==="

# --- Verify Python ---
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi
PY_VER=$(python3 --version 2>&1)
echo "Python: $PY_VER"
MAJOR=$(echo "$PY_VER" | cut -d. -f1 | grep -oP '\d+')
MINOR=$(echo "$PY_VER" | cut -d. -f2 | grep -oP '\d+')
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]; }; then
    echo "ERROR: Python 3.11+ required"
    exit 1
fi

# --- Verify Docker ---
if ! docker info &>/dev/null; then
    echo "WARNING: Docker not detected"
fi

# --- Verify .env ---
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo ".env: created from .env.example"
        echo "  >> Edit .env with your credentials <<"
    else
        echo "WARNING: No .env or .env.example found"
    fi
else
    echo ".env: found"
fi

SERVICES=(
    "ingest-service:services/ingest-service:requirements.txt"
    "ml-service:services/ml-service:requirements.txt"
    "embedding-service:services/embedding-service:requirements.txt"
    "database-service:services/database-service:requirements.txt"
    "energy-service:services/energy-service:requirements.txt"
    "ml-platform:services/ml-platform:requirements.txt"
    "modular-api:services/modular-api:requirements.txt"
)

ALL_OK=true
for entry in "${SERVICES[@]}"; do
    IFS=':' read -r NAME DIR REQ <<< "$entry"
    SVC_DIR="$REPO_ROOT/$DIR"
    VENV_DIR="$SVC_DIR/.venv"
    REQ_FILE="$SVC_DIR/$REQ"

    echo ""
    echo "--- $NAME ---"

    if [ ! -f "$REQ_FILE" ]; then
        echo "  SKIP: requirements.txt not found"
        continue
    fi

    if [ -d "$VENV_DIR" ] && [ "${1:-}" != "--force" ]; then
        echo "  .venv: exists"
    else
        if [ -d "$VENV_DIR" ]; then rm -rf "$VENV_DIR"; fi
        echo "  Creating .venv..."
        python3 -m venv "$VENV_DIR"
        echo "  .venv: created"
    fi

    PIP="$VENV_DIR/bin/pip"
    if [ ! -f "$PIP" ]; then
        echo "  FAILED: pip not found"
        ALL_OK=false
        continue
    fi

    echo "  Installing dependencies..."
    "$PIP" install --quiet --upgrade pip
    "$PIP" install --quiet -r "$REQ_FILE" && echo "  Dependencies: installed" || { echo "  FAILED"; ALL_OK=false; }
done

# --- spaCy model ---
echo ""
echo "--- spaCy Model (ml-service) ---"
ML_PYTHON="$REPO_ROOT/services/ml-service/.venv/bin/python"
if [ -f "$ML_PYTHON" ]; then
    if "$ML_PYTHON" -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
        echo "  spaCy model: found"
    else
        echo "  Downloading en_core_web_sm..."
        "$REPO_ROOT/services/ml-service/.venv/bin/pip" install --quiet \
            "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl" \
            && echo "  spaCy model: downloaded" || echo "  WARNING: download failed"
    fi
fi

echo ""
echo "=== Setup Complete ==="
$ALL_OK && echo "All services configured successfully." || echo "Some services had errors."
echo ""
echo "Next steps:"
echo "  1. Edit .env with your credentials"
echo "  2. Run: scripts/dev/infrastructure/start-infra.sh"
echo "  3. Run: scripts/dev/backend/start-all.sh"
echo "  4. Run: scripts/dev/frontend/start-frontend.sh"
