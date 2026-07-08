# Architecture Review: ProxyDefence

**Date:** 2026-07-04
**Scope:** Post-refactor architecture analysis
**Method:** Full codebase inspection, import graph analysis, startup sequence tracing, responsibility mapping
**Constraint:** No code changes — observation only

---

## PART 1 — Repository Architecture

### Directory Tree (trimmed)

```
C:\ProxyWars\ProxyDefence\
├── .env                          # Active local dev config (127.0.0.1 hosts)
├── .env.example                  # Template for Docker hostnames
├── docker-compose.yml            # Infra only: postgres, kafka, zookeeper, elasticsearch
├── docker-compose.full.yml       # Full stack: infra + 10 app + 1 frontend
├── CLAUDE.md                     # Primary project documentation
├── alembic.ini                   # Alembic config for shared migrations
├── backend/
│   ├── api_service/              # ← modular-api (FastAPI app on port 8000)
│   │   ├── main.py               # App entry, lifespan, middleware, routes
│   │   ├── security.py           # JWT + bcrypt auth
│   │   ├── response.py           # Standardized API envelope
│   │   ├── rate_limit.py         # slowapi 60/min default
│   │   ├── dto.py                # Pydantic DTOs
│   │   ├── routes/               # 13 route files
│   │   ├── repositories/         # intelligence.py (1396 lines), copilot_repository.py
│   │   └── services/             # cache.py (TTL), copilot_service.py (threat assessment)
│   └── shared/                   # Shared library across ALL services
│       ├── config.py             # Settings class + _load_dotenv() + _required_env
│       ├── logging_config.py     # structlog JSON setup
│       ├── request_middleware.py # X-Request-ID / X-Correlation-ID
│       ├── db_pool.py            # asyncpg pool singleton (modular-api only)
│       ├── elastic_client.py     # AsyncElasticsearch singleton (modular-api only)
│       ├── kafka_monitor.py      # Kafka consumer lag (modular-api only)
│       ├── entity_normalization.py # Alias maps, blacklists
│       ├── schema_bootstrap.py   # Idempotent schema bootstrap helper
│       └── migrations/           # 4 Alembic migration scripts
├── services/
│   ├── ingest-service/           # port 8001: app.py, Dockerfile, requirements.txt
│   ├── ml-service/               # port 8002: app.py, consumer.py, ml_core/ (7 modules)
│   ├── database-service/         # port 8003: app.py, consumer.py
│   ├── embedding-service/        # port 8005: app.py, consumer.py
│   ├── energy-service/           # port 8006: app.py, db.py, models.py, filters.py
│   │                               seed.py, parsers/, routers/, seed_data/ (17 JSON)
│   ├── ml-platform/              # port 8007: app.py, db.py, config.py, models.py
│   │                               feature_store/, datasets/, training/, inference/
│   │                               registry/, evaluation/, pipeline/, routers/, tests/
│   ├── modular-api/              # port 8000: Dockerfile, requirements.txt only
│   │                               (code lives in backend/api_service/)
│   └── frontend/                 # port 8081: React 18 + Vite + shadcn/ui
├── scripts/
│   ├── check-env.py              # Environment validation
│   ├── dev/setup/setup.ps1+.sh   # One-time: create all .venvs, install deps
│   ├── dev/common/load-env.ps1+.sh # Source .env into environment
│   ├── dev/infrastructure/       # start/stop/restart-infra (.ps1 + .sh)
│   ├── dev/backend/              # 8 pairs: 7 services + start-all + start-consumers
│   ├── dev/frontend/             # start-frontend.ps1 + .sh
│   ├── maintenance/              # clean.ps1+.sh, reset.ps1+.sh
│   └── testing/                  # run-tests.ps1 + .sh
├── infra/sql/
│   ├── init.sql                  # public schema: 20 tables, 30+ indexes, pgvector
│   ├── energy_schema.sql         # energy schema: 17 tables, 9 ENUMs, 40+ indexes
│   └── ml_schema.sql             # ml schema: 4 tables, 4 ENUMs
├── research/
│   ├── notebooks/                # 8 Jupyter notebooks (EDA → Model Export)
│   ├── datasets/fetch_data.py    # Energy Service REST client + synthetic fallback
│   └── requirements-research.txt # Full ML stack (mlflow, dvc, shap, optuna, lightgbm)
└── tests/
    ├── conftest.py               # ASGI test client with PG + ES
    ├── test_auth.py              # 4 auth tests
    └── test_health.py            # 4 health tests
```

### Summary Counts

