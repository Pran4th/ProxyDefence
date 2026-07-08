# Energy Intelligence Runbook

## Prerequisites

- Windows PowerShell
- Python 3.10
- Node.js and npm
- Docker Desktop
- PostgreSQL, Kafka, Elasticsearch from local Docker compose
- Service virtual environments created by `scripts/dev/setup/setup.ps1`

## Environment Variables

Required local values are loaded from `.env`:

```text
POSTGRES_HOST=127.0.0.1
POSTGRES_DB=defenseintel
POSTGRES_USER=admin
POSTGRES_PASSWORD=change-me
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092
ELASTICSEARCH_HOST=127.0.0.1
EMBEDDING_SERVICE_URL=http://127.0.0.1:8005
ENERGY_SERVICE_URL=http://127.0.0.1:8006
ENERGY_LOAD_SEED=1
VITE_API_URL=http://localhost:8000
```

## Database Setup

Fresh local database:

```powershell
scripts\reset-db.ps1 -All
```

Energy-only reset:

```powershell
scripts\reset-db.ps1 -Energy
```

Manual bridge-table check:

```powershell
docker exec postgres-db psql -U admin -d defenseintel -c "SELECT to_regclass('public.energy_entity_mappings'), to_regclass('public.article_energy_enrichments');"
```

## Docker Setup

Start infrastructure:

```powershell
scripts\dev\infrastructure\start-infra.ps1
```

Stop infrastructure:

```powershell
scripts\dev\infrastructure\stop-infra.ps1
```

Check containers:

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## Migration Commands

Alembic migrations live in `backend/shared/migrations/versions`.

The current local startup path relies on idempotent SQL bootstraps. Bridge tables are also bootstrapped by `services/database-service/services/energy_enrichment.py` so existing local databases do not fail when Kafka messages arrive.

Expected bridge tables:

```sql
SELECT to_regclass('public.energy_entity_mappings');
SELECT to_regclass('public.article_energy_enrichments');
```

## Startup Commands

Full local stack when Docker infra is not already running:

```powershell
scripts\dev\start-local.ps1 -Force
```

When Docker infra is already running:

```powershell
scripts\dev\start-local.ps1 -Force -SkipInfra
```

Individual Energy service:

```powershell
scripts\dev\backend\start-energy.ps1
```

Consumers:

```powershell
scripts\dev\backend\start-consumers.ps1
```

## Shutdown Commands

```powershell
scripts\dev\stop-local.ps1
```

Stop infrastructure too:

```powershell
scripts\dev\infrastructure\stop-infra.ps1
```

## Health Check Commands

```powershell
Invoke-WebRequest http://localhost:8000/ -UseBasicParsing
Invoke-WebRequest http://localhost:8001/health -UseBasicParsing
Invoke-WebRequest http://localhost:8002/health -UseBasicParsing
Invoke-WebRequest http://localhost:8003/health -UseBasicParsing
Invoke-WebRequest http://localhost:8005/health -UseBasicParsing
Invoke-WebRequest http://localhost:8006/health -UseBasicParsing
Invoke-WebRequest http://localhost:8007/health -UseBasicParsing
Invoke-WebRequest http://localhost:8080 -UseBasicParsing
```

Expected: HTTP `200` from each service.

## Service URLs

| Service | URL |
| --- | --- |
| modular-api | `http://localhost:8000` |
| ingest-service | `http://localhost:8001` |
| ml-service | `http://localhost:8002` |
| database-service | `http://localhost:8003` |
| embedding-service | `http://localhost:8005` |
| energy-service | `http://localhost:8006` |
| ml-platform | `http://localhost:8007` |
| frontend | `http://localhost:8080` |
| Kafka | `127.0.0.1:9092` |
| PostgreSQL | `127.0.0.1:5432` |
| Elasticsearch | `http://localhost:9200` |

## Kafka Topics

| Topic | Producer | Consumer |
| --- | --- | --- |
| `raw_articles` | ingest-service | ml-service consumer |
| `processed_articles` | ml-service | database-service consumer |

## Useful Curl Commands

Energy health:

```bash
curl http://localhost:8006/health
```

List locations:

```bash
curl "http://localhost:8006/api/v1/energy/locations?limit=5"
```

List ports:

```bash
curl "http://localhost:8006/api/v1/energy/ports?limit=5"
```

Check article bridge rows:

```bash
docker exec postgres-db psql -U admin -d defenseintel -c "SELECT article_id, context FROM article_energy_enrichments ORDER BY updated_at DESC LIMIT 5;"
```

