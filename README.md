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

Local Development Setup
This is the first-time setup guide for running ProxyDefence entirely on your own machine (no Docker for the app services — only infra runs in containers).

Prerequisites
Python 3.10+ (3.11 recommended, matches the Docker images)
Node.js 18+ (20+ recommended)
Docker Desktop (for PostgreSQL, Kafka, Elasticsearch)
Git
Windows: PowerShell 5.1+ (built in). macOS/Linux: bash.
1. Clone and get API keys
git clone <repo-url>
cd ProxyDefence
You'll need two external API keys before the pipeline can do anything real (the app starts without them, but ingestion and the AI copilot/agents will fail at call time):

GNews API key — free tier at https://gnews.io — sets NEWS_API_KEY. Without a real key, ingest-service fails every fetch with apikey=replace-me style 400 errors.
Groq API key — free tier at https://console.groq.com — sets OPENAI_API_KEY (yes, that variable name, even for Groq — it's read by an OpenAI-compatible SDK pointed at Groq's endpoint). Powers the copilot/agents/ RAG features in modular-api. Any other OpenAI-compatible provider works too — just change OPENAI_BASE_URL/LLM_DEFAULT_MODEL to match.

2. Create your .env
cp .env.example .env
Then edit .env:

Set NEWS_API_KEY and OPENAI_API_KEY to the real keys from step 1.
.env.example's committed defaults are tuned for the Docker network, not local dev — for a local (non-Docker services) setup, also change:

3. One-time dependency install
scripts/dev/setup/setup.ps1
This creates a separate .venv per Python service, installs each requirements.txt, downloads the spaCy model the ML-platform consumer needs, installs shared dev tooling (pytest, ruff, pyright), and installs pre-commit hooks. Safe to re-run; pass -Force to recreate all venvs from scratch.

(macOS/Linux: scripts/dev/setup/setup.sh, and use the .sh twin of every script below instead of .ps1.)

4. Start everything
scripts/dev/start-local.ps1
This is the one-command launcher: it pre-flight-checks your environment (Python/Node/Docker versions, .env exists, venvs exist), starts PostgreSQL/Kafka/Elasticsearch via docker compose, then starts all 6 API services, all 3 Kafka consumers, and the frontend — each gated on its port and health endpoint responding before moving to the next, so it fails fast with a diagnosis (last 50-100 log lines + a guessed failure category) instead of hanging. First run also does npm install for the frontend, so expect it to take a few minutes.

5. Verify it's working
scripts/dev/status.ps1
Shows health-endpoint status for every service plus infra port checks. Then:

Open http://localhost:8080 — the frontend should load and let you register/ log in. The landing page itself works even logged out (it calls a public, unauthenticated preview endpoint) — if it's blank, that's a real bug, not expected behavior.
curl http://localhost:8001/fetch-real-news — manually triggers a news fetch; should return fetched articles, not a replace-me API-key error.
curl http://localhost:8000/public/preview — should return real article previews + stats with no auth token. A 500 here almost always means Postgres or Elasticsearch isn't actually reachable (check .env ports).

6. Stopping
scripts/dev/stop-local.ps1
Stops all tracked service processes and (unless -SkipInfra) runs docker compose down.

Manual / single-service alternative
If you only need one service running (e.g. for focused debugging), you can start it directly instead of using start-local.ps1:

cd services/energy-service
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
.venv\Scripts\uvicorn app:app --host 127.0.0.1 --port 8006 --reload
Or use the per-service script, e.g. scripts/dev/backend/start-energy.ps1 (each one sources .env itself, so you don't need to set PYTHONPATH manually). Note this opens its own terminal window and does not redirect its logs to logs/ the way start-local.ps1's consumers do — expect to read its output directly in that window.


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
