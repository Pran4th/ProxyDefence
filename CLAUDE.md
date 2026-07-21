# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProxyDefence is an AI-driven energy supply-chain resilience platform for import-dependent economies (India-first). It turns live geopolitical signals into executable decisions: news → ML-scored disruption signals → corridor risk probabilities → digital-twin scenario impacts → SPR drawdown + procurement recommendations, chained by a Response Orchestrator whose per-stage latency is persisted to `energy.response_telemetry`. Event-driven microservices: news is ingested → processed by ML/NLP → stored in PostgreSQL and Elasticsearch → served to the React frontend (Command Center at `/command`) via FastAPI.

## Architecture

### Data Pipeline

```
GNews API → ingest-service → Kafka (raw_articles)
                          → ml-platform consumer → Kafka (processed_articles)
                                         → database-service → PostgreSQL + Elasticsearch
                                         → modular-api → Frontend

Energy Service (port 8006) → PostgreSQL (energy schema)
                          → Standalone catalog; risk_engine blends ML scores from ml-platform

ML Platform (port 8007) → PostgreSQL (ml schema)
                       → Consumes Energy Service data; serves prediction API
                       → Kafka consumer (consumer/article_enrichment.py) for article enrichment
                          (replaced ml-service/ml-consumer — see below)

Research (research/) → Jupyter notebooks → Exported models → ML Platform
                       (local, no Docker, pure experimentation)

```

### Service Ports

| Service | Port |
| --- | --- |
| Frontend (Vite dev) | 8080 |
| Ingest Service | 8001 |
| Database Service | 8003 |
| Embedding Service | 8005 |
| Modular API | 8000 |
| Energy Service | 8006 |
| ML Platform | 8007 |
| Kafka | 9092 |
| PostgreSQL | 5434 (not 5432 — see Configuration Notes) |
| Elasticsearch | 9200 |

### Microservices

**ingest-service** (`services/ingest-service/`)

* FastAPI service that fetches news from GNews API
* Publishes raw articles to `raw_articles` Kafka topic
* Trigger via `GET /fetch-real-news` endpoint

**ml-platform's Kafka consumer** (`services/ml-platform/consumer/article_enrichment.py`) — replaces `services/ml-service/`