| Artifact | Count |
|----------|-------|
| Python microservices | 7 (6 FastAPI + 1 frontend) |
| Python shared modules | 9 |
| Python route files | 21 |
| Python consumer processes | 3 (standalone) |
| Infrastructure services | 4 |
| Dockerfiles | 8 |
| Docker Compose files | 2 |
| SQL schema files | 3 |
| Migration scripts | 4 |
| Shell/PowerShell scripts | 31 (15 PS1 + 15 SH + 1 PY) |
| Jupyter notebooks | 8 |
| Seed data JSON files | 17 |
| Database tables | 41 (20 public + 17 energy + 4 ml) |
| Database ENUM types | 13 (9 energy + 4 ml) |

---

## PART 2 — Responsibilities

### ingest-service (port 8001)

**Purpose:** External data ingestion — fetches news from GNews API and publishes to Kafka.

**Responsibilities:**
- Fetch news articles from GNews API on demand and on schedule (1-hour APScheduler)
- Deduplicate by URL hash (SHA256)
- Publish raw articles to `raw_articles` Kafka topic

**Inputs:** GNews API, manual trigger via `GET /fetch-real-news`

**Outputs:** Kafka topic `raw_articles`

**Dependencies:** `confluent-kafka` (Producer), `requests` (HTTP), `APScheduler` (scheduler)

**Consumers of output:** ml-service (consumer group `ml-service-group`)

### ml-service (port 8002)

**Purpose:** NLP enrichment pipeline — consumes raw articles, applies ML models, publishes enriched articles.

**Responsibilities:**
- Consume articles from `raw_articles` Kafka topic
- Load spaCy + Transformers models on startup
- Extract entities (NER), classify topic, analyze sentiment, score threat level
- Extract keywords, summarize text, infer entity relationships
- Build deduplication key (SHA256)
- Publish enriched articles to `processed_articles` Kafka topic

**Inputs:** Kafka topic `raw_articles`

**Outputs:** Kafka topic `processed_articles`

**Dependencies:** `confluent-kafka` (Consumer + Producer), `spacy`, `transformers`

**Consumers of output:** database-service (group `db-service-group`), embedding-service (group `embedding-service-group`)

### ml-platform (port 8007)

**Purpose:** Production ML infrastructure — feature store, dataset builder, model training, registry, prediction API.

**Responsibilities:**
- Manage versioned feature definitions (11 feature types)
- Build datasets from Energy Service data (train/val/test splits)
- Train baseline models (LogReg, DecisionTree, RandomForest, XGBoost, LightGBM)
- Track experiments via MLflow; Registry with 5-stage model lifecycle
- Serve predictions via REST API with latency logging
- Hyperparameter optimization (Grid, Random, Optuna); Model explainability (SHAP)

**Inputs:** Energy Service REST API, MLflow tracking server

**Outputs:** REST API predictions, `.joblib` artifacts, MLflow runs

**Dependencies:** `scikit-learn`, `xgboost`, `lightgbm` (optional), `joblib`, `pandas`, `numpy`, `mlflow` (optional), `dvc` (optional), `shap` (optional)

**Consumers of output:** Future services (Risk Engine, Copilot, Digital Twin per docs)

### database-service (port 8003)

**Purpose:** Persistence layer — stores processed articles in PostgreSQL, indexes in Elasticsearch, manages event correlation and alert generation.

**Responsibilities:**
- Consume enriched articles from `processed_articles` Kafka topic
- Upsert articles into PostgreSQL; replace related records (entities, sentiments, relationships)
- Index articles into Elasticsearch
- Event correlation engine: entity overlap scoring (60%) + topic (15%) + time proximity (15%) + semantic similarity (10%) — creates/updates events, entity_profiles, alerts
- Serve article query API, analytics summary, Elasticsearch search
- Rebuild events from scratch (admin-only endpoint)

**Inputs:** Kafka topic `processed_articles`

**Outputs:** PostgreSQL `public.` schema, Elasticsearch `processed_articles` index

**Dependencies:** `psycopg2-binary`, `elasticsearch`, `confluent-kafka`, `python-jose`

### embedding-service (port 8005)

**Purpose:** Vector embedding generation — converts article text to dense vectors and stores in pgvector.

**Responsibilities:**
- Load `BAAI/bge-small-en-v1.5` embedding model
- Consume articles from `processed_articles` Kafka topic
- Generate 384-dimensional embeddings
- Store in `article_embeddings` table (pgvector, HNSW index)
- Serve semantic search API (`<=>` cosine similarity); backfill APIs

