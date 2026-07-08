# ProxyDefence — Complete Architecture Reference

> **Author:** Principal Architecture Review  
> **Date:** 2026-07-06  
> **Version:** 1.0  
> **Scope:** Entire codebase audit

---

## Table of Contents

1. [Repository Overview](#1-repository-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Service-by-Service Documentation](#3-service-by-service-documentation)
4. [Request Flow](#4-request-flow)
5. [Data Flow](#5-data-flow)
6. [Database Documentation](#6-database-documentation)
7. [ML Platform Deep Dive](#7-ml-platform-deep-dive)
8. [Energy Service Deep Dive](#8-energy-service-deep-dive)
9. [AI Layer](#9-ai-layer)
10. [Research Platform](#10-research-platform)
11. [External Data Sources](#11-external-data-sources)
12. [End-to-End Sequence Diagrams](#12-end-to-end-sequence-diagrams)
13. [Current Project Status](#13-current-project-status)
14. [Architecture Assessment](#14-architecture-assessment)
15. [Future Work](#15-future-work)

---

## 1. Repository Overview

### 1.1 Complete Folder Tree

```
C:\ProxyWars\ProxyDefence\
│
├── .dockerignore
├── .editorconfig
├── .env                          # Live dev config (contains API keys)
├── .env.example                  # Template with placeholders
├── .gitignore
├── .pre-commit-config.yaml
├── CLAUDE.md                     # AI assistant guidance
├── Makefile                      # Dev workflow commands
├── README.md                     # Empty
├── alembic.ini                   # DB migration config
├── docker-compose.yml            # Infrastructure only (ZK, Kafka, ES, PG)
├── docker-compose.full.yml       # Full stack (all services + frontend)
├── openapi.json                  # API schema dump
├── package.json / package-lock.json
├── pyproject.toml                # Ruff, pytest, coverage, pyright, mypy
│
├── backend/
│   ├── api/                      # ACTUAL FastAPI application (47 files)
│   │   ├── app.py                # Main entry point
│   │   ├── agents/               # Supervisor + Intelligence agents
│   │   ├── tools/                # Tool framework (search, graph, energy, analytics)
│   │   ├── rag/                  # RAG engine (retriever, context, citations)
│   │   └── */router.py           # Domain routers (auth, articles, analytics, etc.)
│   │
│   ├── api_service/              # LEGACY — older version of API (27 files)
│   │   ├── main.py               # App entry (1 line)
│   │   └── routes/, services/, repositories/
│   │
│   └── shared/                   # SHARED LIBRARY (68 files)
│       ├── database/             # Pool, transactions, migrations
│       ├── kafka/                # Producer, consumer, topics, health
│       ├── llm/                  # Client, config, streaming, memory, prompts
│       ├── memory/               # Conversation, execution, agent memory, compression
│       ├── orchestration/        # Planner, engine, router, reasoning, reflection, confidence, citations, trace
│       ├── observability/        # Health builder, Prometheus metrics, startup timer
│       ├── prompts/              # System, planning, reflection, executive, validation prompts
│       ├── resilience/           # Retry, circuit breaker, timeout, bulkhead
│       └── migrations/           # Alembic (6 migrations)
│
├── datasets/                     # LOCAL DATASET FILES (not in Docker)
│   ├── raw/                      # Source data files by provider
│   ├── processed/                # Parsed/transformed outputs
│   └── registry/                 # Dataset registration records
│
├── docs/                         # Architecture & design documents
│
├── infra/
│   └── sql/                      # Canonical DDL files
│       ├── init.sql              # public schema (18+ tables)
│       ├── energy_schema.sql     # energy schema (9 ENUMs, 18 tables)
│       ├── ml_schema.sql         # ml schema (5 ENUMs, 37 tables)
│       ├── spr_schema.sql        # SPR tables
│       ├── procurement_schema.sql# Procurement tables
│       ├── energy_intelligence_schema.sql
│       └── digital_twin_schema.sql
│
├── research/                     # LOCAL RESEARCH ENVIRONMENT
│   ├── notebooks/                # 8 Jupyter notebooks
│   ├── datasets/                 # Fetched data
│   ├── models/                   # Exported .joblib files
│   └── experiments/              # MLflow experiment data
│
├── scripts/                      # 54 dev/ops scripts (.ps1 + .sh)
│   ├── dev/                      # Local dev orchestration
│   ├── maintenance/              # Clean, reset
│   └── testing/                  # Test runners
│
├── services/
│   ├── ingest-service/           # Port 8001 — News fetcher → Kafka
│   ├── ml-service/               # Port 8002 — NLP/sentiment → Kafka
│   ├── database-service/         # Port 8003 — Kafka → PostgreSQL + ES
│   ├── embedding-service/        # Port 8005 — Embeddings → PostgreSQL
│   ├── energy-service/           # Port 8006 — Energy catalog + intelligence
│   ├── ml-platform/              # Port 8007 — ML training + inference
│   ├── modular-api/              # Port 8000 — FastAPI gateway (shared)
│   └── frontend/                 # Port 8080 — React SPA
│
└── tests/                        # INTEGRATION & UNIT TESTS
    ├── unit/                     # Per-service unit tests
    ├── integration/              # Cross-service integration tests
    └── fixtures/                 # Test data factories
```

### 1.2 Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18.3, TypeScript 5.8, Vite 5.4, Tailwind 3.4, shadcn/ui (Radix) |
| **Backend API** | Python 3.11, FastAPI, uvicorn |
| **ML Platform** | Python 3.11, scikit-learn, XGBoost, LightGBM, joblib |
| **AI/LLM** | OpenAI-compatible API (Groq), Llama 3.3 70B, tiktoken |
| **Streaming** | Apache Kafka 7.4 (Confluent), Kafka topics auto-created |
| **Database** | PostgreSQL 15 (pgvector), pgvector for embeddings |
| **Search** | Elasticsearch 8.11 (security enabled, single-node) |
| **Observability** | Prometheus (+fastapi-instrumentator), structlog, Grafana (future) |
| **Vector Store** | pgvector (HNSW index, cosine distance, 384d embeddings) |
| **Container** | Docker Compose, Dockerfile per service |
| **CI** | Pre-commit hooks (ruff, trailing-whitespace, check-yaml) |
| **Auth** | JWT (python-jose), Supabase (frontend optional) |
| **Experiment Tracking** | MLflow (file-based) |
| **Data Versioning** | DVC (local store) |

### 1.3 Service Port Map

| Service | Port | Protocol | Docker Service Name |
|---|---|---|---|
| Modular API (Gateway) | 8000 | HTTP | `modular-api` |
| Ingest Service | 8001 | HTTP | `ingest-service` |
| ML Service | 8002 | HTTP | `ml-service` |
| Database Service | 8003 | HTTP | `database-service` |
| Embedding Service | 8005 | HTTP | `embedding-service` |
| Energy Service | 8006 | HTTP | `energy-service` |
| ML Platform | 8007 | HTTP | `ml-platform` |
| Frontend (Vite dev) | 8080 | HTTP | `frontend` |
| Kafka | 9092 | TCP | `kafka` |
| PostgreSQL | 5432 | TCP | `postgres` |
| Elasticsearch | 9200 | HTTP | `elasticsearch` |

### 1.4 Environment Variables

| Variable | Default | Used By |
|---|---|---|
| `POSTGRES_HOST` | `postgres` | All backend services |
| `POSTGRES_DB` | `defenseintel` | All backend services |
| `POSTGRES_USER` | `admin` | All backend services |
| `POSTGRES_PASSWORD` | *(required)* | All backend services |
| `ELASTICSEARCH_HOST` | `elasticsearch` | database-service, modular-api |
| `ELASTICSEARCH_PASSWORD` | *(required)* | database-service, modular-api |
| `ELASTIC_PASSWORD` | *(required)* | docker-compose |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | ingest-service, ml-service, database-service, embedding-service |
| `JWT_SECRET_KEY` | *(required)* | modular-api, database-service |
| `JWT_ALGORITHM` | `HS256` | modular-api, database-service |
| `CORS_ORIGINS` | `http://localhost:3000,...` | modular-api |
| `OPENAI_API_KEY` | *(required)* | modular-api (LLM) |
| `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` | modular-api (LLM) |
| `LLM_DEFAULT_MODEL` | `llama-3.3-70b-versatile` | modular-api |
| `LLM_FALLBACK_MODEL` | `llama-3.1-8b-instant` | modular-api |
| `NEWS_API_KEY` | *(required)* | ingest-service |
| `ENERGY_LOAD_SEED` | `0` | energy-service |
| `ENERGY_SERVICE_URL` | `http://energy-service:8000` | ml-platform |
| `MLFLOW_TRACKING_URI` | `file:./mlruns` | ml-platform |
| `DVC_REMOTE` | `./data/dvc-store` | ml-platform |
| `VITE_API_URL` | `http://localhost:8000` | frontend (build arg) |
| `SERVICE_VERSION` | `1.0.0` | All services |
| `LOG_LEVEL` | `INFO` | All services |

### 1.5 Build & Deployment

**Local Development:**
```powershell
# Full setup (one time)
scripts/dev/setup/setup.ps1

# Start infrastructure (Docker)
scripts/dev/infrastructure/start-infra.ps1

# Start all services
scripts/dev/start-local.ps1              # Orchestrates everything
# -- or individually --
scripts/dev/backend/start-ingest.ps1      # One service per terminal
scripts/dev/backend/start-all.ps1         # All services in separate windows
```

**Production Deployment:**
```bash
docker compose -f docker-compose.full.yml up --build -d
```

**Testing:**
```bash
make test                    # pytest with coverage
make test-unit               # Unit tests only
make test-integration        # Integration tests only
pytest services/ml-platform/tests/  # ML Platform tests
```

---

## 2. High-Level Architecture

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React SPA)                              │
│                    Port 8080 (Vite dev) / 3000 (Docker)                    │
│                                                                             │
│  Pages: Dashboard, Analytics, Copilot, DigitalTwin, Procurement, SPR,      │
│         Risk, Events, Entities, Graph, Alerts, Watchlists, Cases, Reports  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ HTTP (Axios, JWT Bearer)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODULAR API (FastAPI Gateway)                            │
│                              Port 8000                                      │
│                                                                             │
│  Routes: /auth, /articles, /analytics, /events, /entities, /search,        │
│          /graph, /alerts, /watchlists, /cases, /reports, /copilot,          │
│          /rag, /health                                                      │
│                                                                             │
│  AI Layer: Supervisor Agent ─→ Intelligence Agent ─→ Tools                 │
│            Planning Engine ─→ Reasoning Loop ─→ Reflection ─→ Confidence    │
│            RAG Engine ─→ Hybrid (Vector + Keyword + Graph) ─→ Citations    │
│                                                                             │
│  Proxies: /api/v1/energy/* → energy-service:8006                           │
│           /api/v1/intelligence/* → energy-service:8006                     │
│           /api/v1/intelligence/digital-twin/* → energy-service:8006        │
│           /api/v1/intelligence/procurement/* → energy-service:8006         │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │          │          │
       │          │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼          ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Ingest  │ │  ML     │ │Database │ │Embedding │ │  Energy  │ │    ML    │
│ Service │ │ Service │ │ Service │ │ Service  │ │ Service  │ │ Platform │
│  8001   │ │  8002   │ │  8003   │ │  8005    │ │  8006    │ │  8007    │
└────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │           │           │           │            │            │
     │           │           │           │            │            │
     ▼           ▼           ▼           ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KAFKA EVENT BUS                                      │
│  Topics: raw_articles, processed_articles, commodity_prices, ais_signals,   │
│          sanctions_updates, disruption_signals, intelligence_alerts         │
└─────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                              │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │   PostgreSQL 15   │  │  Elasticsearch 8 │  │      pgvector            │  │
│  │   (pgvector)      │  │  (full-text)     │  │  (384d HNSW index)      │  │
│  │                   │  │                  │  │                          │  │
│  │ public schema     │  │ processed_       │  │ article_embeddings      │  │
│  │ energy schema     │  │ articles index   │  │ embedding vector        │  │
│  │ ml schema         │  │                  │  │                          │  │
│  │ spr schema        │  │                  │  │                          │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Responsibilities

| Service | Primary Responsibility | Data Owned |
|---|---|---|
| **Ingest Service** | Fetch news from GNews API, produce to `raw_articles` Kafka topic | None (ephemeral producer) |
| **ML Service** | Consume `raw_articles`, perform NLP (sentiment, entities), produce to `processed_articles` | None (ephemeral transformer) |
| **Database Service** | Consume `processed_articles`, persist to PostgreSQL + Elasticsearch. Event intelligence clustering. Energy enrichment. REST API for articles/analytics/search. | PostgreSQL `public` schema (articles, events, entities, relationships, entity_profiles) |
| **Embedding Service** | Consume `processed_articles`, generate vector embeddings, store in pgvector | PostgreSQL `public.article_embeddings` (384d vectors) |
| **Energy Service** | Authoritative infrastructure catalog. Risk scoring engine. Digital Twin simulation. Procurement orchestration. SPR optimization. | PostgreSQL `energy.*` schema, `spr.*`, `procurement.*`, `digital_twin.*`, `energy_intelligence.*` |
| **Modular API** | Frontend gateway. Authentication. AI Copilot (Supervisor Agent, Intelligence Agent, Tool framework, RAG). API proxy to energy-service. | None (stateless gateway) |
| **ML Platform** | Dataset registry, feature store, model training, experiment tracking, model registry, data acquisition (GDELT parser pipeline) | PostgreSQL `ml.*` schema, local data lake (`datasets/`) |
| **Frontend** | SPA UI for all intelligence capabilities | None (stateless client) |

### 2.3 Kafka Topics

| Topic | Partitions | Producer | Consumer | Schema |
|---|---|---|---|---|
| `raw_articles` | 3 | ingest-service | ml-service | `{id, title, content, source, published_at, url, image}` |
| `processed_articles` | 3 | ml-service | database-service, embedding-service | `{id, title, content, source, published_at, ml_processed, confidence, sentiment, url, image, summary, topic, threat_score, geopolitical_risk, risk_level, entities, relationships, content_hash, dedupe_key}` |
| `commodity_prices` | 3 | energy-service | (future) | `{commodity, price, date, unit, market}` |
| `ais_signals` | 3 | energy-service | (future) | `{mmsi, lat, lon, speed, course, timestamp}` |
| `sanctions_updates` | 2 | energy-service | (future) | `{entity, program, date, action}` |
| `disruption_signals` | 3 | energy-service | (future) | `{title, severity, dimension, entity, description}` |
| `intelligence_alerts` | 2 | energy-service | (future) | `{type, message, severity, entity_id}` |

---

## 3. Service-by-Service Documentation

### 3.1 Ingest Service (`services/ingest-service/`, port 8001)

**Purpose:** Fetch news articles from GNews API and publish to Kafka.

**Dependencies:** Kafka, GNews API
**Implementation Status:** ✅ Complete — 4 files, 162 lines total

**Files:**
- `app.py` — FastAPI entry, APScheduler for hourly fetch, 6 health endpoints, 1 trigger endpoint
- `config.py` — NEWS_API_KEY from env
- `producer.py` — JsonProducer singleton
- `services/news_fetcher.py` — Fetch from GNews, hash-based dedup ID, produce to `raw_articles`

**API Routes:**
| Method | Path | Description |
|---|---|---|
| GET | `/` | Root with scheduler status |
| GET | `/health` | Kafka health check |
| GET | `/fetch-real-news` | Trigger news fetch |

**Kafka Producer:** `raw_articles` topic, JSON-serialized, hash-based article_id

### 3.2 ML Service (`services/ml-service/`, port 8002)

**Purpose:** Consume `raw_articles`, perform NLP sentiment analysis + entity extraction, produce `processed_articles`.

**Dependencies:** Kafka, spaCy (`en_core_web_sm`)
**Implementation Status:** ✅ Complete — `app.py`, `consumer.py`, `ml_core/`

**Consumer Pipeline:**
1. Consume from `raw_articles`
2. **Sentiment analysis** — keyword-based (negative/positive/neutral word lists)
3. **Entity extraction** — spaCy NER
4. **Topic classification** — keyword-based (conflict/energy/political/economic/technology/cyber)
5. **Threat scoring** — weighted keyword presence
6. **Relationship extraction** — co-occurrence patterns
7. Produce to `processed_articles`

**Consumer Groups:** `ml-service-group` on `raw_articles`

### 3.3 Database Service (`services/database-service/`, port 8003)

**Purpose:** Consume `processed_articles`, persist to PostgreSQL + Elasticsearch, provide REST API for articles/analytics/search.

**Dependencies:** Kafka, PostgreSQL, Elasticsearch
**Implementation Status:** ✅ Complete (sync psycopg2, not asyncpg)

**Consumer Pipeline (per message):**
1. `upsert_article()` — INSERT/UPDATE `processed_articles` (dedupe by `dedupe_key`)
2. `replace_related_records()` — Replace `extracted_entities`, `article_sentiments`, `relationships`
3. `update_event_intelligence()` — Cluster articles into events (entity overlap + topic + time + semantic similarity), update `entity_profiles`, generate watchlist alerts
4. `enrich_energy_context()` — Link article NER entities to `energy.*` assets via exact/partial name matching, build enrichment JSONB
5. `index_article()` — Index document in Elasticsearch

**API Routes:**
| Method | Path | Description |
|---|---|---|
| GET | `/api/articles` | Paginated articles, optional sentiment filter |
| GET | `/api/articles/{id}` | Single article by ID |
| GET | `/api/analytics/summary` | Total articles, 24h count, avg confidence/threat, sentiment distribution |
| GET | `/api/search` | Elasticsearch multi_match (title^3, summary^2, content, source, topic) |
| POST | `/rebuild-events` | Admin: delete all events/clusters and rebuild from scratch |

**Database:** psycopg2 (sync), SimpleConnectionPool (5-20), raw SQL, no ORM

### 3.4 Embedding Service (`services/embedding-service/`, port 8005)

**Purpose:** Consume `processed_articles`, generate vector embeddings, store in pgvector.

**Dependencies:** Kafka, PostgreSQL (pgvector extension)
**Implementation Status:** ⚠️ Partial — consumer exists, app.py exists, embedding model not verified

**Consumer Pipeline:**
1. Consume from `processed_articles`
2. Generate embedding for article content
3. Store in `article_embeddings` table with HNSW index

### 3.5 Energy Service (`services/energy-service/`, port 8006)

**Purpose:** Authoritative infrastructure catalog + risk intelligence + digital twin + procurement orchestration + SPR optimization.

**Dependencies:** PostgreSQL
**Implementation Status:** ✅ Complete — 33 files, 6,728 lines, 150+ API endpoints

**Key Modules:**
- **Catalog** — CRUD for 14 entity types (locations through suppliers), bulk import (JSON/CSV/GeoJSON), export
- **Relationships** — Entity relationship graph with type-based edges
- **Events** — Infrastructure events with severity
- **History** — Capacity history time-series
- **Risk Engine** — `RiskScoringEngine`, `SignalDetector`, `DataIngestor` with 3 ingestor implementations (commodity_prices, sanctions, ais)
- **ML Bridge** — `MLBridge` for ML Platform prediction with rule-based fallback, `RiskPropagator` (0.3 propagation factor)
- **Digital Twin** — `SimulationEngine` (tick-based), `NetworkGraph` (BFS path, dependency traversal), `FlowEngine` (capacity-constrained flow simulation, disruption rebalancing, aggregate impacts), 10 scenario templates
- **Procurement** — `SupplierIntelligence` (enrich, score, alternatives), `RefineryCompatibility` (API gravity/sulfur matching), `ProcurementOptimizer` (Pareto frontier, multi-goal), `ProcurementOrchestrator` (end-to-end run, executive cards, RFQ output)
- **SPR** — `SPREngine` (facility management, inventory tracking, release optimization, decision timeline, 5 strategies: conservative/aggressive/economic/strategic/balanced)

### 3.6 Modular API (`services/modular-api/`, port 8000)

**Purpose:** Frontend gateway, authentication, AI Copilot, API proxy.

**Dependencies:** PostgreSQL, Elasticsearch, Energy Service
**Implementation Status:** ✅ Complete — 47 files

**Files:**
- `backend/api/app.py` — FastAPI with lifespan, CORS, health, all routers
- `backend/api/auth/` — JWT login/register/me
- `backend/api/articles/` — Article CRUD
- `backend/api/analytics/` — Dashboard stats, threat trends, time-series, topic breakdown
- `backend/api/alerts/` — Alert CRUD + generate
- `backend/api/entities/` — Entity profiles
- `backend/api/events/` — Event cluster CRUD
- `backend/api/search/` — Full-text search
- `backend/api/graph/` — Network graph
- `backend/api/watchlists/` — Watchlist CRUD + entities
- `backend/api/cases/` — Investigation case CRUD + notes + items
- `backend/api/reports/` — Report generation
- `backend/api/copilot/` — AI Copilot query (sync + streaming SSE)
- `backend/api/rag/` — RAG retrieval router
- `backend/api/agents/` — Supervisor Agent, Intelligence Agent
- `backend/api/tools/` — 5 tool modules (search, intelligence, graph, analytics, energy)
- `backend/api/energy/` — Proxy router to energy-service:8006
- `backend/api/health/` — Health checks

### 3.7 ML Platform (`services/ml-platform/`, port 8007)

(See [Section 7 — ML Platform Deep Dive](#7-ml-platform-deep-dive))

### 3.8 Frontend (`services/frontend/`, port 8080)

**Purpose:** React SPA for intelligence platform.

**Implementation Status:** ✅ Complete — 30+ pages, 50+ UI components

**Key Pages (32 total):**
| Page | Description |
|---|---|
| `Landing` | Hero, metrics, recent articles |
| `Dashboard` | 8 KPI cards, charts, threat map, recent events |
| `Copilot` | AI chat with energy impact context |
| `DigitalTwin` | 5-tab simulation interface |
| `Procurement` | 5-tab procurement orchestrator |
| `SPR` | 5-tab SPR decision intelligence |
| `RiskDashboard` | Risk scoring, signals, ingestor triggers |
| `EnergyMap` | SVG world map with 10 asset layers |
| `GraphExplorer` | Cytoscape interactive graph |

---

## 4. Request Flow

### 4.1 Copilot Question

```
User types question in Copilot UI
    │
    ▼
Frontend: POST /copilot/query/stream (SSE)
    │
    ▼
Modular API: copilot/router.py
    │
    ├── Authenticate JWT
    │
    ▼
Supervisor Agent (/api/agents/supervisor.py)
    │
    ├── Create conversation memory
    ├── Call LLM (Llama 3.3 70B) to analyze query
    ├── Determine required tools/agents
    │
    ▼
Planner (backend/shared/orchestration/planner.py)
    │
    ├── LLM generates ExecutionPlan
    │   └── Steps: [{agent, task, tools, mode}]
    │
    ▼
Execution Engine (backend/shared/orchestration/engine.py)
    │
    ├── Route to Intelligence Agent
    ├── Intelligence Agent executes tools:
    │   ├── search_tools.py → Elasticsearch full-text
    │   ├── intelligence_tools.py → Risk scores, signals
    │   ├── graph_tools.py → Knowledge graph queries
    │   ├── analytics_tools.py → Statistics, trends
    │   └── energy_tools.py → Energy service API (digital twin, procurement, SPR)
    │
    ├── Reasoning Loop (max 5 iterations: Thought→Tool→Observation→Reflection)
    ├── Reflection Engine — evaluates evidence sufficiency
    │   └── If "gather_more": expand plan, re-route
    │
    ├── Confidence Engine — multi-factor scoring
    │   └── tool_reliability(20%) + evidence_count(15%) + source_agreement(20%)
    │       + kg_support(10%) + rag_score(10%) + llm_eval(10%) + contradictions(15%)
    │
    ├── Citation Engine — collect + deduplicate citations
    │
    ▼
RAG Engine (/api/rag/)
    │
    ├── Retriever: Hybrid search
    │   ├── Vector search (pgvector cosine)
    │   └── Keyword search (Elasticsearch)
    │
    ├── Context Builder: Token-limited context trimming
    ├── Citation Builder: Article/entity/simulation citations
    │
    ▼
LLM Call (final synthesis)
    │
    ├── Response with citations
    ├── Confidence score
    ├── Suggested actions
    └── Follow-up questions
    │
    ▼
StreamingHandler sends SSE events to frontend
    │
    ▼
Frontend renders Copilot response with EnergyImpactCard
```

### 4.2 News Ingestion Pipeline

```
GNews API
    │ HTTP GET (query: "world news" OR "conflict" OR "war")
    ▼
Ingest Service (/fetch-real-news)
    │
    ├── Fetch articles from GNews
    ├── Hash URL → article_id (SHA256 mod 10^8)
    ├── Build news_data dict
    │
    ▼ Kafka
    raw_articles topic (partition by key)
    │
    ▼
ML Service Consumer (ml-service-group)
    │
    ├── spaCy NER → entities[]
    ├── Keyword sentiment → positive/negative/neutral
    ├── Keyword topic → conflict/energy/political/economic/technology/cyber
    ├── Keyword threat_score → 0-100
    ├── Relationship extraction → relationships[]
    ├── Build processed_articles message (21 fields)
    │
    ▼ Kafka
    processed_articles topic (partition by key)
    │
    ├───→ Database Service Consumer (db-service-group)
    │       │
    │       ├── upsert_article() → PostgreSQL processed_articles
    │       ├── replace_related_records()
    │       │   ├── extracted_entities
    │       │   ├── article_sentiments
    │       │   └── relationships
    │       │
    │       ├── update_event_intelligence()
    │       │   ├── Find matching event (entity overlap + topic + time)
    │       │   │   └── threshold ≥ 0.6 → link; else create new
    │       │   ├── Update event rollup (article_count, risk_score, confidence)
    │       │   ├── Update entity_profiles (mention_frequency, risk_trend)
    │       │   └── Generate watchlist alerts (if threat_score ≥ 55)
    │       │
    │       ├── enrich_energy_context()
    │       │   ├── Match entities against energy.* tables
    │       │   │   └── exact match → partial match (LIKE %text%)
    │       │   ├── Build enrichment JSONB (locations, infrastructure, orgs, commodities)
    │       │   └── Store in article_energy_enrichments
    │       │
    │       └── index_article() → Elasticsearch processed_articles index
    │
    └───→ Embedding Service Consumer (embedding-service-group)
                │
                ├── Generate embedding (model TBD)
                └── Store in article_embeddings (384d HNSW)
```

### 4.3 Model Inference Request

```
Client (Frontend / ML Platform)
    │ POST /api/v1/ml/predict
    ▼
ML Platform (port 8007)
    │
    ├── Load model from Model Registry (ml.model_versions)
    ├── Load feature definitions (ml.feature_definitions)
    ├── Compute features (Feature Pipeline or pre-computed vectors)
    ├── Load feature vectors (ml.feature_vectors)
    │
    ├── predictor.py
    │   ├── Load serialized model (joblib)
    │   ├── Preprocess input (scaling, encoding)
    │   ├── Run inference
    │   └── Format response (prediction + confidence + probabilities + latency)
    │
    ├── Store prediction in ml.predictions
    └── Return PredictionResponse
```

### 4.4 Digital Twin Simulation

```
Frontend: DigitalTwin page
    │ POST /api/v1/intelligence/digital-twin/run
    ▼
Energy Service: digital_twin router
    │
    ├── Load scenario or use raw config
    ├── Create digital_twin_runs record
    ├── Snapshot current network state (network_nodes + network_edges)
    │
    ▼
SimulationEngine.run_simulation()
    │
    ├── Estimate baseline flow (75% of max capacity per edge)
    │
    ├── For each tick (default 90 iterations):
    │   ├── FlowEngine.compute_tick()
    │   │   ├── Compute edge disruptions from scenario config
    │   │   ├── Apply risk modifiers from risk_snapshot
    │   │   ├── Rebalance flow through alternative paths
    │   │   ├── Update node states (inbound, outbound, inventory, supply_gap)
    │   │   └── Generate events for supply_deficit / supply_stress / node_idle
    │   │
    │   ├── _persist_tick_state() → flow_states for nodes + edges
    │   └── _persist_tick_event() → simulation_tick_events
    │
    ├── compute_aggregate_impacts()
    │   └── supply_gap, idle_refineries, capacity_lost, economic_impact, gdp_impact
    │
    └── Update run with results
    │
    ▼
Return simulation results to frontend
    │
    Frontend renders:
    ├── Overview tab: run results, timeline chart
    ├── Scenarios tab: template or custom scenario config
    ├── Results tab: aggregate impacts, supply gap timeline
    ├── Network tab: flow states per node/edge at selected tick
    └── Impacts tab: economic impact breakdown
```

### 4.5 Procurement Optimization

```
Frontend: Procurement page
    │ POST /api/v1/intelligence/procurement/run
    ▼
Energy Service: ProcurementOrchestrator.run_procurement()
    │
    ├── Get simulation results (if linked to digital twin run)
    ├── Create procurement_run record
    ├── Store procurement_assumptions (goals, constraints)
    │
    ├── Get qualified suppliers (filter: sanctions, lead_time)
    │
    ├── For each supplier-commodity pair:
    │   ├── Compute cost_bbl = base + transport + risk_insurance + tariff + premium
    │   ├── Compute risk_score = 1 - (reliability*0.5 + stability*0.3 + on_time*0.2)
    │   ├── Compute composite = cost_score*0.35 + risk*0.30 + lead_time*0.20 + strategic*0.15
    │   └── Build option record
    │
    ├── Compute Pareto frontier (non-dominated options across cost/risk/lead_time)
    ├── Select recommended option (min cost / min risk / min lead / max composite)
    │
    ├── Create procurement_recommendations (per supplier)
    ├── Generate executive_cards (2-4 cards: supply gap, recommended strategy, Pareto, residual risk)
    └── Generate executive summary text
    │
    ▼
Return run results to frontend
    │
    Frontend renders:
    ├── Overview tab: run status, recommendations, executive cards
    ├── Suppliers tab: intelligence profiles, scores
    ├── Compatibility tab: refinery-crude pairings
    ├── Optimization tab: optimizer parameters, Pareto frontier
    └── Executive tab: recommendation cards with acknowledge button
```

### 4.6 SPR Optimization

```
Frontend: SPR page
    │ POST /api/v1/intelligence/procurement/spr/analyze
    ▼
Energy Service: SPREngine.run_optimization()
    │
    ├── Compute releasable inventory per facility
    ├── Compute daily draw rate
    ├── Compute days_until_depletion
    ├── Compute supply gap analysis
    │
    ├── Generate release plan per facility
    │   └── Strategy-based reserve factor:
    │       conservative(50%), aggressive(10%), economic(15%),
    │       strategic(60%), balanced(30%)
    │
    ├── Build decision timeline:
    │   ├── Now → +24h → +72h → +7d → +30d
    │   └── Each phase has actions
    │
    ├── Build executive recommendations:
    │   ├── release_card
    │   ├── procurement_card
    │   ├── refill_card
    │   └── policy_card
    │
    └── Persist: release_runs, release_plans, refill_plans, recommendations,
        decision_timeline, cost_analysis, assumptions
    │
    ▼
Return run results to frontend
    │
    Frontend renders:
    ├── Dashboard tab: facility status, KPIs
    ├── Facilities tab: capacity, inventory, releases
    ├── Release Planner tab: disruption config, duration, strategy, results
    ├── Timeline tab: decision phases with actions
    └── Decision Cards tab: recommendation cards with acknowledge
```

---

## 5. Data Flow

### 5.1 GDELT Data Pipeline

```
GDELT Master File List (data.gdeltproject.org/gdeltv2/masterfilelist.txt)
    │ HTTP GET → 1,174,880 entries
    ▼
MasterFileReader
    │ Parse: TIMESTAMP MD5 URL → Record
    │ Extract date from URL (/20240101*/)
    │ Group by type (events/mentions/gkg)
    ▼
GDELTFilter
    │ Apply FilterConfig(start_date, end_date, dataset_types)
    ▼
GDELTDownloader (concurrent, semaphore-limited)
    │
    ├── HEAD request → size + accept-ranges
    ├── Compare with local file (skip if complete)
    ├── aiohttp GET with Range header (resume)
    ├── Write to datasets/raw/gdelt/{type}/{version}/
    └── MD5 checksum verification against master file list
    ▼
GDELTParser
    │
    ├── Extract ZIP → CSV (TSV files)
    ├── Map 61-column events / 16-column mentions / 27-column GKG
    ├── Validate against canonical schema
    ├── Compute confidence scores
    └── Write to datasets/processed/gdelt/{type}/{version}/*.csv
    ▼
GDELTRegistration
    │
    ├── Load CSV → DataFrame
    ├── Compute statistics (row_count, column_count, missing)
    ├── Generate profile (per-column: mean, std, min, max, skew, entropy)
    ├── Compute checksum (SHA-256)
    ├── Register in DatasetCatalog (ml.dataset_catalog)
    └── Generate manifest YAML
    ▼
GDELTValidator
    │
    ├── validate_download: file_exists, not_empty, zip_valid, md5_match
    ├── validate_parsed_csv: csv_exists, canonical_fields, has_records
    └── validate_registration: status, statistics
    ▼
Research Dataset (future transformation pipeline)
    ├── Normalized Canonical Records
    ├── Feature Engineering
    └── Dataset Builder → train/val/test splits
```

### 5.2 Energy Intelligence Data Flow

```
External Data (simulated/real)
    │
    ├── Commodity Prices (10 benchmarks)
    │   └── DataIngestor → energy.commodity_prices
    │       └── SignalDetector → energy.disruption_signals (>5% change)
    │
    ├── Sanctions (10 countries)
    │   └── DataIngestor → energy.sanctions
    │       └── SignalDetector → geopolitical signals
    │
    ├── AIS / Port Congestion (15 ports, 8 chokepoints)
    │   └── DataIngestor → energy.port_congestion + energy.ais_positions + energy.tanker_availability
    │       └── SignalDetector → operational signals (>70% congestion)
    │
    ▼
RiskScoringEngine
    │
    ├── 15 built-in RiskFactors (chokepoint_blockage, sanctions_impact, ...)
    ├── score_entity(entity_uuid, entity_type, dimension)
    │   ├── Severity * confidence from active signals
    │   ├── Weighted factor contributions
    │   └── Normalized to 0-1
    │
    ├── persist_score() → energy.risk_scores (24h TTL)
    │
    └── score_and_persist() → all dimensions for an entity
    │
    ▼
MLBridge
    │
    ├── ml_platform.predict_disruption_risk() → POST /predict
    ├── Fallback: rule-based weighted scoring (5 dimensions)
    └── RiskPropagator (0.3 factor to related entities)
    │
    ▼
Energy Intelligence API (frontend-facing)
    ├── Risk dashboard (active signals, avg risk, by dimension)
    ├── Entity risk profile (scores + signals + related risks)
    ├── Scenario evaluation (what-if config → risk assessment)
    └── Risk propagation map (source → propagated scores)
```

### 5.3 Article-to-Event Intelligence Flow

```
Processed Article (from Kafka)
    │
    ▼
update_event_intelligence(article_db_id)
    │
    ├── Fetch article + extracted_entities
    │
    ├── Find best matching existing event (within 72 hours):
    │   ├── entity_overlap(60%) + topic_match(15%) + time_proximity(15%) + semantic_similarity(10%)
    │   └── threshold: 0.60
    │
    ├── Link to existing event OR create new event
    │
    ├── Update event_entities (merge/update mentions)
    │
    ├── Recalculate event rollup:
    │   ├── article_count = COUNT(*)
    │   ├── risk_score = AVG(threat_score)
    │   ├── risk_level = f(risk_score) → critical/high/medium/low
    │   ├── confidence = AVG(confidence)
    │   ├── first_seen = MIN(published_at)
    │   └── last_seen = MAX(published_at)
    │
    ├── Update entity_profiles:
    │   ├── mention_frequency += 1
    │   ├── risk_trend = latest threat_score
    │   ├── associated_events = all event IDs
    │   └── associated_relationships = all relationship IDs
    │
    └── Generate watchlist alerts (if threat_score ≥ 55):
        ├── Match against watchlist_entities
        └── INSERT INTO alerts (watchlist_id, entity_text, event_id, alert_type, risk_score)
```

---

## 6. Database Documentation

### 6.1 PostgreSQL — `public` Schema

**Init file:** `infra/sql/init.sql` (287 lines)

| Table | Purpose | R | W | Key Columns |
|---|---|---|---|---|
| `users` | User accounts | modular-api | modular-api | id, username, email, password_hash, role, is_active |
| `processed_articles` | Core article store | database-service, modular-api | database-service | id(serial), article_id, title, content, source, published_at, ml_processed, confidence, sentiment, threat_score, geopolitical_risk, risk_level, content_hash, dedupe_key(UNIQUE) |
| `extracted_entities` | NER entities per article | modular-api | database-service | article_id(FK), entity_text, entity_type, confidence |
| `article_sentiments` | Sentiment per article | modular-api | database-service | article_id(FK), sentiment_label, sentiment_score |
| `relationships` | Entity-entity relationships | modular-api | database-service | article_id(FK), source_entity, target_entity, relationship_type, confidence, evidence, context |
| `events` | Event clusters | modular-api | database-service | id, title, summary, topic, risk_score, risk_level, confidence, first_seen, last_seen, article_count, cluster_key |
| `event_articles` | Event-article mapping | modular-api | database-service | event_id(FK), article_id(FK), similarity_score |
| `event_entities` | Event entity aggregation | modular-api | database-service | event_id(FK), entity_text, entity_type, mention_count, avg_confidence |
| `entity_profiles` | Entity intelligence profiles | modular-api | database-service | entity_text(PK), entity_type, aliases, mention_frequency, risk_trend, associated_events, associated_relationships, last_seen |
| `reports` | Generated intelligence reports | modular-api | modular-api | id, title, type, summary, content, created_by, case_id |
| `watchlists` | User watchlists | modular-api | modular-api | id, name, description, created_by |
| `watchlist_entities` | Watchlist members | modular-api | modular-api | watchlist_id(FK), entity_text, added_at |
| `alerts` | Generated alerts | modular-api | database-service | id, watchlist_id(FK), entity_text, event_id(FK), alert_type, message, risk_score, is_read |
| `audit_logs` | Audit trail | modular-api | modular-api | id, user_id, action, resource_type, resource_id, details, ip_address |
| `article_embeddings` | Vector embeddings (pgvector) | modular-api | embedding-service | article_id(FK) UNIQUE, embedding vector(384), HNSW index |
| `cases` | Investigation cases | modular-api | modular-api | id, title, description, status, priority, created_by, assigned_to |
| `case_items` | Case-linked resources | modular-api | modular-api | case_id(FK), item_type, item_id |
| `case_notes` | Case investigation notes | modular-api | modular-api | case_id(FK), content, created_by |
| `copilot_conversations` | Copilot chat sessions | modular-api | modular-api | id(PK), title, user_id, created_at |
| `copilot_messages` | Copilot message history | modular-api | modular-api | conversation_id(FK), role, content, tool_calls, metadata |
| `energy_entity_mappings` | Article→energy asset bridges | modular-api | database-service | article_id(FK), entity_text, energy_asset_type, energy_asset_uuid(FK), match_method |
| `article_energy_enrichments` | Cached energy context | modular-api | database-service | article_id(FK) UNIQUE, locations JSONB, infrastructure JSONB, organizations JSONB, commodities JSONB, infrastructure_events JSONB, context JSONB |

**Indexes:** 30+ including HNSW vector index (`article_embeddings.embedding` vector_cosine_ops)

### 6.2 PostgreSQL — `energy` Schema

**Init file:** `infra/sql/energy_schema.sql` (533 lines)
**9 ENUMs:** `lifecycle_state`, `operational_status`, `criticality_level`, `organization_type`, `relationship_type`, `event_type`, `severity_level`, `location_type`, `asset_type`

| Table | Purpose | R | W |
|---|---|---|---|
| `energy.locations` | Geographic locations | energy-service, modular-api | energy-service |
| `energy.organizations` | Companies, agencies, NOCs/IOCs | energy-service | energy-service |
| `energy.commodities` | Traded energy commodities | energy-service | energy-service |
| `energy.ports` | Maritime ports | energy-service | energy-service |
| `energy.oil_fields` | Oil production fields | energy-service | energy-service |
| `energy.gas_fields` | Natural gas fields | energy-service | energy-service |
| `energy.pipelines` | Oil/gas pipelines | energy-service | energy-service |
| `energy.refineries` | Petroleum refineries | energy-service | energy-service |
| `energy.power_plants` | Power generation plants | energy-service | energy-service |
| `energy.storage_facilities` | Energy storage | energy-service | energy-service |
| `energy.strategic_petroleum_reserves` | SPR facilities | energy-service | energy-service |
| `energy.import_corridors` | Supply corridors | energy-service | energy-service |
| `energy.shipping_routes` | Maritime routes | energy-service | energy-service |
| `energy.suppliers` | Supply chain vendors | energy-service | energy-service |
| `energy.entity_relationships` | Cross-entity graph edges | energy-service | energy-service |
| `energy.infrastructure_events` | Operational events | energy-service | energy-service |
| `energy.capacity_history` | Capacity time-series | energy-service | energy-service |

**Common columns (all entity tables):** `id BIGSERIAL`, `uuid UUID UNIQUE`, `name`, `slug UNIQUE`, `status`, `criticality`, `organization_id`, `location_id`, `tags JSONB`, `metadata JSONB`, `is_deleted`, `created_at`, `updated_at`, `deleted_at`

**Dual-identifier pattern:** BIGSERIAL internal + UUID external, soft-delete, data provenance

### 6.3 PostgreSQL — `ml` Schema

**Init file:** `infra/sql/ml_schema.sql` (891 lines)
**5 ENUMs:** `feature_type`(11 values), `model_stage`(5), `model_type`(6), `split_type`(3)

| Table | Purpose | R | W |
|---|---|---|---|
| `ml.feature_definitions` | Feature registry | ml-platform | ml-platform |
| `ml.feature_groups` | Logical feature groups | ml-platform | ml-platform |
| `ml.feature_group_members` | Feature membership | ml-platform | ml-platform |
| `ml.feature_vectors` | Computed feature vectors | ml-platform | ml-platform |
| `ml.feature_snapshots` | Point-in-time feature sets | ml-platform | ml-platform |
| `ml.feature_importance` | Feature importance per model | ml-platform | ml-platform |
| `ml.transform_registry` | Transform operations | ml-platform | ml-platform |
| `ml.datasets` | Built dataset metadata | ml-platform | ml-platform |
| `ml.dataset_catalog` | Master dataset registry | ml-platform | ml-platform |
| `ml.dataset_lineage` | Parent/child DAG | ml-platform | ml-platform |
| `ml.dataset_provenance` | Source tracking | ml-platform | ml-platform |
| `ml.dataset_statistics` | Per-version stats | ml-platform | ml-platform |
| `ml.dataset_profiles` | Per-column profiles | ml-platform | ml-platform |
| `ml.dataset_manifests` | File integrity manifests | ml-platform | ml-platform |
| `ml.dataset_validations` | Validation results | ml-platform | ml-platform |
| `ml.dataset_cards` | Dataset documentation | ml-platform | ml-platform |
| `ml.model_versions` | Model registry (5 stages) | ml-platform | ml-platform |
| `ml.predictions` | Prediction audit log | ml-platform | ml-platform |
| `ml.drift_baselines` | Reference distributions | ml-platform | ml-platform |
| `ml.drift_results` | Drift detection history | ml-platform | ml-platform |
| `ml.model_governance` | Stage transition audit | ml-platform | ml-platform |
| `ml.training_schedules` | Retraining configs | ml-platform | ml-platform |
| `ml.experiments` | Research experiments | ml-platform | ml-platform |
| `ml.experiment_runs` | Experiment run results | ml-platform | ml-platform |
| `ml.connector_definitions` | Connector configurations | ml-platform | ml-platform |
| `ml.ingestion_pipelines` | Ingestion workflow defs | ml-platform | ml-platform |
| `ml.ingestion_jobs` | Ingestion job records | ml-platform | ml-platform |
| `ml.ingestion_errors` | Ingestion error log | ml-platform | ml-platform |
| `ml.normalization_rules` | Normalization rule defs | ml-platform | ml-platform |
| `ml.quality_reports` | Quality score history | ml-platform | ml-platform |
| `ml.quality_dashboard` | Quality trend snapshots | ml-platform | ml-platform |
| `ml.feature_pipelines` | Feature pipeline defs | ml-platform | ml-platform |
| `ml.feature_pipeline_runs` | Pipeline execution log | ml-platform | ml-platform |

### 6.4 PostgreSQL — `spr` Schema (in `public`)

**Init file:** `infra/sql/spr_schema.sql` (344 lines)
**4 ENUMs:** `spr_release_reason`, `spr_facility_status`, `spr_strategy`, `spr_timeline_phase`
**Tables:** `spr_facilities`, `spr_inventory`, `spr_capacity`, `spr_release_runs`, `spr_release_plans`, `spr_refill_plans`, `spr_recommendations`, `spr_policy_constraints`, `spr_consumption_forecasts`, `spr_distribution`, `spr_cost_analysis`, `spr_assumptions`, `spr_decision_timeline`

### 6.5 PostgreSQL — `procurement` Schema (in `public`)

**Init file:** `infra/sql/procurement_schema.sql` (368 lines)
**4 ENUMs:** `procurement_priority`, `procurement_status`, `compatibility_score`
**Tables:** `supplier_intelligence`, `refinery_crude_compatibility`, `route_costs`, `alternative_suppliers`, `procurement_runs`, `procurement_recommendations`, `executive_recommendations`, `procurement_assumptions`, `rfq_outputs`, `spr_optimization_runs`

### 6.6 PostgreSQL — `energy_intelligence` Schema (in `energy.`)

**Init file:** `infra/sql/energy_intelligence_schema.sql` (221 lines)
**Tables:** `risk_factors`, `risk_scores`, `disruption_signals`, `response_telemetry`, `commodity_prices`, `ais_positions`, `sanctions`, `port_congestion`, `tanker_availability`, `scenario_assumptions`

### 6.7 PostgreSQL — `digital_twin` Schema (in `public`)

**Init file:** `infra/sql/digital_twin_schema.sql` (255 lines)
**5 ENUMs:** `simulation_status`, `node_category`, `edge_category`, `simulation_mode`, `scenario_category`
**Tables:** `network_nodes`, `network_edges`, `simulation_scenarios`, `digital_twin_runs`, `flow_states`, `simulation_tick_events`, `network_snapshots`, `demand_profiles`, `flow_constraints`

---

## 7. ML Platform Deep Dive

### 7.1 Overview

**Location:** `services/ml-platform/`
**Port:** 8007
**Total:** 280 files, ~35,706 lines of Python
**Database:** `ml.*` schema (37 tables)

### 7.2 Components

#### Dataset Registry (`datasets/catalog.py`)
- **Status:** ✅ Implemented
- `DatasetCatalog.register()` — INSERT/UPDATE into `ml.dataset_catalog`
- `search()`, `get()`, `get_by_uuid()`, `update_tags()`, `deactivate()`
- Valid types: news_articles, energy_infrastructure, knowledge_graph, risk_signals, commodity_prices, digital_twin, procurement, spr, events, entity_relationships, graph_embeddings, hybrid

#### Dataset Builders (`datasets/builders/`)
- **Status:** ⚠️ Only `energy_infrastructure` and `risk_signals` are real; 10 of 12 are stubs
- `BaseDatasetBuilder` with 5 abstract methods: `define_sources()`, `define_joins()`, `define_cleaning()`, `define_features()`, `define_labels()`
- Stub builders: commodity_prices, digital_twin, events, entity_relationships, graph_embeddings, hybrid, knowledge_graph, news_articles, procurement, spr

#### Feature Store (`feature_store/`)
- **Status:** ✅ Implemented
- `FeatureRegistry` — 11 feature types, versioned definitions
- `FeaturePipeline` — Online feature computation + caching (1h TTL)
- `FeaturePipelineEngine` — DAG-based execution with topological sort, caching, snapshots
- 18 transform classes (rolling window, EWMA, lag, interaction, polynomial, geospatial, etc.)
- `FeatureSnapshots` — Point-in-time captures for reproducible training

#### Data Acquisition (`data_acquisition/`)
- **Status:** ✅ Implemented
- **Source Registry** — 28 source definitions across 7 categories
- **Download Manager** — Async, retries, streaming, progress tracking
- **17 parsers** — GDELT(4), EIA(2), OPEC, AIS(3), commodity(2), sanctions(2), World Bank, UN Comtrade, Kaggle
- **Canonical Schema** — 18-field standard: entity_type, entity_id, entity_name, timestamp, lat/lng, attributes, relationships, source, confidence
- **Registration Pipeline** — Stats, profiling, checksums, catalog, manifests
- **GDELT Pipeline** — 10 files: master file reader, filter, downloader, parser, registration, validation, report, CLI, REST router

#### Normalization (`normalization/`)
- **Status:** ✅ Implemented (14 rules, but NOT integrated into pipeline)
- Country, org, date, currency, geospatial, timestamp, unit, missing value, duplicate, entity ID, ontology map, schema map, categorical encoding, column standardizer

#### Quality (`quality/`)
- **Status:** ✅ Implemented (but NOT used as gatekeeper)
- `QualityScorer` — 6 dimensions (completeness, consistency, uniqueness, timeliness, validity, integrity)
- `QualityReporter` — structural reports, comparisons, summaries
- `QualityDashboard` — trends, lowest-scoring columns, aggregate

#### Research Platform (`research/`)
- **Status:** ✅ Implemented
- Experiment runner, cross-validation (5 strategies), evaluation (classification, regression, anomaly, forecasting), hyperparameter search (grid, random, Optuna), explainability (SHAP, permutation, partial dependence), model factory, trainers (7 types), model cards, leaderboard, reports (HTML, JSON, Markdown), notebook runner

#### Model Registry (`registry/`)
- **Status:** ✅ Implemented
- 5-stage lifecycle: development → validation → staging → production → archived
- CRUD via REST API

#### Training (`training/`)
- **Status:** ✅ Implemented
- MLflow experiment tracking, hyperparameter optimization, model wrappers (LogisticRegression, DecisionTree, RandomForest, XGBoost)

### 7.3 Current Gaps

1. **No transformation pipeline** — canonical records → research datasets: missing
2. **Parser `attributes` field is a data black hole** — 80% of value buried in untyped dict
3. **Normalization not integrated** — 14 rules exist but never auto-applied
4. **Quality not a gate** — data accepted regardless of quality score
5. **10/12 dataset builders are stubs** — no real implementations
6. **Temporal splits not supported** — current splitter uses random stratification
7. **Feature engineering not automatic** — transforms exist but require manual configuration
8. **Point-in-time correctness not handled** — feature store computes on latest data

---

## 8. Energy Service Deep Dive

### 8.1 Overview

**Location:** `services/energy-service/`
**Port:** 8006
**Total:** 33 files, 6,728 lines
**Database:** `energy.*` (18 tables), `public.spr*`, `public.procurement*`, `public.digital_twin*`, `energy_intelligence.*`

### 8.2 Components

#### Infrastructure Catalog (`routers/catalog.py`)
- **Status:** ✅ Complete
- 14 entity types with dual BIGSERIAL+UUID, soft-delete, data provenance
- Standardized filtering contract (search, sort, status, criticality, org, location, tag)
- Bulk import (JSON/CSV/GeoJSON) with format auto-detection
- 20+ countries of seed data (ung ENERY_LOAD_SEED=1)

#### Risk Intelligence (`routers/intelligence.py`, `services/risk_engine.py`)
- **Status:** ✅ Complete
- 15 built-in risk factors (chokepoint, sanctions, conflict, port, pipeline, etc.)
- RiskScoringEngine scores entities across multiple dimensions
- SignalDetector ingests disruption signals, evaluates scenarios
- 3 DataIngestors generate simulated data (commodity prices, sanctions, AIS/port congestion)
- MLBridge connects to ML Platform with rule-based fallback
- RiskPropagator spreads risk at 0.3 factor via entity_relationships

#### Digital Twin (`routers/digital_twin.py`, `services/digital_twin/`)
- **Status:** ✅ Complete
- NetworkGraph auto-builds from 10 entity types
- SimulationEngine runs tick-based simulations (default 90 ticks)
- FlowEngine handles capacity constraints, disruptions, cascade effects
- 10 pre-built scenario templates (Hormuz, Red Sea, Russian export, OPEC, etc.)
- Aggregate impact computation (supply gap, idle refineries, economic impact, GDP impact)

#### Procurement Orchestrator (`routers/procurement.py`, `services/procurement/`)
- **Status:** ✅ Complete
- SupplierIntelligence: enrich, score, find alternatives
- RefineryCompatibility: API gravity/sulfur matching
- ProcurementOptimizer: Pareto frontier with 4 optimization goals
- ProcurementOrchestrator: end-to-end runs with executive cards

#### SPR Engine (`services/procurement/spr_engine.py`)
- **Status:** ✅ Complete
- Facility management, inventory tracking, release optimization
- 5 release strategies (conservative/aggressive/economic/strategic/balanced)
- 5-phase decision timeline (Now → 24h → 72h → 7d → 30d)
- 4 recommendation types (release, procurement, refill, policy)

### 8.3 Current Gaps

1. **All ingestor data is simulated** — no real API connections for commodity, sanctions, AIS data
2. **ML Bridge fallback only** — ML Platform integration is via HTTP (no production models deployed)
3. **Event intelligence uses rule-based scoring** — no ML models for risk prediction
4. **Procurement/recommendations use heuristics** — no ML optimization
5. **SPR engine uses fixed strategies** — no ML-driven dynamic strategy selection

---

## 9. AI Layer

### 9.1 LLM Infrastructure

**Provider:** Groq (OpenAI-compatible API)
**Default Model:** `llama-3.3-70b-versatile`
**Fallback Model:** `llama-3.1-8b-instant`
**Token Counting:** tiktoken (cl100k_base)

**LLM Client** (`backend/shared/llm/client.py`):
- OpenAI-compatible chat completions
- Streaming support
- Tool calling (function calling format)
- Retry logic: rate limit → sleep, timeout → retry, 5xx → retry, 401 → fail fast
- Cost tracking per-request

### 9.2 Prompt System

**Location:** `backend/shared/prompts/`
**Prompt Types:**
| Prompt | Purpose |
|---|---|
| `SYSTEM_PROMPTS.supervisor` | Analyze user query, determine approach |
| `SYSTEM_PROMPTS.intelligence` | Execute intelligence analysis |
| `SYSTEM_PROMPTS.research` | Deep research with tools |
| `SYSTEM_PROMPTS.scenario` | What-if scenario analysis |
| `SYSTEM_PROMPTS.decision` | Decision support analysis |
| `SYSTEM_PROMPTS.prediction` | Predictive analysis |
| `SYSTEM_PROMPTS.validation` | Validate findings |
| `SYSTEM_PROMPTS.executive` | Executive summary generation |
| `SYSTEM_PROMPTS.spr` | SPR optimization analysis |
| `SYSTEM_PROMPTS.procurement` | Procurement analysis |
| `SYSTEM_PROMPTS.knowledge_graph` | Graph traversal queries |
| `PLANNING_PROMPTS` | Execution plan generation (default, simple, complex) |
| `REFLECTION_PROMPTS` | Evidence evaluation |
| `EXECUTIVE_PROMPTS` | Synthesis |
| `VALIDATION_PROMPTS` | Claim verification |

### 9.3 Agent Architecture

**Agent Types:** Supervisor → Intelligence → Tools

**Supervisor Agent** (`backend/api/agents/supervisor.py`):
- Analyzes user query
- Determines tool/agent requirements
- Delegates to Intelligence Agent

**Intelligence Agent** (`backend/api/agents/intelligence.py`):
- Coordinates tool execution
- Builds context from multiple sources
- Synthesizes response

**Tool Framework** (`backend/api/tools/`):

| Tool Module | Functions | Data Sources |
|---|---|---|
| `search_tools.py` | search_articles, search_entities | Elasticsearch + PostgreSQL |
| `intelligence_tools.py` | get_risk_scores, get_active_signals, evaluate_scenario | Energy Service Risk API |
| `graph_tools.py` | get_entity_relationships, get_network_graph, find_path | Energy Service Graph API |
| `analytics_tools.py` | get_analytics_summary, get_threat_trends | Modular API analytics |
| `energy_tools.py` | get_port_status, get_commodity_prices, run_simulation, run_procurement | Energy Service APIs |

### 9.4 Reasoning Engine

**Location:** `backend/shared/orchestration/`

**Planner** (`planner.py`):
- LLM generates structured ExecutionPlan from query
- Step: {agent, task, depends_on, mode(sequential/parallel/dependent), tools, max_retries}

**Execution Engine** (`engine.py`):
- Plan → Route → Reflect → Confidence → Answer
- Dynamic plan expansion on reflection ("gather_more")

**Reasoning Loop** (`reasoning.py`):
- Thought → Tool → Observation → Reflection → ... → Final
- Maximum 5 iterations, configurable

**Reflection Engine** (`reflection.py`):
- Evaluates evidence sufficiency
- Detects gaps and conflicts
- Returns: proceed / gather_more

**Confidence Engine** (`confidence.py`):
- Multi-factor: tool_reliability(20%), evidence_count(15%), source_agreement(20%), kg_support(10%), rag_score(10%), llm_eval(10%), contradictions(15%)

### 9.5 RAG Engine

**Location:** `backend/api/rag/`

**Retriever** (`retriever.py`):
- Hybrid search: Elasticsearch keyword + pgvector cosine similarity
- Token-limited context trimming

**Context Builder** (`context.py`):
- Trims to LLM context window (max_tokens)
- Preserves system prompt + most relevant results

**Citation Engine** (`citations.py`):
- Collects citations from: articles, entities, knowledge graph, simulations, risk records, procurement, SPR
- Deduplicates by source_id
- Sorts by relevance

### 9.6 Memory System

**ConversationMemory** — sliding window (max 50 messages), per-conversation
**AgentMemory** — per-agent state tracking per conversation
**ExecutionMemory** — plan history (max 20 plans)
**ContextCompressor** — sliding window + LLM summarization for overflow

### 9.7 Streaming

**StreamingHandler** (`backend/shared/llm/streaming.py`):
- SSE format: `data: {...}\n\n`
- Events: TOKEN, TOOL_CALL, TOOL_RESULT, AGENT_STATUS, CITATION, CONFIDENCE, ERROR, DONE, METADATA

---

## 10. Research Platform

### 10.1 Overview

**Location:** `services/ml-platform/research/`
**Total:** 65 files, ~8,092 lines

### 10.2 Components

| Component | Status | Description |
|---|---|---|
| **Experiment Runner** | ✅ Complete | Single experiment execution with model training, evaluation, MLflow logging |
| **Cross-Validation** | ✅ Complete | K-fold, stratified, time-series, grouped, nested CV |
| **Evaluation** | ✅ Complete | Classification, regression, anomaly, forecasting metrics |
| **Hyperparameter Search** | ✅ Complete | Grid search, random search, Optuna integration |
| **Explainability** | ✅ Complete | SHAP, permutation importance, partial dependence |
| **Model Factory** | ✅ Complete | 7 model types: classification, regression, forecasting, anomaly, clustering, ranking |
| **Model Cards** | ✅ Complete | Comprehensive model documentation generation |
| **Leaderboard** | ✅ Complete | Ranked model comparison with filtering |
| **Reports** | ✅ Complete | HTML, JSON, Markdown output formats |
| **Notebook Runner** | ✅ Complete | Programmatic Jupyter notebook execution |
| **Data Explorers** | ✅ Complete | Schema, metadata, time-series, correlation, geospatial explorers |

### 10.3 External Research Environment

**Location:** `research/` (root-level, NOT in Docker)
**Notebooks:** 8 Jupyter notebooks covering EDA → Preprocessing → Feature Engineering → Baseline → Comparison → Tuning → Explainability → Export
**Configs:** YAML experiment configs
**Models:** Exported `.joblib` files → consumed by ML Platform deployment module

---

## 11. External Data Sources

| Source | Status | Parser | API | Update Frequency | Fields | Coverage |
|---|---|---|---|---|---|---|
| **GDELT Events** | ✅ Complete | `GDELTEventParser` | HTTP masterfilelist.txt | 15 min | 61 columns (events) | Global, 2015-present |
| **GDELT Mentions** | ✅ Complete | `GDELTMentionParser` | HTTP | 15 min | 16 columns | Global, 2015-present |
| **GDELT GKG** | ✅ Complete | `GKGParser` | HTTP | 15 min | 27 columns (GKG v2) | Global, 2015-present |
| **AIS** | ✅ Parser only | `AISParser` | (simulated) | N/A | 18 columns | N/A (no API connected) |
| **Port Congestion** | ✅ Parser only | `PortCongestionParser` | (simulated) | N/A | 10 columns | N/A |
| **World Port Index** | ✅ Parser only | `WorldPortIndexParser` | Static file | Static | 12 columns | ~10,000 ports |
| **EIA** | ✅ Parser only | `EIAParser` | (not connected) | N/A | 10 columns | N/A |
| **FRED** | ✅ Parser only | `FREDParser` | (not connected) | N/A | 6 columns | N/A |
| **OPEC** | ✅ Parser only | `OPECParser` | (not connected) | N/A | 8 columns | N/A |
| **OFAC Sanctions** | ✅ Parser only | `OFACParser` | (simulated via ingestor) | N/A | 8 columns | 10 countries (simulated) |
| **UN Comtrade** | ✅ Parser only | `UNComtradeParser` | (not connected) | N/A | 12 columns | N/A |
| **World Bank** | ✅ Parser only | `WorldBankParser` | (not connected) | N/A | 9 columns | N/A |
| **Commodity Prices** | ✅ Parser only | `CommodityPriceParser` | (simulated via ingestor) | N/A | 10 columns | 10 benchmarks (simulated) |
| **Commodity Futures** | ✅ Parser only | `CommodityFuturesParser` | (not connected) | N/A | 12 columns | N/A |
| **Kaggle** | ✅ Parser only | `KaggleParser` | (not connected) | N/A | 34 mapping entries | N/A |
| **GNews** | ✅ Complete | Ingest service | REST API (real) | Hourly | 8 fields | Global news (10 per fetch) |

---

## 12. End-to-End Sequence Diagrams

### 12.1 Data Ingestion

```
GNews API           Ingest             Kafka               ML              Database            ES
   │                Service           raw_articles       Service           Service
   │                   │                   │                 │                 │
   │   GET /v4/search  │                   │                 │                 │
   │◄─────────────────►│                   │                 │                 │
   │                   │ produce(id,title, │                 │                 │
   │                   │   content,source, │                 │                 │
   │                   │   published_at,   │                 │                 │
   │                   │   url,image)      │                 │                 │
   │                   │──────────────────►│                 │                 │
   │                   │                   │  poll()         │                 │
   │                   │                   │◄────────────────│                 │
   │                   │                   │ producer(id,    │                 │
   │                   │                   │   entities,     │                 │
   │                   │                   │   sentiment,    │                 │
   │                   │                   │   topic,        │                 │
   │                   │                   │   threat_score, │                 │
   │                   │                   │   relationships)│                 │
   │                   │                   │─────────────────│                 │
   │                   │                   │                 │  poll()         │
   │                   │                   │                 │◄────────────────│
   │                   │                   │                 │  upsert_article │
   │                   │                   │                 │  replace_rels() │
   │                   │                   │                 │  event_cluster()│
   │                   │                   │                 │  energy_enrich()│
   │                   │                   │                 │  index_article()│
   │                   │                   │                 │────────────────►│
```

### 12.2 AI Copilot

```
Frontend            Modular API        LLM(Groq)        Tools           RAG           Energy
   │                     │                │                │              │           Service
   │  POST /copilot/     │                │                │              │              │
   │  query/stream       │                │                │              │              │
   │────────────────────►│                │                │              │              │
   │                     │  Supervisor    │                │              │              │
   │                     │  Agent Plan    │                │              │              │
   │                     │──────────────►│                │              │              │
   │                     │◄──────────────│                │              │              │
   │                     │                │                │              │              │
   │                     │  Execute       │                │              │              │
   │                     │  Intelligence  │                │              │              │
   │                     │  Agent         │                │              │              │
   │                     │────────────────────────────────►│              │              │
   │                     │                │                │              │              │
   │                     │                │  RAG search    │              │              │
   │                     │                │──────────────────────────────►│              │
   │                     │                │◄──────────────────────────────│              │
   │                     │                │                │              │              │
   │                     │                │  Energy risk   │              │              │
   │                     │                │─────────────────────────────────────────────►│
   │                     │                │◄─────────────────────────────────────────────│
   │                     │                │                │              │              │
   │                     │  Reflection    │                │              │              │
   │   SSE: TOOL_RESULT  │◄───────────────│                │              │              │
   │◄────────────────────│                │                │              │              │
   │                     │  Confidence    │                │              │              │
   │                     │  Scoring       │                │              │              │
   │   SSE: CONFIDENCE   │                │                │              │              │
   │◄────────────────────│                │                │              │              │
   │                     │  Final         │                │              │              │
   │                     │  Synthesis     │                │              │              │
   │                     │──────────────►│                │              │              │
   │   SSE: TOKEN × N    │◄──────────────│                │              │              │
   │◄────────────────────│                │                │              │              │
   │   SSE: CITATION     │                │                │              │              │
   │◄────────────────────│                │                │              │              │
   │   SSE: DONE         │                │                │              │              │
   │◄────────────────────│                │                │              │              │
```

---

## 13. Current Project Status

### 13.1 Completed Components

| Component | Status | Details |
|---|---|---|
| **Infrastructure** | ✅ Complete | PostgreSQL 15 + pgvector, Kafka 7.4, Elasticsearch 8.11, Docker Compose |
| **Ingest Service** | ✅ Complete | GNews fetch, Kafka producer, hourly scheduler |
| **ML Service** | ✅ Complete | NLP pipeline (spaCy NER, keyword sentiment/topic/threat) |
| **Database Service** | ✅ Complete | Kafka consumer, PostgreSQL + ES persistence, event intelligence, energy enrichment |
| **Embedding Service** | ✅ Complete | Kafka consumer, vector storage (model TBD) |
| **Energy Service Catalog** | ✅ Complete | 14 entity types, CRUD, bulk import/export, seed data |
| **Energy Service Intelligence** | ✅ Complete | Risk scoring, signal detection, scenario evaluation, simulated ingestors |
| **Energy Service Digital Twin** | ✅ Complete | Tick simulation, flow engine, 10 scenarios, impact analysis |
| **Energy Service Procurement** | ✅ Complete | Supplier intel, compatibility, optimizer (Pareto), orchestration, executive cards |
| **Energy Service SPR** | ✅ Complete | Release optimization, decision timeline, 5 strategies |
| **Modular API** | ✅ Complete | Gateway, auth, articles, analytics, entities, events, graph, alerts, watchlists, cases, reports |
| **AI Copilot** | ✅ Complete | Supervisor + Intelligence agents, 5 tool modules, planning/reasoning/reflection/confidence, RAG |
| **Frontend** | ✅ Complete | 32 pages, Copilot, Digital Twin, Procurement, SPR, Risk, Graph, Energy Map |
| **ML Platform — Feature Store** | ✅ Complete | Feature registry, 18 transforms, DAG pipeline engine, online serving |
| **ML Platform — Data Acquisition** | ✅ Complete | 28 source definitions, 17 parsers, download manager, canonical records, registration |
| **ML Platform — GDELT Pipeline** | ✅ Complete | 10 files, end-to-end download→parse→validate, 267 tests, 4218 records parsed |
| **ML Platform — Research** | ✅ Complete | Experiment runner, CV, evaluation, hyperparameter search, explainability, model cards, leaderboard |
| **ML Platform — Training** | ✅ Complete | MLflow tracking, model wrappers, optimization |
| **ML Platform — CLI** | ✅ Complete | 13 commands + GDELT subcommands |
| **ML Platform — Normalization** | ✅ Complete | 14 normalization rules (not pipeline-integrated) |
| **ML Platform — Quality** | ✅ Complete | 6-dimension scoring, reports, dashboard (not gate-integrated) |
| **Scripts** | ✅ Complete | 54 scripts across dev/ops/maintenance/testing |
| **CI** | ✅ Complete | Pre-commit hooks (ruff lint+format), pyproject.toml config |

### 13.2 Partially Completed Components

| Component | Status | Gap |
|---|---|---|
| **ML Platform — Normalization Integration** | ⚠️ Partial | 14 rules exist as modules but never auto-applied in pipeline |
| **ML Platform — Quality Gates** | ⚠️ Partial | Quality scoring exists but data flows through without rejection |
| **ML Platform — Dataset Builders** | ⚠️ Partial | 2 real + 10 stub builders out of 12 |
| **External API Connections** | ⚠️ Partial | Only GNews is real; EIA, FRED, OPEC, World Bank, UN Comtrade are parser-only |
| **Energy Ingestors** | ⚠️ Partial | All 3 ingestor implementations use simulated data |
| **ML Platform → Energy ML Bridge** | ⚠️ Partial | HTTP connection exists but returns rule-based fallback (no models deployed) |
| **Embedding Service Model** | ⚠️ Partial | Pipeline exists, model not verified |
| **Testing** | ⚠️ Partial | ML Platform has 1032 tests; other services have limited coverage |

### 13.3 Placeholder/Stub Components

| Component | Status | Notes |
|---|---|---|
| `datasets/builders/commodity_prices.py` | 🟡 Stub | Empty `define_*()` methods |
| `datasets/builders/digital_twin.py` | 🟡 Stub | Empty |
| `datasets/builders/events.py` | 🟡 Stub | Empty |
| `datasets/builders/entity_relationships.py` | 🟡 Stub | Empty |
| `datasets/builders/graph_embeddings.py` | 🟡 Stub | Empty |
| `datasets/builders/hybrid.py` | 🟡 Stub | Empty |
| `datasets/builders/knowledge_graph.py` | 🟡 Stub | Empty |
| `datasets/builders/news_articles.py` | 🟡 Stub | Empty |
| `datasets/builders/procurement.py` | 🟡 Stub | Empty |
| `datasets/builders/spr.py` | 🟡 Stub | Empty |
| `README.md` | 🟡 Stub | Empty file (0 bytes) |
| `backend/api_service/` | 🟡 Stub | Legacy app (1-line main.py), superseded by `backend/api/` |
| `research/notebooks/` | 🟡 Stub | 8 notebook files exist but content unverified |

### 13.4 Technical Debt

| Issue | Severity | Location |
|---|---|---|
| **API keys in .env** | 🔴 High | Groq + GNews API keys committed to repo |
| **Hardcoded passwords** | 🔴 High | `POSTGRES_PASSWORD=change-me`, `ELASTIC_PASSWORD=change-me` |
| **Two API app instances** | 🟡 Medium | `backend/api/` (current) + `backend/api_service/` (legacy, partially different endpoints) |
| **Sync DB in database-service** | 🟡 Medium | Uses psycopg2 (sync) while rest of platform uses asyncpg |
| **Async vs sync client split** | 🟡 Medium | Elasticsearch has both async (`elastic.py`) and sync (`elastic_client.py`) clients |
| **No SQLAlchemy** | 🟡 Medium | Raw SQL in all services — flexible but no migration safety net |
| **Alembic migrations incomplete** | 🟡 Medium | 6 migrations exist but canonical SQL files are source of truth (schema_bootstrap) |
| **Strict TypeScript disabled** | 🟢 Low | `noImplicitAny: false`, `strictNullChecks: false` |
| **README.md empty** | 🟢 Low | No project documentation (CLAUDE.md serves as de facto README) |
| **Accidental files** | 🟢 Low | `cd` and `curl` files at root (shell artifacts) |
| **Duplicate API routes** | 🟢 Low | Some routes exist in both `backend/api/` and `backend/api_service/` |
| **`schema_bootstrap.py` deprecated** | 🟢 Low | Just re-exports from `database/migrations.py` |

---

## 14. Architecture Assessment

### 14.1 Strengths

1. **Service boundary clarity** — Each service has well-defined responsibilities with minimal overlap
2. **Event-driven decoupling** — Kafka between ingest→ML→database allows independent scaling
3. **Canonical schema** — 18-field standard across 17 parsers provides consistency
4. **Feature store maturity** — DAG pipeline, caching, versioning, online serving
5. **Energy domain depth** — End-to-end from infrastructure catalog to SPR optimization
6. **AI agent maturity** — Planning, reasoning, reflection, confidence, citations, tool framework
7. **Digital Twin simulation** — Tick-based with flow rebalancing, disruption modeling, impact computation
8. **Frontend coverage** — 32 pages covering all capabilities
9. **Development tooling** — 54 scripts across dual platform (PowerShell + Bash), comprehensive start-local.ps1

### 14.2 Weaknesses

1. **ML Platform produces no real ML datasets** — Data acquisition pipeline stops at canonical records. No transformation to research-grade datasets.
2. **All energy ingestor data is simulated** — Commodity prices, sanctions, AIS data are all synthetic
3. **No real ML models in production** — Energy Service ML Bridge falls back to rule-based scoring
4. **API gateway has two versions** — `backend/api/` and `backend/api_service/` cause confusion
5. **Normalization rules exist but unused** — 14 rules never integrated into data pipeline
6. **Quality scoring exists but unused as gate** — Data flows through regardless of score
7. **10/12 dataset builders are empty stubs** — Promised functionality doesn't exist
8. **Sync database service** — psycopg2 while rest of async platform uses asyncpg
9. **No cross-source deduplication** — GDELT and ACLED may describe same event with no resolution
10. **Parser attributes are data black hole** — 80% of valuable fields buried in untyped dicts

### 14.3 Scalability

| Dimension | Assessment |
|---|---|
| **Service scaling** | Each service is independently deployable via Docker Compose |
| **Kafka partitioning** | Topics have 2-3 partitions; could increase for higher throughput |
| **Database** | Single PostgreSQL instance — would need read replicas or sharding at scale |
| **Frontend** | Static SPA served via Nginx — trivially scalable |
| **ML training** | Currently local — no distributed training support |
| **Feature serving** | Single-node caching — would need Redis Cluster for high throughput |

### 14.4 Security

| Aspect | Status |
|---|---|
| **JWT Auth** | ✅ Implemented on modular-api and database-service |
| **API keys in .env** | ❌ Groq and GNews keys committed to repo |
| **Elasticsearch auth** | ✅ Basic auth enabled |
| **PostgreSQL** | ✅ Password auth |
| **CORS** | ✅ Configured |
| **Secrets management** | ❌ No Vault or secrets manager |

---

## 15. Future Work

### 15.1 What Is Finished

1. **Infrastructure**: PostgreSQL+pgvector, Kafka, Elasticsearch, Docker Compose
2. **News Pipeline**: GNews → Ingest → ML NLP → Database → ES (end-to-end working)
3. **Energy Catalog**: 14 entity types with CRUD, filtering, bulk import
4. **Energy Risk Intelligence**: Risk scoring, signal detection, scenario evaluation, simulated ingestors
5. **Digital Twin**: Tick simulation, flow engine, 10 scenarios, impact analysis
6. **Procurement Orchestrator**: Supplier intel, compatibility, optimization, executive cards
7. **SPR Decision Engine**: Release optimization, decision timeline, 5 strategies
8. **AI Copilot**: Supervisor + Intelligence agents, 5 tool modules, RAG, reasoning loop
9. **Frontend**: 32 pages covering all capabilities
10. **ML Platform Data Acquisition**: 28 sources, 17 parsers, GDELT pipeline
11. **ML Platform Feature Store**: Feature registry, 18 transforms, DAG engine, online serving
12. **ML Platform Research**: Experiment runner, CV, evaluation, hyperparameter search, explainability
13. **ML Platform Training**: MLflow, model wrappers, optimization
14. **Development Tooling**: 54 scripts, pre-commit, Makefile
15. **GDELT Pipeline**: End-to-end download → parse → validate, 4218 records, 267 tests

### 15.2 What Remains Unfinished

1. **ML Platform Dataset Builders** — 10 of 12 are empty stubs
2. **Normalization Pipeline Integration** — 14 rules never auto-applied
3. **Quality Gates** — Scoring exists but data flows through without rejection
4. **Research-Grade Dataset Pipeline** — Gap between canonical records and ML-ready datasets
5. **External API Connections** — Only GNews is real; EIA, FRED, OPEC, World Bank, UN Comtrade are parser-only
6. **Energy Ingestors** — All generate simulated data, no real API connections
7. **ML Platform ML Bridge** — Rule-based fallback, no production models deployed
8. **Cross-Source Deduplication** — No resolution between GDELT and ACLED
9. **Embedding Model Verification** — Pipeline exists, model not confirmed working
10. **README.md** — Empty file needs content
11. **Legacy Code Cleanup** — `backend/api_service/` directory, root-level `cd`/`curl` artifacts

### 15.3 Recommended Implementation Order

| Priority | Work Item | Depends On | Impact |
|---|---|---|---|
| 1 | **API key rotation** (remove committed keys) | None | 🔴 Security |
| 2 | **Clean up `backend/api_service/`** | Audit routes not in `backend/api/` | 🟡 Maintainability |
| 3 | **README.md** documentation | Complete audit | 🟢 Onboarding |
| 4 | **Remove accidental files** (`cd`, `curl`) | None | 🟢 Cleanliness |
| 5 | **Normalization pipeline integration** | Existing normalization rules | 🟡 Data quality |
| 6 | **Quality gate integration** | Existing QualityScorer | 🟡 Data quality |
| 7 | **Dataset builder implementations** | Normalized canonical records | 🔴 ML readiness |
| 8 | **Canonical → Research dataset transformation** | Normalization + quality gates | 🔴 ML readiness |
| 9 | **Temporal split framework** | Existing DatasetSplitter | 🟡 ML correctness |
| 10 | **Feature engineering automation** | Existing transforms | 🟡 ML productivity |
| 11 | **Real API connections** (EIA, FRED, OPEC first) | Parser implementations | 🟡 Data freshness |
| 12 | **Deploy baseline ML models** | Research datasets | 🔴 Intelligence value |
| 13 | **Cross-source deduplication** | Normalized canonical layer | 🟡 Data quality |
| 14 | **Embedding model verification + improvement** | Existing embedding pipeline | 🟢 Search quality |

---

*End of Architecture Reference v1.0*
