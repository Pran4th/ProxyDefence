# ProxyDefence Service Architecture

## Overview

ProxyDefence is a military-grade cyber defense intelligence platform. Data flows through a Kafka pipeline: news is ingested from GNews API, processed by ML/NLP (sentiment, entities, topics, threats), and stored in PostgreSQL and Elasticsearch. A modular FastAPI gateway serves the React frontend.

8 microservices + 3 infrastructure components (PostgreSQL, Kafka, Elasticsearch).

---

## Service Responsibility Map

| Service | Port | Kafka | DB | API | Responsibility |
|---------|------|-------|----|-----|----------------|
| ingest-service | 8001 | Producer (`raw_articles`) | None | Yes | Fetch news from GNews, publish to Kafka |
| ml-service | 8002 | Consumer + Producer | None | Yes | NLP enrichment (sentiment, entities, topics, threats) |
| database-service | 8003 | Consumer | PG + ES | Yes | Store articles, event correlation, search |
| embedding-service | 8005 | Consumer | PG (vector) | Yes | Generate embeddings, semantic search |
| energy-service | 8006 | None | PG (energy) | Yes | Energy infrastructure catalog |
| ml-platform | 8007 | None | PG (ml) | Yes | ML training, feature store, model registry, inference |
| modular-api (backend/api_service) | 8000 | None | PG + ES | Yes | API gateway for frontend |
| frontend | 8080 | None | None | Yes (browser) | React + Vite UI |

---

## Standard Service Layout

Every service follows this pattern:

```
service/
  app.py          # FastAPI application: lifespan, middleware, router registration, health endpoints
  config.py       # Service-specific environment variables
  db.py           # Database pool: get_pool(), close_pool(), ensure_schema() (if DB needed)
  consumer.py     # Kafka consumer (standalone process, if Kafka needed)
  models.py       # Pydantic models (if complex schemas)
  routers/        # API route files (if many endpoints)
  services/       # Business logic modules
  utils/          # Helper/utility functions
```

Folders are omitted when unnecessary (no Kafka -> no consumer.py, no DB -> no db.py).

---

## Startup Lifecycle (Every Service)

Every FastAPI service uses the `lifespan` context manager (not `@app.on_event` decorators):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting")
    # 1. Initialize logging (already done at module level)
    # 2. Load models / resources
    # 3. Initialize database pool
    # 4. Bootstrap schema if needed
    yield
    # 5. Close pool
    # 6. Flush/flush connections
    logger.info("service_stopped")
```

---

## Health Endpoints (Every API Service)

Every service exposes these 5 endpoints with consistent response structure:

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /` | Service identity | `{"service": "name", "version": "x.y.z"}` |
| `GET /health` | Full health check | `{"status": "healthy"/"unhealthy", ...deps}` |
| `GET /liveness` | Process alive check | `{"status": "alive"}` |
| `GET /readiness` | Dependency check | `{"status": "healthy"/"unhealthy", ...details}` |
| `GET /version` | Version info | `{"service": "name", "version": "x.y.z"}` |

---

## Database Ownership

Every service owns its own database schema. No two services write to the same schema:

| Schema | Owner | Tables |
|--------|-------|--------|
| `public` | database-service (writer), modular-api (reader) | processed_articles, extracted_entities, events, users, watchlists, alerts, cases, reports |
| `energy` | energy-service | locations, organizations, ports, oil_fields, pipelines, refineries, ... |
| `ml` | ml-platform | feature_definitions, datasets, model_versions, predictions, training_runs |

Database access is encapsulated in `db.py` with standard functions:

```python
get_pool()      # Return initialized connection pool
close_pool()    # Close and clear pool
ensure_schema() # Apply DDL if schema doesn't exist (ml-platform)
bootstrap()     # Apply DDL + seed data if schema doesn't exist (energy-service)
```

---

## Kafka Pipeline

```
GNews API -> ingest-service -> raw_articles [topic]
                                  |
                            ml-service (ml-service-group)
                                  |
                            processed_articles [topic]
                               /              \
                  db-service-group    embedding-service-group
                       |                       |
                  PostgreSQL + ES         pgvector embeddings
```