**Inputs:** Kafka topic `processed_articles`

**Outputs:** PostgreSQL `article_embeddings` (pgvector)

**Dependencies:** `fastembed`, `asyncpg`, `confluent-kafka`

### energy-service (port 8006)

**Purpose:** Authoritative energy infrastructure catalog — 14 entity types, relationships, events, capacity history.

**Responsibilities:**
- CRUD for 14 entity types with soft delete and data provenance
- Polymorphic entity relationships; infrastructure events tracking; capacity history
- Filtering: search, sort, status, criticality, org, location, tag
- Bulk import (JSON/CSV/GeoJSON); network graph API; dashboard summary
- Schema auto-bootstrap on startup; idempotent seed data (207+ entities)

**Inputs:** Seed data, REST API requests, bulk import files

**Outputs:** REST API responses

**Dependencies:** `asyncpg`, `python-multipart`

**Consumers of output:** ml-platform (dataset builder via REST API)

### modular-api (port 8000)

**Purpose:** API gateway and intelligence platform — serves all frontend-facing endpoints.

**Responsibilities:**
- User auth (register, login, JWT); rate limiting (60/min); CORS
- Articles, analytics (8 endpoints), search (full-text + semantic)
- Entities, events, relationship graph, cases, watchlists, alerts, reports
- Copilot intelligence query; Kafka monitoring; request auditing

**Inputs:** PostgreSQL `public.` schema, Elasticsearch, embedding-service REST

**Outputs:** REST API responses to frontend

**Dependencies:** `asyncpg`, `elasticsearch`, `slowapi`, `python-jose`, `passlib`+`bcrypt`

### frontend (port 8081)

**Purpose:** React SPA for threat intelligence visualization.

**Inputs:** modular-api REST API (port 8000)
**Outputs:** Browser UI
**Dependencies:** React 18, React Router 6, TanStack Query (configured but unused), Axios, Recharts, shadcn/ui, Cytoscape

---

## PART 3 — Data Flow

### Primary Pipeline: News → Intelligence

```
  GNews API
      │
      ▼
  ┌──────────────────┐
  │  ingest-service  │  port 8001
  │  (APScheduler)   │
  └────────┬─────────┘
           │ HTTP GET /fetch-real-news (or hourly scheduler)
           ▼
  ┌──────────────────┐
  │  raw_articles    │  Kafka topic (partition 0)
  └────────┬─────────┘
           │ consumed by ml-service-group
           ▼
  ┌──────────────────┐
  │  ml-service      │  port 8002
  │  consumer.py     │  (separate process)
  │                   │
  │  1. Load models   │
  │  2. enrich_article│  entity NER → sentiment → topic → threat → keywords → relationships
  │  3. Publish result│
  └────────┬─────────┘
           │ publish to processed_articles
           ▼
  ┌──────────────────┐
  │ processed_articles│  Kafka topic (partition 0)
  └──┬──────────┬───┘
     │          │
     │          │ consumed by embedding-service-group
     │          ▼
     │  ┌──────────────────┐
     │  │ embedding-service │  port 8005
     │  │ consumer.py       │
     │  │ 1. Load bge model│
     │  │ 2. Generate 384d  │
     │  │ 3. INSERT INTO     │
     │  │    article_embeddings│
     │  └──────────────────┘
     │
     │ consumed by db-service-group
     ▼
  ┌──────────────────────────────┐
  │  database-service            │  port 8003
  │  consumer.py                 │
  │  1. upsert_article()         │  → PostgreSQL processed_articles
  │  2. replace_related_records()│  → entities / sentiments / relationships
  │  3. update_event_intelligence│  → event matching + scoring engine
  │     (60% entity + 15% topic + 15% time + 10% semantic)
  │     → CREATE/UPDATE events, event_articles, event_entities
  │     → UPSERT entity_profiles
  │     → GENERATE alerts (watchlist matches)
  │  4. index_article()           │  → Elasticsearch
  └──────────────────────────────┘
           │
           ▼
  ┌──────────────────────────────┐
  │  PostgreSQL + Elasticsearch   │
  └──────────────────────────────┘
           │
           ▼
  ┌──────────────────────┐
  │  modular-api          │  port 8000
  │  Reads PG + ES +      │
  │  embedding-service    │
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │  frontend            │  port 8081
  │  20 pages            │
  └──────────────────────┘
```

### Energy Domain Flow

```
  Energy Service (port 8006)
       │
       │ Bootstrap on startup: energy_schema.sql → seed data (207+ entities)
       ▼
  PostgreSQL [energy schema] ←─ REST API ──→ ml-platform (dataset builder)
```

