# Architecture

## Layer Separation

```
Research               Development              Production
──────────────────────────────────────────────────────────
Jupyter/Notebooks      VS Code                  Docker Compose
       ↓                    ↓                        ↓
  research/            Python .venv              Docker Images
       ↓                    ↓                        ↓
  Models (.joblib)     FastAPI Services         Containerized APIs
       ↓                    ↓                        ↓
  Data Analysis        Docker Infrastructure    Full Stack
```

## Data Pipeline

```
GNews API → ingest-service → Kafka (raw_articles)
                          → ml-platform consumer → Kafka (processed_articles)
                                         → database-service → PostgreSQL + Elasticsearch
                                         → modular-api → Frontend

Energy Service (port 8006) → PostgreSQL (energy schema)
                          → Standalone catalog; risk_engine blends ML scores from ml-platform

ML Platform (port 8007) → PostgreSQL (ml schema)
                       → Consumes Energy Service data; serves prediction API
                       → Kafka consumer (consumer/article_enrichment.py) for article
                          enrichment — replaces the retired ml-service/ml-consumer pair
```

## Development Architecture

```
VS Code
    │
    ├── ingest-service ── .venv ── uvicorn :8001
    ├── embedding-service─ .venv ── uvicorn :8005
    ├── database-service ─ .venv ── uvicorn :8003
    ├── energy-service ─── .venv ── uvicorn :8006
    ├── ml-platform ────── .venv ── uvicorn :8007 (also runs the article-enrichment consumer)
    ├── modular-api ────── .venv ── uvicorn :8000
    └── frontend ───────── node ── vite :8080
                │
                ▼
        Docker Infrastructure
            │
            ├── PostgreSQL :5434 (mapped from container's 5432 — see 06_ENVIRONMENT_VARIABLES.md)
            ├── Kafka      :9092
            └── Elasticsearch :9200
```

## Production Architecture

```
docker-compose.full.yml
    │
    ├── All services in Docker containers
    ├── Healthchecks on every service
    ├── Docker bridge network (proxy_net)
    └── Volumes for PostgreSQL + Elasticsearch
```

## Service Dependencies

| Service | Depends On |
|---------|-----------|
| ingest-service | Kafka |
| ml-platform | Kafka, PostgreSQL, energy-service |
| embedding-service | PostgreSQL, Kafka |
| database-service | Kafka, PostgreSQL, Elasticsearch |
| modular-api | PostgreSQL, Elasticsearch |
| energy-service | PostgreSQL |
| ml-platform | PostgreSQL, energy-service |
| frontend | modular-api |

## Shared Code

All services share code from `backend/shared/`:

- `config.py` — Settings class with required env vars
- `db_pool.py` — PostgreSQL connection pool
- `elastic_client.py` — Elasticsearch client
- `logging_config.py` — Structured logging (structlog)
- `request_middleware.py` — Request tracking middleware
- `entity_normalization.py` — Entity normalization utilities
- `schema_bootstrap.py` — Schema initialization helpers
