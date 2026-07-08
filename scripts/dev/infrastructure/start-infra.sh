#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
echo "Starting infrastructure services..."
docker compose up -d
echo "Infrastructure started."
echo "  PostgreSQL: localhost:5432"
echo "  Kafka:      localhost:9092"
echo "  Elasticsearch: localhost:9200"
