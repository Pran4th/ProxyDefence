#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

. "$REPO_ROOT/scripts/dev/common/load-env.sh" "$REPO_ROOT"

launch_consumer() {
    local name=$1 svc_dir=$2 script=$3
    local python="$REPO_ROOT/$svc_dir/.venv/bin/python"
    if [ ! -f "$python" ]; then
        echo "WARNING: $name skipped (.venv not found)"
        return
    fi
    echo "Starting $name..."
    cd "$REPO_ROOT/$svc_dir"
    PYTHONPATH="$REPO_ROOT" ENVIRONMENT="development" \
        nohup "$python" "$script" > "/tmp/$name.log" 2>&1 &
    echo "  PID $!"
}

launch_consumer "ml-platform-consumer" "services/ml-platform"       "consumer/article_enrichment.py"
launch_consumer "embedding-consumer"   "services/embedding-service" "consumer.py"
launch_consumer "db-consumer"          "services/database-service"  "consumer.py"

echo ""
echo "Consumers running in background. Check /tmp/*.log for output."
echo "Stop with: kill <PID>"
