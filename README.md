# ProxyDefence

AI-driven energy supply-chain resilience platform for import-dependent economies, starting with India. It turns geopolitical and logistics inputs into reviewable decision support: news is ingested → ML-scored into disruption signals → corridor risk probabilities → digital-twin scenario impacts → SPR drawdown and procurement recommendations, with each response's latency and evidence persisted.

Event-driven microservices: news → Kafka → ML enrichment → PostgreSQL/Elasticsearch → FastAPI gateway → React command center.

## Architecture

```
GNews/NewsData → ingest-service → Kafka (raw_articles)
                               → ml-platform consumer → Kafka (processed_articles)
                                              → database-service → PostgreSQL + Elasticsearch
                                                                   → modular-api → Frontend

Energy Service (port 8006) → risk engine · corridor risk · digital twin · SPR · procurement
                           → Response Orchestrator (signal → recommendation, telemetry-tracked)
ML Platform (port 8007)    → trained models over public/derived datasets → prediction API
```

### Service Ports

| Service | Port |
|---------|------|
| Frontend (Vite) | 8080 |
| Modular API | 8000 |
| Ingest Service | 8001 |
| Database Service | 8003 |
| Embedding Service | 8005 |
| Energy Service | 8006 |
| ML Platform | 8007 |
| Kafka | 9092 |
| PostgreSQL | 5434 |
| Elasticsearch | 9200 |

## Quick Start

For the reproducible public pilot path, use:

```powershell
scripts/demo/start-pilot.ps1
```

For development, start the services individually:

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
| `docs/08_PILOT_DEMO_RUNBOOK.md` | Reproducible pilot demo and recording runbook |
| `docs/09_PILOT_PACKAGE.md` | Design-partner and YC positioning package |
| `docs/10_PUBLIC_DEMO_PROFILE.md` | Public Jamnagar demo profile and source boundaries |
| `docs/11_CODEBASE_GUIDE.md` | System-level codebase guide and operating model |
| `docs/12_BUSINESS_CASE.md` | Business problem, demonstrated evidence, and claim boundaries |
| `docs/13_SECURITY_AND_VALIDATION.md` | Security posture, deployment gates, and validation commands |
| `docs/14_FOUNDING_ENGINEER_INTERVIEW_PLAYBOOK.md` | Founding-engineer interview preparation tailored to ProxyDefence |
| `docs/15_HACKATHON_WINNING_PLAYBOOK.md` | Final pitch, demo, judging, video, and Q&A playbook for the energy-resilience challenge |

## Intelligence Source Status

The command center reports the mode and freshness of every decision input.
`live` means a connector has reported a current observation; `cached` is a
persisted snapshot; `replay` is a historical evaluation case; and `fallback`
or `disabled` means the input must not be treated as current intelligence.
Country-level sanctions aggregation is currently disabled, and AIS is a
persisted collector snapshot until a continuous connector is deployed.

## Stack

- **Backend**: Python 3.12, FastAPI, asyncpg, Kafka 7.4, Elasticsearch 8.11
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts
- **ML**: spaCy, scikit-learn, XGBoost, LightGBM, MLflow, DVC
- **Infrastructure**: Docker Compose, PostgreSQL 15 + pgvector, Kafka 7.4 (3 partitions)
- **AI**: Groq (Llama 3.3 70B), Supervisor→Intelligence agent chain, hybrid RAG (vector+keyword+graph)