### ML Platform Flow

```
  POST /features → Feature definitions
  POST /datasets → Fetch from Energy Service → Feature matrix → Parquet + DVC
  POST /models   → Train → MLflow → .joblib → Registry (development→staging→production)
  POST /predict  → Load .joblib (cached) → Preprocess → Predict → Log → Return
```

### Frontend Data Flow

```
  React SPA → Axios → modular-api → PostgreSQL / Elasticsearch / embedding-service

---

## PART 4 — ML Architecture

### Three Distinct ML Components

The repository has THREE separate ML-related components with entirely different responsibilities:

| Component | Role | Training? | Inference? | Kafka? | Models |
|-----------|------|-----------|------------|--------|--------|
| **ml-service** (8002) | NLP pipeline | No (pre-trained only) | Real-time | Yes | spaCy, HuggingFace |
| **ml-platform** (8007) | Production ML infra | Yes (5 algorithms) | On-demand API | No | sklearn, xgboost, lightgbm |
| **research/** | Experimentation | Yes (notebooks) | No | No | Exports .joblib |

### ml-service / ml_core package

`ml_core/` is a private package within `ml-service/`. It is NOT shared with any other service.

```
ml_core/
├── __init__.py      # Re-exports all 7 submodules
├── models.py        # Model loading: spacy.load(), transformers.pipeline()
├── text.py          # normalize_text(), build_full_text(), summarize_text(), extract_keywords()
├── sentiment.py     # analyze_sentiment() → transformers pipeline → fallback to neutral
├── topic.py         # classify_topic() → keyword frequency scoring (war/cyber/economics/diplomacy)
├── entities.py      # extract_entities() → transformers NER → fallback to spaCy
├── threat.py        # score_threat() → keyword + sentiment + topic + entity count composite
└── relationships.py # infer_relationships() → pairwise keyword-based
```

**Key observations:**
- No overlap with ml-platform — different ML domains (NLP/text vs tabular/structured)
- Models are pre-trained — no training code, no registry
- The sentiment analysis is keyword-based at runtime (transformers fallback)
- `entities.py` imports `backend.shared.entity_normalization` — the only shared dependency

### ml-platform internal structure

```
ml-platform/
├── app.py                # FastAPI + lifespan (asyncpg pool + schema bootstrap)
├── db.py                 # Pool + ensure_schema() → ml_schema.sql
├── config.py             # ENERGY_SERVICE_URL, MLFLOW_TRACKING_URI, DVC_REMOTE
├── models.py             # Pydantic models for API
├── feature_store/        # registry.py, builders.py, transforms.py
├── datasets/             # builder.py, loader.py, splitter.py, versioning.py
├── training/             # trainer.py, models.py, experiment.py, optimization.py
├── inference/            # predictor.py (joblib load + cache + predict)
├── registry/             # model_registry.py (5-stage lifecycle)
├── evaluation/           # classification.py, regression.py, reporter.py
├── pipeline/             # preprocessing.py, selection.py, detection.py, explainability.py, reporting.py
├── routers/              # features.py, datasets.py, models.py, inference.py
└── tests/                # 7 test files, 49 tests
```

**Key observations:**
- `lightgbm` and `catboost` are optional (try/except imports)
- `mlflow`, `dvc`, `shap`, `optuna` are optional (try/except imports)
- `requirements.txt` is intentionally minimal for production inference
- Full ML stack is in `research/requirements-research.txt` — explicitly excluded from Docker

### research/organization

```
research/
├── notebooks/
│   ├── 01_eda.ipynb                # Exploratory data analysis
│   ├── 02_preprocessing.ipynb      # Data cleaning
│   ├── 03_feature_engineering.ipynb # Feature creation
│   ├── 04_baseline_models.ipynb     # LogReg, DecisionTree
│   ├── 05_model_comparison.ipynb    # RF, XGBoost, LightGBM
│   ├── 06_hyperparameter_tuning.ipynb # Grid/Random/Optuna
│   ├── 07_explainability.ipynb      # SHAP
│   └── 08_final_model_export.ipynb  # Export .joblib
├── datasets/fetch_data.py          # REST client for Energy Service + synthetic fallback
├── requirements-research.txt       # 15 packages (NEVER in Docker)
├── artifacts/ (empty)              # Intended for experiment outputs
├── experiments/ (empty)
├── models/ (empty)                 # Intended for exported .joblib
└── reports/ (empty)
```

### Responsibility Overlap Analysis

**ml-service vs ml-platform: NO OVERLAP.** Completely different domains (NLP vs tabular). Correctly separated.

**ml-platform vs research: CORRECT SEPARATION.** Research produces models; ml-platform consumes them. The dependency separation (two requirements.txt files) enforces this.

**ml_core vs shared: CORRECT ISOLATION.** ml_core is private to ml-service. It imports only `backend.shared.entity_normalization` for entity name normalization — a reasonable cross-cutting concern.

**database-service event correlation: POTENTIAL DRIFT.** The event correlation engine in `consumer.py` contains substantial business logic (scoring, clustering, alert generation) embedded in a persistence service. This would more appropriately live in a dedicated analytics service.

### Intended Runtime Lifecycle

```
ml-service:
  app.py (FastAPI REST API)     consumer.py (standalone Kafka consumer)
  ├── startup_event()           ├── load_models()
  │   └── load_models()         ├── start_kafka_consumer()
  └── serves: /health, /liveness,   └── poll loop: consume → enrich → produce
      /readiness, /version

