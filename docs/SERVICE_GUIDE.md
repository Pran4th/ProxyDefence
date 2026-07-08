# Service Guide

## Quick-Reference Table

| Service | Port | Kafka Role | DB Schema | Health Endpoint | Start Command |
|---------|------|------------|-----------|-----------------|---------------|
| Ingest | 8001 | Producer (`raw_articles`) | None | `GET /health` | `start-ingest.ps1` |
| ML | 8002 | Consumer (`raw_articles`) + Producer (`processed_articles`) | None | `GET /health` | `start-ml.ps1` |
| Database | 8003 | Consumer (`processed_articles`) | `public` (writer) | `GET /health` | `start-database.ps1` |
| Embedding | 8005 | Consumer (`processed_articles`) | `public` (pgvector) | `GET /health` | `start-embedding.ps1` |
| Energy | 8006 | None | `energy` | `GET /health` | `start-energy.ps1` |
| ML Platform | 8007 | None | `ml` | `GET /health` | `start-ml-platform.ps1` |
| Modular API | 8000 | None | `public` (reader) | `GET /health` | `start-modular-api.ps1` |
| Frontend | 8080 | None | None | `GET /` | `start-frontend.ps1` |

---

## Ingest Service (port 8001)

**Purpose:** Fetches news articles from the GNews API and publishes them as raw messages to Kafka topic `raw_articles`.

**Startup:**
1. Initializes structlog and health builder
2. Runs an initial `fetch_real_news()` call to seed data
3. Starts an APScheduler job that fetches news every hour
4. Exposes Prometheus metrics at `/metrics`

**Endpoints:**
- `GET /` — service identity + scheduler status
- `GET /health` — checks Kafka connectivity
- `GET /liveness` — process alive
- `GET /readiness` — same as health
- `GET /version` — version info
- `GET /fetch-real-news` — trigger an immediate fetch

**Env Vars:**
- `NEWS_API_KEY` (required) — GNews API key
- `KAFKA_BOOTSTRAP_SERVERS` (default: `kafka:9092`)
- `SERVICE_VERSION` (default: `1.0.0`)

**What happens on start:** Kafka producer initializes → news is fetched → articles are published to `raw_articles` topic → scheduler starts hourly polling.

---

## ML Service (port 8002)

**Purpose:** Consumes `raw_articles` from Kafka, performs NLP enrichment (sentiment analysis, entity extraction, topic classification, threat scoring), and publishes processed results to `processed_articles` topic.

**Startup:**
1. Loads spaCy model (`en_core_web_sm`) for NER
2. Initializes sentiment analysis pipeline
3. Registers model health checks
4. Consumer runs as a **separate process** (`consumer.py`), not in the FastAPI process

**Endpoints:**
- `GET /` — service identity
- `GET /health` — checks model loading status
- `GET /liveness` — process alive
- `GET /readiness` — same as health
- `GET /version` — version info

**Env Vars:**
- `KAFKA_BOOTSTRAP_SERVERS` (default: `kafka:9092`)
- `SERVICE_VERSION` (default: `1.0.0`)

**What happens on start:** spaCy and transformer models are loaded into memory → FastAPI starts serving health endpoints → consumer.py (separate process) polls `raw_articles`, enriches each message, and publishes to `processed_articles`.

---

## Database Service (port 8003)

**Purpose:** Consumes `processed_articles` from Kafka, stores articles in PostgreSQL (`public.processed_articles`), indexes them in Elasticsearch, and provides REST endpoints for querying.

**Startup:**
1. Initializes asyncpg connection pool
2. Initializes Elasticsearch client
3. Consumer runs as a separate process (`consumer.py`)

**Endpoints:**
- `GET /` — service identity
- `GET /health` — checks PostgreSQL + Elasticsearch
- `GET /liveness` — process alive
- `GET /readiness` — dependency check
- `GET /version` — version info
- `GET /api/articles` — list/filter articles
- `GET /api/articles/{article_id}` — single article
- `GET /api/analytics/summary` — analytics summary
- `GET /api/search` — search articles

**Env Vars:**
- `POSTGRES_*` — host, port, db, user, password
- `ELASTICSEARCH_*` — host, port, user, password
- `JWT_SECRET_KEY` (required)
- `JWT_ALGORITHM` (default: `HS256`)
- `KAFKA_BOOTSTRAP_SERVERS` (default: `kafka:9092`)
- `SERVICE_VERSION` (default: `1.0.0`)

**What happens on start:** Database pool created → Elasticsearch client initialized → FastAPI serves endpoints → consumer.py persists articles to PG + ES.

---

## Embedding Service (port 8005)

**Purpose:** Consumes `processed_articles` from Kafka, generates vector embeddings using a sentence-transformer model, and stores them in PostgreSQL with pgvector extension.

**Startup:**
1. Loads embedding model (default: `BAAI/bge-small-en-v1.5`)
2. Initializes asyncpg pool
3. Ensures pgvector extension exists
4. Consumer runs as separate process (`consumer.py`)

**Endpoints:**
- `GET /` — service identity
- `GET /health` — checks PostgreSQL + model
- `GET /liveness` — process alive
- `GET /readiness` — dependency check
- `GET /version` — version info
- `POST /generate` — generate embedding for text
- `GET /search` — semantic search (k-NN)

**Env Vars:**
- `POSTGRES_*` — host, port, db, user, password
- `EMBEDDING_MODEL_NAME` (default: `BAAI/bge-small-en-v1.5`)
- `KAFKA_BOOTSTRAP_SERVERS` (default: `kafka:9092`)
- `SERVICE_VERSION` (default: `1.0.0`)

**What happens on start:** Embedding model downloaded + loaded → pgvector extension ensured → consumer.py generates embeddings for each article → FastAPI serves search/generate endpoints.

