# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProxyDefence is a military-grade cyber defense intelligence platform with an event-driven microservices architecture. Data flows through a Kafka pipeline: news is ingested → processed by ML/NLP → stored in PostgreSQL and Elasticsearch → served to the React frontend via FastAPI.

## Architecture

### Data Pipeline

```
GNews API → ingest-service → Kafka (raw_articles)
                          → ml-service → Kafka (processed_articles)
                                         → database-service → PostgreSQL + Elasticsearch
                                         → modular-api → Frontend

Energy Service (port 8006) → PostgreSQL (energy schema)
                          → Standalone catalog; consumed by future services

ML Platform (port 8007) → PostgreSQL (ml schema)
                       → Consumes Energy Service data; serves prediction API

Research (research/) → Jupyter notebooks → Exported models → ML Platform
                       (local, no Docker, pure experimentation)

```

### Service Ports

| Service | Port |
| --- | --- |
| Frontend (Vite dev) | 8080 |
| Ingest Service | 8001 |
| ML Service | 8002 |
| Database Service | 8003 |
| Embedding Service | 8005 |
| Modular API | 8000 |
| Energy Service | 8006 |
| ML Platform | 8007 |
| Kafka | 9092 |
| PostgreSQL | 5432 |
| Elasticsearch | 9200 |

### Microservices

**ingest-service** (`services/ingest-service/`)

* FastAPI service that fetches news from GNews API
* Publishes raw articles to `raw_articles` Kafka topic
* Trigger via `GET /fetch-real-news` endpoint

**ml-service** (`services/ml-service/`)

* FastAPI service that subscribes to `raw_articles` topic
* Performs sentiment analysis (keyword-based, returns negative/positive/neutral)
* Publishes processed articles to `processed_articles` Kafka topic
* Runs consumer as background thread on startup
* Uses spaCy, Transformers, PyTorch (though sentiment is currently simple keyword-based)

**database-service** (`services/database-service/`)

* FastAPI service that consumes from `processed_articles` topic
* Stores articles in PostgreSQL `processed_articles` table
* Indexes articles in Elasticsearch `processed_articles` index
* Provides REST endpoints: `/api/articles`, `/api/analytics/summary`, `/api/search`, `/api/articles/{article_id}`

**energy-service** (`services/energy-service/`)

* FastAPI microservice — authoritative infrastructure catalog for the energy domain
* 14 entity types: locations, organizations, commodities, ports, oil_fields, gas_fields, pipelines, refineries, power_plants, storage_facilities, strategic_petroleum_reserves, import_corridors, shipping_routes, suppliers
* Dual identifiers (BIGSERIAL+UUID), soft delete, data provenance on every record
* Standardized filtering contract (search, sort, status, criticality, org, location, tag)
* Bulk import supporting JSON, CSV, GeoJSON format detection
* Idempotent seed data covering 20+ countries, 22 ports, 15 refineries, 15 pipelines, 15 oil fields, chokepoints, shipping routes, SPRs, benchmarks
* Tables live in `energy.` schema, auto-created on startup via `energy_schema.sql`
* Seed data enabled via `ENERGY_LOAD_SEED=1` env var
* REST API at `/api/v1/energy/`

**ml-platform** (`services/ml-platform/`)

* Production ML Platform — dataset building, feature engineering, model training, experiment tracking, model registry, prediction API
* 4 tables in `ml.` schema: feature_definitions, datasets, model_versions, predictions
* Feature store with 11 feature types (numerical, categorical, boolean, timestamp, geospatial, entity_statistics, relationship_statistics, historical_capacity, infrastructure, embedding_reference, graph_placeholder)
* Dataset builder pulling data from Energy Service REST API with deterministic train/val/test splits
* Baseline models: Logistic Regression, Decision Tree, Random Forest, XGBoost, LightGBM
* MLflow experiment tracking with parameter/metric/artifact logging
* Model registry with 5-stage lifecycle: development → validation → staging → production → archived
* Prediction API returning prediction + confidence + probabilities + model_version + feature_version + latency
* Hyperparameter optimization via Grid Search, Random Search, and Optuna
* SHAP explainability integration
* DVC dataset versioning
* No notebooks, no experimentation — pure deterministic production ML infrastructure
* Consumes from Energy Service; consumed by future services (Risk Engine, Copilot, Digital Twin)