ml-platform:
  app.py (FastAPI REST API)
  └── lifespan startup: get_pool() → ensure_schema()
  └── lazy model loading on first predict() call
  └── serves: features, datasets, models, predict endpoints

---

## PART 5 — Startup Lifecycle

| Service | Init Order | Database Init | Kafka Consumer | Models Loaded | Background Tasks |
|---------|-----------|---------------|----------------|---------------|------------------|
| **ingest-service** | 1. fetch_real_news() 2. start APScheduler | None | None | None | Scheduler (1h) |
| **ml-service app** | load_models() | None | None | spaCy + Transformers (eager) | None |
| **ml-service consumer** | load_models() → start_kafka_consumer() | None | raw_articles (group: ml-service-group) | spaCy + Transformers (duplicate) | Poll loop |
| **database-service app** | init_db_pool() | None (from init.sql) | None | None | None |
| **database-service consumer** | init_db_pool() → start_kafka_consumer() | None | processed_articles (group: db-service-group) | None | Poll loop + event correlation |
| **embedding-service app** | load model → asyncpg pool → ensure vector ext | Ensures vector ext | None | bge-small-en-v1.5 | None |
| **embedding-service consumer** | load model → asyncpg pool → start consumer() | Ensures vector ext | processed_articles (group: embedding-group) | bge-small-en-v1.5 (duplicate) | Poll loop |
| **energy-service** | get_pool() → bootstrap() → seed() | energy. schema (17 tables, 9 ENUMs) | None | None | None |
| **ml-platform** | get_pool() → ensure_schema() | ml. schema (4 tables, 4 ENUMs) | None | None (lazy) | None |
| **modular-api** | get_pg_pool() → get_es_client() | None (from init.sql) | None | None | None |

### Critical Observations

1. **Duplicate model loading**: ml-service and embedding-service load the same models TWICE (once in app.py, once in consumer.py). The consumer loads them because it is a separate process, but models could be loaded once and shared via IPC.

2. **No startup order enforcement**: There is no orchestration guaranteeing that infra starts before services. The startup scripts assume Docker infra is already running.

3. **Blocking startup**: ingest-service's `fetch_real_news()` call blocks the startup event — the service won't serve requests until the first news fetch completes (or fails).

4. **Dual schema initialization sources**: The `public.` schema is initialized from two sources: (a) `infra/sql/init.sql` mounted into PostgreSQL's docker-entrypoint-initdb.d, and (b) Alembic migrations in `backend/shared/migrations/`. These could drift.

5. **Energy/ml schemas are auto-bootstrapped on service startup**, which is correct for local dev. In production with persistent volumes, the bootstrap check is a no-op (sentinel table exists).

---

## PART 6 — Dependency Graph

### Service → Backend.Shared Import Matrix

| Service | config | logging | middleware | entity_norm | db_pool | es_client | kafka_monitor | schema_bootstrap |
|---------|--------|---------|------------|-------------|---------|-----------|---------------|------------------|
| ingest-service | SERVICE_VERSION | setup_structlog | RequestTracking | — | — | — | — | — |
| ml-service | SERVICE_VERSION | setup_structlog | RequestTracking | entities.py | — | — | — | — |
| database-service | SERVICE_VERSION | setup_structlog | RequestTracking | consumer.py | — | — | — | — |
| embedding-service | SERVICE_VERSION | setup_structlog | RequestTracking | — | — | — | — | — |
| energy-service | SERVICE_VERSION | setup_structlog | RequestTracking | — | — | — | — | bootstrap_schema |
| ml-platform | SERVICE_VERSION | setup_structlog | RequestTracking | — | — | — | — | — |
| modular-api | settings + SV | setup_structlog | RequestTracking | graph.py | get/close_pool | get/close_client | health.py | — |