* `services/ml-service/` (the old `ml-service` + `ml-consumer` container pair) is retired. ml-platform now performs article enrichment directly, reusing `backend.shared.kafka.ConsumerRunner`/`JsonProducer` (no new shared infra needed — just added `confluent-kafka` to ml-platform's requirements.txt).
* Subscribes to `raw_articles`, publishes to `processed_articles` with the **exact same schema** the old consumer produced (`topic`, `sentiment`, `threat_score`, `geopolitical_risk`, `risk_level`, `entities`, `relationships`, `keywords`, `content_hash`, `dedupe_key`) — `database-service` needed zero changes.
* Real transformer sentiment (DistilBERT) + NER (BERT-large + spaCy fallback) migrated verbatim from the old `ml_core/` package (`services/ml-platform/consumer/ml_core/`) — these were already legitimate ML, just relocated for single-source-of-truth.
* **Topic classification replaced**: was pure keyword-counting (`ml_core/topic.py`, and had a real bug — `max(scores, ..., default=("war",0))` meant any topic-neutral article silently defaulted to "war"). Now a trained XGBoost classifier (`scripts/train_topic_classifier.py`) over TF-IDF of GDELT GKG headline-slug text, proxy-labeled via GDELT's own theme taxonomy grouped into the same 5 categories (war/diplomacy/economics/cyber/general). Verified in a live parallel-run against real Kafka traffic: correctly classifies topic-neutral content as "general" where the old system defaulted to "war".
* **Threat scoring upgraded**: keyword formula blended (0.4 weight, same pattern as `risk_engine.py`) with a live call to ml-platform's own `/api/v1/risk/disruption-score` (the trained `gdelt-disruption-risk-classifier`), giving calibrated rather than keyword-saturating threat scores.
* Parallel-run validation (both consumers run against real Kafka, side-by-side comparison) is the standard rollout pattern for future consumer changes — don't cut over without it.

**database-service** (`services/database-service/`)

* FastAPI service that consumes from `processed_articles` topic
* Stores articles in PostgreSQL `processed_articles` table
* Indexes articles in Elasticsearch `processed_articles` index
* Provides REST endpoints: `/api/articles`, `/api/analytics/summary`, `/api/search`, `/api/articles/{article_id}`

**energy-service** (`services/energy-service/`)

* FastAPI microservice — authoritative infrastructure catalog **and intelligence engine** for the energy domain
* 14 entity types: locations, organizations, commodities, ports, oil_fields, gas_fields, pipelines, refineries, power_plants, storage_facilities, strategic_petroleum_reserves, import_corridors, shipping_routes, suppliers
* Dual identifiers (BIGSERIAL+UUID), soft delete, data provenance on every record
* Standardized filtering contract (search, sort, status, criticality, org, location, tag)
* Bulk import supporting JSON, CSV, GeoJSON format detection
* Idempotent seed data covering 20+ countries, 25 ports, 17 refineries, pipelines, oil fields, chokepoints, shipping routes, 7 SPRs, 9 suppliers with supplier_intelligence
* Tables live in `energy.` schema, auto-created on startup via `energy_schema.sql`
* Seed data enabled via `ENERGY_LOAD_SEED=1` env var
* REST API at `/api/v1/energy/` (catalog) and `/api/v1/intelligence/` (risk/signals/scenarios)

**Intelligence modules inside energy-service** (`services/energy-service/services/`) — these are BUILT, not future work:

* `risk_engine.py` (~700 lines) — multi-dimension risk scoring (geopolitical/operational/economic/environmental), disruption signals, chokepoint risk factors; persists to `energy.risk_scores`. **Blends formula scores with the trained ML classifier via MLBridge** (`ML_BLEND_WEIGHT=0.4`); API responses include an `ml` block with model version and both scores.
* `ml_bridge.py` — calls ML Platform `POST /api/v1/risk/disruption-score` (trained GDELT classifier); rule-based fallback if the platform is down. `ML_PLATFORM_URL` env var (local dev: `http://127.0.0.1:8007`). Also `RiskPropagator` for graph-based risk propagation.
* `digital_twin/` — engine (378 lines), network flow (299), graph (386), scenarios (231) incl. Hormuz partial/full closure, Red Sea suspension, OPEC+ cut, Jamnagar refinery fire
* `procurement/` — optimizer (composite scoring + Pareto frontier), orchestrator (526 lines), spr_engine (851 lines), crude-grade compatibility, supplier_intel. `supplier_intelligence` rows are enriched with REAL signals (OFAC sanction counts, GDELT escalation rates) by `ml-platform/scripts/build_procurement_dataset.py --enrich`.

**ml-platform** (`services/ml-platform/`)

* Production ML Platform — dataset building, feature engineering, model training, experiment tracking, model registry, prediction API, **and the article-enrichment Kafka consumer** (see Microservices section above — replaces the old ml-service)
* 41 tables in `ml.` schema (datasets, dataset_catalog, model_versions, predictions, leaderboard, dataset_validations, dataset_profiles, feature store, drift, governance, research, ...)
* Data acquisition layer: 23 registered sources across 7 categories (GDELT, EIA, FRED, OPEC, AIS, OFAC/UN sanctions, commodities, Comtrade, World Bank, Kaggle) with real per-source parsers; file-based data lake rooted at `DATASET_DIR` (repo `datasets/` folder). EIA and AIS are now live (keys in `.env`); NGA World Port Index remains blocked. Status documented in `datasets/DATA_SOURCE_STATUS.md`.
* CLI: `python cli/main.py {list|download|parse|register|gdelt|build_dataset|info|...}` — run from `services/ml-platform` with `PYTHONPATH="<repo>;<repo>/services/ml-platform"` and `POSTGRES_*` env
* **Registered & validated datasets** (`ml.dataset_catalog`, ~330k records, 20 sources): ofac-sanctions, eu-sanctions, opensanctions, global-ports, global-fuel-prices (USD-normalized via World Bank FX), 5 GEM infrastructure sets, gdelt-events, procurement-options, spr-drawdown-schedules, eia-crude-stocks (weekly US crude/SPR stock levels, national + PADD regions), crude-price-api (live Brent spot + forecasts), ais-chokepoints (real-time vessel positions near Hormuz/Bab-el-Mandeb/Malacca/Suez/Gibraltar/Bosphorus/Panama), india-crude-imports (multi-year 2021-2024, real Russia supply-shift signal), country-energy-indicators, brent-daily/wti-daily (FRED). Run `scripts/validate_all_datasets.py` to regenerate quality reports (mean quality score 0.910; flattens the canonical `attributes` JSON column before validating — raw-column validation is nearly a no-op on this schema).
* Model registries in `training/models.py`: classification (LogReg, DT, RF, XGBoost, LightGBM), regression (Ridge, RF, XGBoost), ranking (XGBRanker). `ModelTrainer(task="classification"|"regression")`
* **Trained production models** (`ml.model_versions`, artifacts in `data/artifacts/`, all Optuna-tuned via `scripts/tune_and_promote.py`): `gdelt-disruption-risk-classifier` (XGB, val AUC 0.734), `procurement-option-ranker` (XGB regressor, val R² 0.336), `fuel-price-forecaster` (val R² 0.377, beats persistence baseline), `brent-shock-forecaster` (val R² 0.223), `article-topic-classifier` (XGB over TF-IDF, 5-class incl. "general", beats naive baseline by +18pp — see article-enrichment consumer notes above)
* **Leaderboard**: `GET /api/v1/ml/research/leaderboard` (`routers/research_leaderboard.py`) — real, DB-backed via `research/leaderboard/board.py::Leaderboard`, persists to `ml.leaderboard`. Run `scripts/generate_benchmark_report.py` to populate it from `ml.model_versions` and write reports to `data/reports/`.
* Training/build scripts in `scripts/`: train_risk_classifier.py, build_procurement_dataset.py (--enrich updates energy.supplier_intelligence), train_procurement_ranker.py, train_price_forecaster.py, train_brent_shock_model.py, train_topic_classifier.py, optimize_spr_drawdown.py (scipy LP), tune_and_promote.py (Optuna), validate_all_datasets.py, generate_benchmark_report.py
* Risk serving endpoint for energy-service: `POST /api/v1/risk/disruption-score` (`routers/risk.py`) — builds the classifier's 98-col feature vector from high-level signals (country, tone, media volume)
* Generic prediction API: `POST /api/v1/ml/predict` (production-stage lookup by model name)
* MLflow tracking (needs `MLFLOW_ALLOW_FILE_STORE=true` with mlflow>=3), model lifecycle: development → validation → staging → production → archived
* Consumes from Energy Service; consumed by energy-service risk engine via ml_bridge; consumes `raw_articles` / produces `processed_articles` via `consumer/article_enrichment.py`

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
* **MapLibre GL** for the real geospatial map (`pages/EnergyMap.tsx`) — CARTO dark raster basemap (free, no key), chokepoints/ports/refineries/SPRs as GeoJSON circle layers, click-to-inspect
* Lucide React for icons
* Axios for API calls to modular-api (energy routes are JWT-protected; login via `/auth`)

**Frontend API client** (`frontend/src/lib/api.ts`):

* Uses `VITE_API_URL` env var, defaults to `http://localhost:8000`
* Key functions: `fetchArticles()`, `fetchAnalyticsSummary()`

---

## AI Collaboration (Gemini Integration)

This project uses a "Multi-Model" approach. While Claude handles code generation and refactoring, **Gemini 1.5/2.0** is used for high-context analysis across the entire microservices architecture.

**Gemini Usage Instructions for Claude:**

* **Codebase Reviews:** Use the Gemini CLI to analyze all services (`/services/**`) simultaneously when checking for architectural drift or Kafka schema consistency.
* **Log Analysis:** If a data pipeline error occurs, pipe the output of `docker-compose logs` to Gemini for root-cause analysis across multiple containers.
* **ML/NLP Strategy:** Delegate complex prompt engineering or NLP model selection logic (for `ml-platform`'s article-enrichment consumer) to Gemini, as it can reference a larger corpus of documentation.

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
cd services/ml-platform
$env:PYTHONPATH = "C:\path\to\repo;C:\path\to\repo\services\ml-platform"
.venv\Scripts\python consumer/article_enrichment.py
```

### VS Code Debugging

Open `.vscode/launch.json` — debug configurations for all services.
Select a service from the Run dropdown and press F5. Breakpoints, hot reload,
and environment variables are pre-configured.

### Production Deployment

AWS EC2, venv-based — mirrors local dev exactly (infra via `docker compose up -d`,
services in venvs under systemd, frontend built + served by nginx). There is
deliberately **no app-in-Docker build** (torch makes ml-platform's image slow and
fragile). Full runbook: `docs/05_DEPLOYMENT.md`.

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

## Testing & Validation

**pytest suites** (all passing — 132 in `services/modular-api`'s scope, 1033 in `services/ml-platform`'s):

```powershell
# Unit + integration (modular-api's venv; needs the full stack up for --run-integration)
$env:PYTHONPATH = "C:\path\to\repo"
services/modular-api/.venv/Scripts/python.exe -m pytest tests/unit tests/integration -q --run-integration

# ml-platform's own suite (separate venv — has numpy/pandas/xgboost/confluent-kafka)
$env:PYTHONPATH = "C:\path\to\repo;C:\path\to\repo\services\ml-platform"
services/ml-platform/.venv/Scripts/python.exe -m pytest services/ml-platform -q
```

`tests/integration` is skipped by default (`use --run-integration to include`) since it needs
live PG/ES/Kafka. Most integration tests use a mocked `pg_pool`/`es_client` (`async_client`
fixture in `tests/conftest.py`); `test_auth_api.py` uses a real DB connection instead
(`live_client` fixture) because register/login genuinely need INSERT...RETURNING /
uniqueness-constraint round trips a generic mock can't simulate. If you add tests that
`importlib.reload()` `backend.shared.settings`/`config` under monkeypatched env vars, know
that module objects are process-wide singletons — the `_restore_shared_modules_after_reload`
autouse fixture reloads them back to real values after each test so pollution doesn't leak
into tests that run afterward in the same session; extend its module list if you reload
something new.

**End-to-end validation framework** (`validation/`, standalone — not pytest):

```powershell
$env:PYTHONPATH = "C:\path\to\repo"
services/modular-api/.venv/Scripts/python.exe -m validation.runner            # everything
services/modular-api/.venv/Scripts/python.exe -m validation.runner --list     # categories
services/modular-api/.venv/Scripts/python.exe -m validation.runner -c services  # one category
```

Hits every live service over real HTTP/DB/ES/Kafka (10 categories: infrastructure, services,
data_pipeline, datasets, feature_store, model_registry, inference, ai_layer, gdelt, frontend)
and writes `validation_report.{json,html}`. Registers/logs in as a dedicated
`validation-suite@proxydefence-test.io` account (`validation/auth.py`) to get a Bearer token
for protected routes — needs the full stack running first. The `ai_layer` category exercises
the real LLM (Groq) end-to-end, so heavy repeated runs can trip Groq's free-tier rate limit;
that surfaces as a clean `503 LLM_RATE_LIMITED` response now, not a crash.

## Configuration Notes

* Kafka auto-creates topics, no manual setup needed
* **PostgreSQL runs on host port 5434** (5432 is occupied by another project on this machine) — `POSTGRES_PORT=5434` in `.env`, container `postgres-db`, credentials from `.env` (`admin/change-me`), database: `defenseintel`
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
