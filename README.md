# ProxyDefence

Military-grade cyber defense intelligence platform with event-driven microservices architecture. Ingests news → processes via ML/NLP → stores in PostgreSQL + Elasticsearch → serves to a React frontend via FastAPI.

## Architecture

```
GNews API → ingest-service → Kafka (raw_articles)
                          → ml-service → Kafka (processed_articles)
                                         → database-service → PostgreSQL + Elasticsearch
                                                              → modular-api → Frontend

Energy Service (port 8006) → PostgreSQL (energy schema)
ML Platform (port 8007)    → PostgreSQL (ml schema) → prediction API
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
| **ingest-service** (8001) | Fetches news from GNews API, publishes to Kafka |
| **ml-service** (8002) | NLP processing (sentiment, entities, topics, threats) |
| **database-service** (8003) | Kafka consumer → PostgreSQL + Elasticsearch |
| **embedding-service** (8005) | Kafka consumer → pgvector |
| **modular-api** (8000) | REST gateway with 15 domain routers, AI Copilot, RAG |
| **energy-service** (8006) | Infrastructure catalog (14 entities), risk intelligence, digital twin, SPR, procurement |
| **ml-platform** (8007) | Dataset builder, feature store, model training/registry, prediction API |

## Key Documentation

| Document | Contents |
|----------|----------|
| `docs/ARCHITECTURE.md` | Full architecture reference (15 parts, 12 sequence diagrams) |
| `docs/AI_ARCHITECTURE.md` | AI Copilot agent architecture (Supervisor/Intelligence, RAG, reasoning, confidence) |
| `docs/DATABASE_GUIDE.md` | Schema documentation (7 schemas, 75+ tables) |
| `docs/LOCAL_DEVELOPMENT.md` | Development setup walkthrough |
| `docs/SERVICE_GUIDE.md` | Per-service configuration details |

## Stack

- **Backend**: Python 3.12, FastAPI, asyncpg, Kafka 7.4, Elasticsearch 8.11
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts
- **ML**: spaCy, scikit-learn, XGBoost, LightGBM, MLflow, DVC
- **Infrastructure**: Docker Compose, PostgreSQL 15 + pgvector, Kafka 7.4 (3 partitions)
- **AI**: Groq (Llama 3.3 70B), Supervisor→Intelligence agent chain, hybrid RAG (vector+keyword+graph)