### Infrastructure Dependencies

```
                     ┌─────────────────┐
                     │   PostgreSQL     │  port 5432
                     │  3 schemas:      │
                     │  public, energy, │
                     │  ml              │
                     └──┬───┬───┬───┬──┘
                        │   │   │   │
            ┌───────────┘   │   │   └───────────┐
            ▼               ▼   ▼               ▼
     database-service   energy  ml-platform  modular-api
     (psycopg2)         (asyncpg)(asyncpg)    (asyncpg)
     consumer.py        app.py   app.py       main.py

                     ┌─────────────────┐
                     │  Elasticsearch   │  port 9200
                     │  processed_      │
                     │  articles index  │
                     └──┬──────────┬───┘
                        │          │
                        ▼          ▼
                 database-service  modular-api
                 (es client)       (AsyncElasticsearch)

                     ┌─────────────────┐
                     │     Kafka       │  port 9092
                     │  raw_articles   │
                     │  processed_     │
                     │  articles       │
                     └──┬──┬──┬────┬───┘
                        │  │  │    │
              ┌─────────┘  │  │    └──────────┐
              ▼            ▼  ▼               ▼
       ingest-service  ml-service  database   embedding
       (producer)      (C+P)       -service    -service
                                    (C)         (C)

                     ┌─────────────────┐
                     │  GNews API      │  External
                     └────────┬────────┘
                              │
                              ▼
                       ingest-service
                       (requests HTTP)

                     ┌─────────────────┐
                     │  Energy Service  │  port 8006
                     │  REST API        │
                     └────────┬────────┘
                              │
                              ▼
                       ml-platform
                       (requests HTTP)
```

---

## PART 7 — Architectural Regressions

### 7.1 Responsibility Drift

**1. modular-api does too much.**
- It owns API gateway duties (auth, rate limiting, CORS) PLUS intelligence analytics, event management, watchlists, cases, reports, copilot, graph, search, and audit logging.
- The `IntelligenceRepository` at `1396 lines` contains data access for ~15 entity types across PostgreSQL and Elasticsearch.
- This is a monolith-in-microservice's-clothing. A true microservice decomposition would split this into separate services (auth-service, analytics-service, event-service, case-service, search-service).

**2. database-service does too much.**
- It owns persistence (PostgreSQL writes + Elasticsearch indexing) PLUS event correlation (scoring engine, alert generation).
- Event correlation is intelligence/analytics logic, not persistence logic.
- The consumer.py file is ~650+ lines with the `update_event_intelligence()` function containing the scoring algorithm.

**3. energy-service route ordering is broken.**
- `catalog.router` is included before `relationships`, `events`, `history`, `bulk` routers in `app.py`.
- Generic routes like `/{table}` and `/{table}/{entity_uuid}` shadow specific routes like `POST /events`, `GET /graph/network`, `POST /bulk/import`.
- This causes 5 API endpoints to be unreachable (they return 404).

### 7.2 Duplicate Logic

**1. Model loading duplicated.** `load_models()` in `ml_core/models.py` is called by both `app.py` and `consumer.py`. spaCy and Transformers models are loaded twice on the same machine.

**2. Database connections duplicated.** `init_db_pool()` (database-service), `get_pool()` (embedding-service asyncpg), and `get_pg_pool()` (modular-api backend.shared) all create PostgreSQL connection pools to the same database.

**3. Schema initialization duplicated.** The `public.` schema is initialized by `infra/sql/init.sql` (via PostgreSQL docker-entrypoint) AND by Alembic migrations (`0001_initial_schema.py`). Both define the same tables. If they drift, startup could fail.

**4. Consumer startup patterns identical.** All three consumer.py files follow the exact same pattern: signal handlers → init pool → start_kafka_consumer. Only the processing logic differs.

### 7.3 Missing Responsibilities

**1. No health check cascading.** If ml-service consumer crashes, database-service and embedding-service continue consuming stale data with no notification.

**2. No dead letter queue.** If ml-service fails to process a message (e.g., the JSON decode error we found), the message stays on the topic with lag forever. No DLQ, no retry, no poison message handling.

**3. No schema validation on Kafka messages.** Messages are JSON objects with no schema enforcement (no Avro, no Protobuf, no JSON Schema). Any producer can write any format to any topic.