---

## Energy Service (port 8006)

**Purpose:** Authoritative infrastructure catalog for the energy domain. Manages 14 entity types (locations, organizations, ports, oil/gas fields, pipelines, refineries, power plants, storage facilities, SPRs, import corridors, shipping routes, suppliers) with full CRUD, relationships, events, and capacity history.

**Startup:**
1. Initializes asyncpg pool
2. Bootstraps `energy` schema (DDL from `infra/sql/energy_schema.sql`)
3. Loads seed data if `ENERGY_LOAD_SEED=1`

**Endpoints:**
- `GET /` — service identity
- `GET /health` — checks PostgreSQL connectivity + latency
- `GET /liveness` — process alive
- `GET /readiness` — same as health
- `GET /version` — version info
- `GET /api/v1/energy/{entity}` — list entities with filtering
- `GET /api/v1/energy/{entity}/{uuid}` — single entity
- `POST /api/v1/energy/{entity}` — create entity
- `PUT /api/v1/energy/{entity}/{uuid}` — update entity
- `DELETE /api/v1/energy/{entity}/{uuid}` — soft delete
- `POST /api/v1/energy/bulk/import` — bulk import (JSON, CSV, GeoJSON)

**Env Vars:**
- `POSTGRES_*` — host, port, db, user, password
- `ENERGY_LOAD_SEED` (default: unset, set to `1` to load seed data)
- `SERVICE_VERSION` (default: `1.0.0`)

**What happens on start:** Schema bootstrapped via `energy_schema.sql` → if `ENERGY_LOAD_SEED=1`, seed data is upserted → FastAPI serves catalog API.

---

## ML Platform (port 8007)

**Purpose:** Production ML infrastructure: feature store, dataset builder, model training with MLflow tracking, model registry with 5-stage lifecycle, and prediction API. Consumes data from Energy Service REST API.

**Startup:**
1. Initializes asyncpg pool
2. Ensures `ml` schema exists (DDL from `infra/sql/ml_schema.sql`)
3. Prepares dataset directories

**Endpoints:**
- `GET /` — service identity
- `GET /health` — checks PostgreSQL
- `GET /liveness` — process alive
- `GET /readiness` — same as health
- `GET /version` — version info
- Feature store: CRUD for feature definitions
- Datasets: build, version, list
- Models: train, register, promote, archive
- `POST /api/v1/predict` — run prediction

**Env Vars:**
- `POSTGRES_*` — host, port, db, user, password
- `ENERGY_SERVICE_URL` (default: `http://energy-service:8000`)
- `MLFLOW_TRACKING_URI` (default: `file:./mlruns`)
- `DVC_REMOTE` (default: `./data/dvc-store`)
- `DATASET_DIR` (default: `./data/datasets`)
- `ARTIFACT_DIR` (default: `./data/artifacts`)
- `DEFAULT_RANDOM_SEED` (default: `42`)
- `SERVICE_VERSION` (default: `1.0.0`)

**What happens on start:** ML schema created → feature definitions loaded → FastAPI serves ML endpoints.

---

## Modular API (port 8000)

**Purpose:** Main API gateway for the frontend. Proxies and aggregates data from database-service, embedding-service, and others. Handles authentication, authorization, rate limiting.

**Startup:**
1. Initializes asyncpg pool
2. Initializes Elasticsearch client
3. Registers all route modules (auth, articles, analytics, search, semantic-search, events, entities, reports, watchlists, alerts, cases, copilot)

**Endpoints:**
- `GET /` — service identity
- `GET /health` — checks PostgreSQL + Elasticsearch
- `GET /liveness` — process alive
- `GET /readiness` — dependency check
- `GET /version` — version info
- `POST /auth/login`, `POST /auth/register` — authentication
- `GET /api/articles` — list articles
- `GET /api/analytics/summary` — analytics
- `GET /api/search` — full-text search
- `POST /api/semantic-search` — vector similarity search
- `GET /api/events` — event correlation
- `GET /api/entities` — entity profiles
- `POST /api/reports/generate` — generate reports
- `GET /api/watchlists` — watchlist management
- `GET /api/alerts` — alert management
- `GET /api/cases` — case management
- `POST /api/copilot/chat` — AI copilot

**Env Vars:**
- `POSTGRES_*` — host, port, db, user, password
- `ELASTICSEARCH_*` — host, port, user, password
- `JWT_SECRET_KEY` (required)
- `JWT_ALGORITHM` (default: `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default: `60`)
- `CORS_ORIGINS` (default: `http://localhost:3000,http://127.0.0.1:3000`)
- `SERVICE_VERSION` (default: `1.0.0`)

**What happens on start:** PG pool + ES client created → 15+ route modules registered → JWT auth middleware active → rate limiter configured → FastAPI serves frontend-facing API.

---

## Frontend (port 8080)

**Purpose:** React 18 + TypeScript 5.8 + Vite 5.4 UI. Communicates exclusively with modular-api (port 8000).

**Start command:** `npm run dev` (or `start-frontend.ps1`)

**Env Vars:**
- `VITE_API_URL` (default: `http://localhost:8000`)

## Consumer Processes

The following Kafka consumer processes **must** run alongside the API services:

| Consumer | Topic | Group ID | Start Command |
|----------|-------|----------|---------------|
| ml-consumer | `raw_articles` | `ml-service-group` | `python services/ml-service/consumer.py` |
| db-consumer | `processed_articles` | `db-service-group` | `python services/database-service/consumer.py` |
| embedding-consumer | `processed_articles` | `embedding-service-group` | `python services/embedding-service/consumer.py` |

Consumers are started automatically by `start-local.ps1` in separate PowerShell windows.
