#!/usr/bin/env bash
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "Cleaning cache files..."
find "$REPO_ROOT" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find "$REPO_ROOT" -type f -name "*.pyc" -delete 2>/dev/null
find "$REPO_ROOT" -type f -name "*.pyo" -delete 2>/dev/null
find "$REPO_ROOT" -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null
echo "Cache files removed."