**4. No auth on most services.** Only modular-api has authentication. Ingest, ml, database, embedding, energy, and ml-platform all have open endpoints.

**5. No frontend error handling.** All 20 pages use `.finally()` without `.catch()`. API failures produce silent hangs.

### 7.4 Incorrect Coupling

**1. database-service and modular-api share the same PostgreSQL `public.` schema AND Elasticsearch index.** They are tightly coupled by shared data stores — they must agree on schema, migrations, and index mappings. This violates microservice autonomy.

**2. embedding-service writes to the same schema (public.article_embeddings) that modular-api reads.** Three services write to the same schema: database-service, embedding-service, and modular-api (auth writes users table).

**3. ml-platform depends on energy-service REST API at runtime.** If energy-service is down, dataset building fails with no fallback or retry.

### 7.5 Dead or Unused Code

**1. TanStack Query is configured but unused.** `QueryClientProvider` wraps the app in `App.tsx`, but all 20 pages use raw `useEffect` + `useState` instead of `useQuery`.

**2. `infra/init.sql/` is an empty directory.** The actual init SQL is at `infra/sql/init.sql`.

**3. `research/models/`, `research/artifacts/`, `research/experiments/`, `research/reports/` are empty.** The intended workflow (notebook 08 → export .joblib → research/models/) has not been executed.

**4. `ml-platform/data/datasets/test_dataset/v1/` is empty.** The dataset builder has created the directory structure but no datasets have been built.

**5. `ml-platform/mlruns/` is empty.** No MLflow runs have been created.

**6. `services/frontend/package copy.json` is a residual file.** Likely a backup/copy during refactoring.

### 7.6 Startup Inconsistencies

**1. ingest-service blocks on first fetch.** `fetch_real_news()` in the startup event makes an HTTP request to GNews API. If this fails (network, quota), the service delays startup or fails entirely.

**2. ml-service and embedding-service load models at startup.** Large models (spaCy ~12MB, distilbert ~250MB, bge-small ~34MB) are loaded eagerly. If they fail, the service logs an error but continues with degraded functionality.

**3. No readiness gate.** There is no mechanism preventing the frontend or modular-api from querying a service that hasn't completed its startup sequence.

### 7.7 Hidden Dependencies

**1. Kafka hostname differs between compose files.** `docker-compose.yml` uses `PLAINTEXT://localhost:9092` for local dev. `docker-compose.full.yml` uses `PLAINTEXT://kafka:9092` for container networking. A misconfigured .env causes silent failures.

**2. `.env` vs `.env.example` hostnames differ.** `.env` uses `127.0.0.1`, `.env.example` uses Docker service names. Using the wrong file causes connection failures.

**3. Elasticsearch security enabled by default.** ES 8.11.0 starts with security enabled. The `.env` has `ELASTICSEARCH_PASSWORD=change-me`, but the database-service search endpoint crashes with 500 because ES requires authentication on the search endpoint.

---

## PART 8 — Final Architecture Report

### 1. Current Architecture

7 microservices + 4 infrastructure services, communicating via Kafka (pipeline) and REST (queries). PostgreSQL shared across 3 schemas (public by 3 services, energy by 1, ml by 1). Elasticsearch shared across database-service and modular-api. Frontend talks only to modular-api.

### 2. Intended Responsibilities (per CLAUDE.md + Docker Compose)

| Service | Intended Job |
|---------|-------------|
| ingest-service | Fetch news, publish to Kafka |
| ml-service | NLP enrichment (sentiment, NER, topic, threat) |
| database-service | Persist to PG + ES, serve article API |
| embedding-service | Generate + store vector embeddings |
| modular-api | Frontend gateway + intelligence API |
| energy-service | Energy infrastructure catalog |
| ml-platform | ML training + prediction platform |

### 3. Actual Responsibilities (as implemented)

| Service | Actually Does |
|---------|--------------|
| ingest-service | fetch + publish + scheduler |
| ml-service | NLP enrichment (Kafka consumer) |
| database-service | Persist + event correlation + alert generation + search API + analytics API + admin rebuild |
| embedding-service | Embeddings + semantic search API + backfill API |
| modular-api | Auth + analytics (8 endpoints) + search + entities + events + graph + watchlists + alerts + cases + reports + copilot + audit + rate limiting + Kafka monitoring |
| energy-service | CRUD + relationships + events + history + bulk import + seed data + network graph |
| ml-platform | Feature store + dataset builder + model training + registry + prediction |

### 4. Responsibility Drift