Copilot query requires authentication:

```bash
curl -X POST http://localhost:8000/copilot/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is the energy impact of Russia pipeline disruptions?\"}"
```

## Sample API Requests

Create an Energy event:

```bash
curl -X POST http://localhost:8006/api/v1/energy/events \
  -H "Content-Type: application/json" \
  -d "{\"entity_type\":\"pipeline\",\"entity_id\":1,\"event_type\":\"maintenance\",\"severity\":\"medium\",\"description\":\"Scheduled outage\"}"
```

Create a relationship:

```bash
curl -X POST http://localhost:8006/api/v1/energy/relationships \
  -H "Content-Type: application/json" \
  -d "{\"source_entity_type\":\"pipeline\",\"source_entity_id\":1,\"target_entity_type\":\"location\",\"target_entity_id\":1,\"relationship_type\":\"located_in\"}"
```

## Sample API Responses

Energy catalog response:

```json
{
  "items": [
    {
      "id": 14,
      "name": "Angola",
      "slug": "angola",
      "location_type": "country",
      "geojson": {},
      "metadata": {}
    }
  ],
  "total": 31,
  "limit": 1,
  "offset": 0
}
```

Article energy context:

```json
{
  "countries_mentioned": ["Russia"],
  "infrastructure_mentioned": ["Russia to Europe (Pipeline)"],
  "organizations_mentioned": [],
  "commodities_mentioned": [],
  "infrastructure_event_count": 0,
  "total_linked_assets": 2
}
```

## Verify Energy Integration

1. Start local stack.
2. Confirm `energy-service` health is `200`.
3. Confirm seed data exists:

```powershell
docker exec postgres-db psql -U admin -d defenseintel -c "SELECT count(*) FROM energy.locations; SELECT count(*) FROM energy.ports;"
```

4. Confirm bridge tables exist:

```powershell
docker exec postgres-db psql -U admin -d defenseintel -c "SELECT to_regclass('public.energy_entity_mappings'), to_regclass('public.article_energy_enrichments');"
```

5. Confirm database consumer is running and has no new `consumer_handler_failed` errors.
6. Confirm enrichment rows:

```powershell
docker exec postgres-db psql -U admin -d defenseintel -c "SELECT count(*) FROM energy_entity_mappings; SELECT count(*) FROM article_energy_enrichments;"
```

## Debug Failures

Read logs:

```powershell
scripts\dev\logs.ps1 -Service energy
scripts\dev\logs.ps1 -Service db-consumer
scripts\dev\logs.ps1 -Service modular-api
```

Check process ports:

```powershell
Get-NetTCPConnection -LocalPort 8000,8003,8006,8007,8080 -ErrorAction SilentlyContinue
```

Check DB tables:

```powershell
docker exec postgres-db psql -U admin -d defenseintel -c "\dt public.*energy*"
docker exec postgres-db psql -U admin -d defenseintel -c "\dt energy.*"
```

## Common Issues

Bridge tables missing:

- Symptom: DB consumer logs `relation "energy_entity_mappings" does not exist`.
- Fix: restart the DB consumer with current code or run one enrichment; `ensure_energy_bridge_schema()` creates the tables idempotently.

Plural vs singular asset types:

- API routes use plural tables such as `ports`.
- `energy.asset_type` uses singular values such as `port`.
- The routers normalize this internally.

JSONB returned as strings:

- Restart `energy-service` so the API response normalizer is active.

Frontend not on port `5173`:

- In this workspace Vite serves on `http://localhost:8080`.

Python tests fail with `pytest_asyncio` missing:

- Install test requirements or run through the project-managed test environment.

## Troubleshooting Guide

If startup fails on occupied infra ports, use:

```powershell
scripts\dev\start-local.ps1 -Force -SkipInfra
```

If a service is stale after code changes, restart only that service:

```powershell
scripts\dev\backend\start-energy.ps1
scripts\dev\backend\start-database.ps1
```

If consumers are duplicated, stop local processes and start again:

```powershell
scripts\dev\stop-local.ps1
scripts\dev\start-local.ps1 -Force -SkipInfra
```

## Expected Outputs

Healthy Energy Service:

```json
{"status":"healthy","service":"energy-service","version":"1.0.0"}
```

Enrichment success log:

```text
energy_enrichment_complete article_id=<id> matched_assets=<n>
```

Bridge count query:

```text
mappings: greater than or equal to 0
enrichments: greater than or equal to 0
```