**research/** (`research/`)

* Non-Docker research environment for ML experimentation
* 8 Jupyter notebooks forming a structured ML learning journey: EDA → Preprocessing → Feature Engineering → Baseline Models → Model Comparison → Hyperparameter Tuning → Explainability → Model Export
* Each notebook includes concept explanation, mathematical intuition, visualizations, interview questions, and production mapping
* Fetches data from Energy Service via `research/datasets/fetch_data.py`
* Exported models from notebook 08 go to `research/models/` for production consumption
* MLflow tracking (local), synthetic data fallback when Energy Service unavailable
* **NEVER installed inside Docker** — uses `requirements-research.txt`

## Environment Separation

The project strictly separates **Research** (local Jupyter/Kaggle/Colab) from **Production** (FastAPI in Docker).

### Dependency Files

| File | Environment | Purpose |
|------|------------|---------|
| `services/ml-platform/requirements.txt` | Production Docker | Inference-only: fastapi, uvicorn, asyncpg, sklearn, xgboost, joblib |
| `research/requirements-research.txt` | Local research | Full ML stack: mlflow, dvc, shap, optuna, lightgbm, jupyter, viz |

### Research Workflow
```
Kaggle/Jupyter
  ↓
EDA → Feature Engineering → Training → Experiment Tracking → Model Export
  ↓
research/models/*.joblib
```

### Production Workflow
```
Exported Model (research/models/*.joblib)
  ↓
ML Platform FastAPI (Docker)
  ↓
Load → Preprocess → Inference → Return Prediction
  ↓
Only: health, metrics, logging, request validation
```

### Key Rules
- Research code NEVER becomes part of the Docker image
- Notebooks never execute inside containers
- Docker is only for production services
- Training, tuning, SHAP, EDA, visualizations belong exclusively to research
- Production only loads models, preprocesses inputs, and serves predictions

### Database Schema

**processed_articles** - Main article table with id, title, content, source, published_at, ml_processed, confidence, sentiment
**extracted_entities** - Child table referencing processed_articles(id)
**article_sentiments** - Child table referencing processed_articles(id)

Schema defined in `infra/sql/init.sql`, initialized on PostgreSQL container startup.

### Energy Domain Schema (energy schema)

**18 tables in `energy.` schema**: locations, organizations, commodities, ports, oil_fields, gas_fields, pipelines, refineries, power_plants, storage_facilities, strategic_petroleum_reserves, import_corridors, shipping_routes, suppliers, entity_relationships, infrastructure_events, capacity_history

**9 ENUM types**: lifecycle_state, operational_status, criticality_level, organization_type, relationship_type, event_type, severity_level, location_type, asset_type

Canonical DDL in `infra/sql/energy_schema.sql`, Alembic migration #0003 in `backend/shared/migrations/versions/`.

### Frontend Stack

* React 18 + TypeScript 5.8 + Vite 5.4
* Tailwind CSS 3.4 + shadcn/ui components (Radix UI primitives)
* React Router 6 for routing
* TanStack Query (@tanstack/react-query) for data fetching
* React Hook Form + Zod for forms
* Recharts for charts
* Lucide React for icons
* Axios for API calls to modular-api

**Frontend API client** (`frontend/src/lib/api.ts`):

* Uses `VITE_API_URL` env var, defaults to `http://localhost:8000`
* Key functions: `fetchArticles()`, `fetchAnalyticsSummary()`

---

## AI Collaboration (Gemini Integration)

This project uses a "Multi-Model" approach. While Claude handles code generation and refactoring, **Gemini 1.5/2.0** is used for high-context analysis across the entire microservices architecture.

**Gemini Usage Instructions for Claude:**

* **Codebase Reviews:** Use the Gemini CLI to analyze all services (`/services/**`) simultaneously when checking for architectural drift or Kafka schema consistency.
* **Log Analysis:** If a data pipeline error occurs, pipe the output of `docker-compose logs` to Gemini for root-cause analysis across multiple containers.
* **ML/NLP Strategy:** Delegate complex prompt engineering or NLP model selection logic (for `ml-service`) to Gemini, as it can reference a larger corpus of documentation.

**Integration Commands:**

* Analyze all services: `gemini analyze ./services`
* Explain pipeline flow: `gemini "Explain the data flow from ingest-service to Elasticsearch in this repo"`

---

## Development Workflow

### 1. Setup (one time)

```powershell
scripts/dev/setup/setup.ps1
```

Creates Python virtual environments for every service, installs dependencies,
downloads spaCy models, verifies Python/Docker/.env.

### 2. Start Infrastructure

```powershell
scripts/dev/infrastructure/start-infra.ps1
```

Starts PostgreSQL, Kafka, Elasticsearch via `docker-compose.yml`.
Equivalent: `docker compose up -d` (docker-compose.yml is now infra-only).

### 3. Start Services

Choose one:

```powershell
# All services (separate terminals)
scripts/dev/backend/start-all.ps1

# Or start a single service:
scripts/dev/backend/start-energy.ps1
scripts/dev/backend/start-ml-platform.ps1
scripts/dev/backend/start-ingest.ps1
```

Each script activates the service's virtual environment, sets PYTHONPATH,
and starts uvicorn with `--reload` on the correct port.

### 4. Start Frontend

```powershell
scripts/dev/frontend/start-frontend.ps1
```

### 5. Stop

```powershell
scripts/dev/infrastructure/stop-infra.ps1
```

### Consumer Processes

Run in separate terminals with PYTHONPATH set:

```powershell
cd services/ml-service
$env:PYTHONPATH = "C:\path\to\repo"
.venv\Scripts\python consumer.py
```

### VS Code Debugging

Open `.vscode/launch.json` — debug configurations for all 7 services.
Select a service from the Run dropdown and press F5. Breakpoints, hot reload,
and environment variables are pre-configured.

### Production Deployment

```bash
docker compose -f docker-compose.full.yml up --build -d
```

### Research

```bash
cd research
pip install -r requirements-research.txt
python datasets/fetch_data.py
jupyter notebook
```

### Trigger Data Pipeline

```bash
curl http://localhost:8001/fetch-real-news
```

## Configuration Notes

* Kafka auto-creates topics, no manual setup needed
* PostgreSQL credentials: `admin/admin123`, database: `defenseintel`
* Elasticsearch runs with security disabled (single-node dev mode)
* All services communicate over the `proxy_net` Docker bridge network
* The frontend lives under `services/frontend/` and is served through the Docker Compose frontend service
* Energy schema is in `energy.` namespace — coexists with `public` schema from `init.sql`
* Seed data loads only when `ENERGY_LOAD_SEED=1` is set; safe to re-run (upserts on slug)
* No PostGIS available — lat/lng stored as DOUBLE PRECISION, GeoJSON in JSONB column
* No SQLAlchemy ORM — raw asyncpg queries due to PostgreSQL-specific features (ENUMs, JSONB, GIN)
* ML Platform in `ml.` schema — auto-created on startup via `ml_schema.sql`
* MLflow tracking URI configurable via `MLFLOW_TRACKING_URI` env var (default: `file:./mlruns`)
* DVC remote configurable via `DVC_REMOTE` env var (default: `./data/dvc-store`)
* Research notebooks use `research/datasets/fetch_data.py` to pull data — never run inside Docker
* **Dependency separation**: `services/ml-platform/requirements.txt` (production inference) vs `research/requirements-research.txt` (full experimentation stack)
* Production Docker installs **only** `requirements.txt` — no mlflow, dvc, shap, optuna, lightgbm, jupyter, or visualization packages
* Baseline models: LogReg, DecisionTree, RandomForest, XGBoost, LightGBM — no deep learning
* All training runs logged to MLflow with params, metrics, dataset version, feature version, git commit hash

---