- **database-service** has drifted: it now owns event intelligence (scoring, clustering, alerting) — business logic that belongs elsewhere.
- **modular-api** has drifted: it is a monolith gateway handling 15+ domains. The original intent may have been for it to be a thin proxy.
- **energy-service route ordering drift**: the catalog router shadows specific routers, making 5 endpoints unreachable by mistake.
- **frontend** has drifted from its tech stack: TanStack Query configured but unused; no error handling despite being a production intelligence platform.

### 5. Service Interaction Diagram

```
                    GNews API
                        │
                    ingest-service
                        │ Kafka
                    ml-service
                   ┌────┴────┐
                   │ Kafka   │ Kafka
                   ▼         ▼
         embedding-service  database-service
                   │           ├── PostgreSQL
                   │           └── Elasticsearch
                   │                 │
                   └──modular-api────┘
                        │ HTTP
                   frontend

energy-service ←── PostgreSQL ──→ ml-platform
```

### 6. Startup Order

```
1. PostgreSQL ──→ Kafka ──→ Elasticsearch    (Docker Compose)
2. energy-service       (bootstraps energy schema + seed)
3. ml-platform          (bootstraps ml schema)
4. modular-api           (connects to PG + ES)
5. database-service      (connects to PG + ES + Kafka)
6. embedding-service     (connects to PG + Kafka + loads model)
7. ml-service            (loads models)
8. ingest-service        (fetches news + starts scheduler)
9. Consumers (in parallel):
   a. ml-service consumer    (consumes raw_articles → processes → produces processed_articles)
   b. database-service consumer (consumes processed_articles → persists → correlates)
   c. embedding-service consumer (consumes processed_articles → embeds → stores)
10. frontend              (starts Vite dev server)
```

**Note:** This order is NOT enforced anywhere. Services retry connections internally but there is no orchestration layer.

### 7. Runtime Data Flow

The primary runtime flow (Pipeline) is sequential and synchronous via Kafka:
```
GNews → ingest → [raw_articles] → ml-service → [processed_articles] → database-service + embedding-service → PG + ES → modular-api → frontend
```

The secondary flow (Energy → ML) is on-demand REST:
```
energy-service API → ml-platform → model training → prediction API
```

### 8. Technical Debt

**Critical:**
- ML consumer crashes on bad message (raise instead of continue)
- Elasticsearch search returns 500 (auth credentials missing)
- Energy service 5 endpoints shadowed by route ordering bug
- No frontend error handling on any page

**Medium:**
- Database-service and modular-api share PG + ES (no autonomy)
- Event correlation logic in persistence layer
- Duplicate model loading (app.py + consumer.py)
- No Kafka schema enforcement (JSON without Avro/Protobuf)
- No dead letter queue
- TanStack Query configured but unused (500+ lines of dead-ish config)
- Duplicate database connection pools to the same database
- Long-lived blocking startup in ingest-service

**Low:**
- Empty directories (research/models/, infra/init.sql/)
- Residual file (package copy.json)
- Empty dataset and MLflow directories
- Duplicate consumer processes (system Python + venv Python)

### 9. Questions That Must Be Answered Before Any Code Changes

1. **Should modular-api be decomposed?** It handles 15+ domains. Would splitting into auth-service, analytics-service, case-service, etc. improve maintainability?

2. **Should database-service own event correlation?** The scoring engine, clustering, and alert generation are business logic. Should they move to a dedicated service?

3. **Should database-service and modular-api share a database?** If these were truly autonomous microservices, they would not share PostgreSQL or Elasticsearch. Is the shared-schema approach intentional or an architectural compromise?

4. **Should Kafka topics use schemas?** The pipeline has no schema enforcement. Is Avro/Protobuf/JSON Schema planned, or is ad-hoc JSON acceptable?

5. **Should the energy-service shadowed endpoints be fixed with a route ordering change?** Or should the catalog router be redesigned to avoid path conflicts entirely?

6. **What is the intended relationship between research/ models and ml-platform?** The notebooks export to `research/models/` but ml-platform has its own training pipeline. Should ml-platform consume research exports, or should they remain independent?

7. **Should there be a dead letter queue?** The ML consumer crashes on bad messages. What should happen to unprocessable messages?

8. **Should model loading be deduplicated between app.py and consumer.py?** Is there a design reason for loading models twice (shared memory? container separation?), or is this an oversight?

9. **Is the frontend's lack of error handling intentional?** Was it deferred, or is this a known gap?

10. **Are the empty directories and files intentional stubs or technical debt?** (research/models/, research/artifacts/, ml-platform/data/datasets/, frontend/package copy.json)

```

```

