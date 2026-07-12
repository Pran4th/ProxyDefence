# ProxyDefence

AI-driven energy supply-chain resilience platform for import-dependent economies, starting with India. Turns live geopolitical signals into executable decisions: news is ingested → ML-scored into disruption signals → corridor risk probabilities → digital-twin scenario impacts → SPR drawdown and procurement recommendations, end to end in under a minute — with every stage's latency measured and persisted.

Event-driven microservices: news → Kafka → ML enrichment → PostgreSQL/Elasticsearch → FastAPI gateway → React command center.

## Architecture

```
GNews/NewsData → ingest-service → Kafka (raw_articles)
                               → ml-platform consumer → Kafka (processed_articles)
                                              → database-service → PostgreSQL + Elasticsearch
                                                                   → modular-api → Frontend

Energy Service (port 8006) → risk engine · corridor risk · digital twin · SPR · procurement
                           → Response Orchestrator (signal → recommendation, telemetry-tracked)
ML Platform (port 8007)    → 5 trained models over ~330k real records → prediction API
```

### Service Ports

| Service | Port |
|---------|------|
| Frontend (Vite) | 8080 |
| Modular API | 8000 |
| Ingest Service | 8001 |
| ML Service | 8002 |
| Database Service | 8003 |
| Embedding Service | 8005 |
| Energy Service | 8006 |
| ML Platform | 8007 |
| Kafka | 9092 |
| PostgreSQL | 5432 |
| Elasticsearch | 9200 |

## Quick Start

```powershell
# 1. One-time setup (Python venvs, spaCy models, dependencies)
scripts/dev/setup/setup.ps1

# 2. Start infrastructure (PostgreSQL, Kafka, Elasticsearch)
scripts/dev/infrastructure/start-infra.ps1

# 3. Start backend services (separate terminals)
scripts/dev/backend/start-all.ps1

# 4. Start frontend
scripts/dev/frontend/start-frontend.ps1

# 5. Trigger data pipeline
curl http://localhost:8001/fetch-real-news
```

### Single Service Development

```powershell
scripts/dev/backend/start-energy.ps1
scripts/dev/backend/start-ml-platform.ps1
scripts/dev/backend/start-ingest.ps1
```

## Services

| Service | Role |
|---------|------|
| **ingest-service** (8001) | Fetches news from GNews/NewsData APIs, publishes to Kafka |
| **database-service** (8003) | Kafka consumer → PostgreSQL + Elasticsearch |
| **embedding-service** (8005) | Kafka consumer → pgvector |
| **modular-api** (8000) | REST gateway with 15 domain routers, AI Copilot, RAG |
| **energy-service** (8006) | Infrastructure catalog (14 entities), risk intelligence, digital twin, SPR, procurement |
| **ml-platform** (8007) | Dataset builder, feature store, model training/registry, prediction API |

## Key Documentation

| Document | Contents |
|----------|----------|
| `docs/01_LOCAL_SETUP.md` | Development setup walkthrough |
| `docs/02_ARCHITECTURE.md` | Architecture reference |
| `docs/03_DEVELOPMENT_WORKFLOW.md` | Day-to-day dev workflow |
| `docs/04_DEBUGGING.md` | Debugging guide |
| `docs/05_DEPLOYMENT.md` | Deployment guide |
| `docs/06_ENVIRONMENT_VARIABLES.md` | Environment variable reference |

## Stack

- **Backend**: Python 3.12, FastAPI, asyncpg, Kafka 7.4, Elasticsearch 8.11
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts
- **ML**: spaCy, scikit-learn, XGBoost, LightGBM, MLflow, DVC
- **Infrastructure**: Docker Compose, PostgreSQL 15 + pgvector, Kafka 7.4 (3 partitions)
- **AI**: Groq (Llama 3.3 70B), Supervisor→Intelligence agent chain, hybrid RAG (vector+keyword+graph)