- **Topics**: `raw_articles`, `processed_articles` — auto-created by Kafka
- **Serialization**: Plain JSON (no schema registry)
- **Consumer groups**: Each consumer has a unique `group.id`:
  - `ml-service-group` consumes `raw_articles`
  - `db-service-group` consumes `processed_articles`
  - `embedding-service-group` consumes `processed_articles`
- **Offset management**: All consumers use `enable.auto.commit=False` with manual `commit()` after successful processing
- **Error handling**: Malformed messages are logged and skipped (commit + continue)

---

## Kafka Consumer Pattern (Every Consumer)

Every Kafka consumer follows this exact lifecycle:

```python
consumer = Consumer({
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "group.id": "...",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
})
consumer.subscribe(["topic"])

try:
    while running:
        msg = consumer.poll(1.0)
        if msg is None: continue
        if msg.error(): continue
        # process message
        consumer.commit()
finally:
    consumer.close()
```

Consumers run as standalone processes (`python consumer.py`), not inside the FastAPI process. Signal handlers (SIGTERM/SIGINT) set `running = False` for graceful shutdown.

---

## Configuration

### Shared Configuration (`backend/shared/`)

| Module | Purpose |
|--------|---------|
| `config.py` | Loads `.env`, exposes `SERVICE_VERSION`, `GIT_COMMIT`, `_required_env()` |
| `settings.py` | `Settings` class with validated PG/ES/JWT config (only imported by services that need it) |
| `logging_config.py` | `setup_structlog()`, `get_logger()` for structured logging |
| `request_middleware.py` | `RequestTrackingMiddleware` for request/correlation IDs |
| `db_pool.py` | `get_pg_pool()`, `close_pg_pool()` — asyncpg pool for modular-api |
| `elastic_client.py` | `get_es_client()`, `close_es_client()` — AsyncElasticsearch for modular-api |
| `schema_bootstrap.py` | `bootstrap_schema()` — idempotent schema initialization |
| `entity_normalization.py` | Entity name aliases and blacklists |
| `kafka_monitor.py` | Kafka consumer group monitoring |

### Service-Specific Configuration

Each service has its own `config.py` for service-specific env vars:

- **ingest-service**: `NEWS_API_KEY`, `KAFKA_BOOTSTRAP_SERVERS`
- **ml-service**: `KAFKA_BOOTSTRAP_SERVERS` (in consumer.py)
- **database-service**: `POSTGRES_*`, `ELASTICSEARCH_*`, `JWT_*`, `KAFKA_BOOTSTRAP_SERVERS`
- **embedding-service**: `POSTGRES_*`, `EMBEDDING_MODEL_NAME`
- **energy-service**: `POSTGRES_*`
- **ml-platform**: `POSTGRES_*`, `ENERGY_SERVICE_URL`, `MLFLOW_TRACKING_URI`, `DVC_REMOTE`

Services that need PG/ES/JWT configuration use `backend.shared.settings` (which validates all required env vars). Services that only need `SERVICE_VERSION` import from `backend.shared.config` directly.

---

## Logging

All services use structured logging via `structlog`:

```python
from backend.shared.logging_config import setup_structlog, get_logger

setup_structlog("service-name")
logger = get_logger(__name__)

logger.info("event_name", key="value", count=42)
```

No service uses `logging.basicConfig`, `print()`, stdlib `logging.getLogger()`, or mixed logging styles.

---

## Module Layout by Service

### ingest-service

```
ingest-service/
  app.py              # FastAPI: lifespan (scheduler start/stop), health endpoints, /fetch-real-news
  config.py           # KAFKA_BOOTSTRAP_SERVERS, NEWS_API_KEY
  producer.py         # Kafka Producer, delivery callback, check_kafka_connection, flush_producer
  services/
    news_fetcher.py   # fetch_real_news() — GNews API + Kafka produce
```

### ml-service

```
ml-service/
  app.py              # FastAPI: lifespan (load models), health endpoints
  consumer.py         # Kafka consumer: consumes raw_articles, produces processed_articles
  ml_core/            # ML modules: models, sentiment, entities, text, topic, threat, relationships
```

### database-service

```
database-service/
  app.py              # FastAPI: lifespan (init pool), health endpoints, JWT auth, route handlers
  config.py           # POSTGRES_*, ELASTICSEARCH_*, JWT_*, KAFKA_BOOTSTRAP_SERVERS
  consumer.py         # Kafka consumer: consumes processed_articles, stores in PG + ES
  db.py               # PostgreSQL pool + ES client: create_pool, get_pool, close_pool, get_es
  services/
    database.py           # Article CRUD: upsert_article, fetch_articles, get_analytics_summary
    event_intelligence.py # Event correlation: update_event_intelligence, replace_related_records
    elastic_indexer.py    # ES operations: index_article, search_articles
```

### embedding-service

```
embedding-service/
  app.py              # FastAPI: lifespan (load model, init pool), health endpoints, /search, /generate
  config.py           # POSTGRES_*, EMBEDDING_MODEL_NAME
  consumer.py         # Kafka consumer: consumes processed_articles, stores embeddings in pgvector
  db.py               # asyncpg pool: create_pool, get_pool, close_pool, ensure_vector_extension
  services/
    embeddings.py     # Shared embedding logic: load_model, embed_text, make_vector_str
```

### energy-service

```
energy-service/
  app.py              # FastAPI: lifespan (init pool, bootstrap schema), health endpoints
  config.py           # POSTGRES_*
  db.py               # asyncpg pool: get_pool, close_pool, bootstrap
  models.py           # Pydantic models for 14 entity types
  routers/            # catalog, relationships, events, history, bulk
  parsers/            # Bulk import parsers (csv, json, geojson)
  filters.py          # FilterParams for standardized list endpoints
  seed.py             # Idempotent seed data loader
  seed_data/          # JSON seed data files
```

### ml-platform

```
ml-platform/
  app.py              # FastAPI: lifespan (init pool, ensure schema), health endpoints
  config.py           # POSTGRES_*, ENERGY_SERVICE_URL, MLFLOW_TRACKING_URI, DVC_REMOTE
  db.py               # asyncpg pool: get_pool, close_pool, ensure_schema
  models.py           # Pydantic models for features, datasets, training, inference
  routers/            # features, datasets, models, inference
  feature_store/      # Feature registry, feature builders
  training/           # Model training, experiment tracking, hyperparameter optimization
  inference/          # Prediction API, model loading
  registry/           # Model registry (5-stage lifecycle)
  pipeline/           # Dataset builder, explainability
  evaluation/         # Metrics, reporting
  datasets/           # Data loader, versioning
  tests/              # Test suite (49 tests)
```

### modular-api (backend/api_service)

```
backend/api_service/
  main.py             # FastAPI: lifespan (init PG + ES), middleware, router registration
  security.py         # JWT auth: hash_password, verify_password, create_access_token, get_current_user
  response.py         # Response helpers: success_response, error_response, APIResponse
  dto.py              # Pydantic DTOs: PageParams, ReportGenerateRequest, WatchlistCreateRequest
  rate_limit.py       # slowapi Limiter instance
  routers/            # 15 route files (health, auth, articles, analytics, search, events, etc.)
  services/           # Business logic (CopilotService, etc.)
  repositories/       # Data access (IntelligenceRepository)
```

---

## Request Flow

```
Browser -> Vite (port 8080) -> modular-api (port 8000) -> PostgreSQL / Elasticsearch
                                                      -> embedding-service (HTTP, semantic search)
                                                      -> database-service (Kafka consumer, writes)
```

Frontend communicates exclusively with modular-api. No direct frontend-to-service calls.

---

## How to Add a New Service

1. Create `services/new-service/` with `app.py`, `config.py`, `db.py` (if DB needed)
2. Follow the standard `app.py` pattern: `lifespan`, 5 health endpoints, middleware
3. Use `setup_structlog()`, `get_logger()` for logging
4. Use `backend.shared.config` or `backend.shared.settings` for shared config
5. Add `scripts/dev/backend/start-new-service.ps1`
6. Add debug config to `.vscode/launch.json`
7. Add to `docker-compose.full.yml` if production deployment
