# ProxyDefence Startup Runbook

**Goal:** Get the entire platform running on a clean machine in under 15 minutes.

---

## Prerequisites

- **Docker Desktop** (v28+) - https://docs.docker.com/desktop/setup/install/windows-install/
- **Python 3.10+** - https://www.python.org/downloads/
- **Node.js 18+** - https://nodejs.org/
- **Git** - https://git-scm.com/
- **PowerShell 5.1+** (built into Windows 10/11)

---

## Quick Start (3 commands)

```powershell
# 1. Clone and setup
git clone <repo-url> ProxyDefence
cd ProxyDefence
.\scripts\dev\setup\setup.ps1

# 2. Start infrastructure
.\scripts\dev\infrastructure\start-infra.ps1

# 3. Start everything
.\scripts\dev\backend\start-all.ps1
.\scripts\dev\frontend\start-frontend.ps1
```

---

## Step-by-Step

### 1. Clone Repository

```powershell
git clone <repo-url> ProxyDefence
cd ProxyDefence
```

### 2. Configure Environment

```powershell
# Copy example env (if .env doesn't exist)
copy .env.example .env
```

Edit `.env` with your actual values:

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `OPENAI_API_KEY` | **YES** | (none) | Get a Groq key from https://console.groq.com/keys |
| `OPENAI_BASE_URL` | YES | `https://api.groq.com/openai/v1` | Keep default for Groq; change for other providers |
| `LLM_DEFAULT_MODEL` | YES | `llama-3.3-70b-versatile` | Default model; check `groq models list` for available |
| `LLM_FALLBACK_MODEL` | YES | `llama-3.1-8b-instant` | Fallback on rate-limit/errors |
| `NEWS_API_KEY` | YES | (none) | Get from https://gnews.io/ |
| `POSTGRES_PASSWORD` | YES | `change-me` | Change for production |
| `JWT_SECRET_KEY` | YES | `change-me` | Change for production |
| `ELASTIC_PASSWORD` | YES | `change-me` | Change for production |

### 3. Setup Virtual Environments

```powershell
.\scripts\dev\setup\setup.ps1
```

This creates .venv for each service and installs dependencies.

**Manual alternative** (if setup script fails):

```powershell
# For each service in services/*/
cd services/<service-name>
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# Also install shared deps for modular-api
.venv\Scripts\pip install openai tiktoken
```

### 4. Start Infrastructure

```powershell
.\scripts\dev\infrastructure\start-infra.ps1
```

This runs `docker compose up -d` which starts:

| Container | Port | Health Check |
|-----------|------|-------------|
| postgres-db | 5432 | `pg_isready -U admin -d defenseintel` |
| kafka | 9092 | `kafka-topics --list` |
| elasticsearch | 9200 | `curl localhost:9200/_cluster/health` |
| zookeeper | 2181 | Internal (Kafka dependency) |

**Verify infrastructure:**

```powershell
docker compose ps
```

Expected: All 4 containers show "Up" and "(healthy)".

**Database initialization:** On first startup, PostgreSQL runs `infra/sql/init.sql` which creates all tables in the `public` schema. Additional schemas are created by each service on startup.

### 5. Wait for Database Schema Creation

```powershell
# Wait for tables to exist (5-10 seconds after first start)
docker exec postgres-db psql -U admin -d defenseintel -c "\dt public.*" 2>$null
```

Expected output: 22 tables listed.

### 6. Start Backend Services

**Quick method** (opens separate windows):

```powershell
.\scripts\dev\backend\start-all.ps1
```

**Manual method** (one service at a time):

```powershell
# Terminal 1: Modular API (primary REST gateway)
.\scripts\dev\backend\start-modular-api.ps1

# Terminal 2: Energy Service
.\scripts\dev\backend\start-energy.ps1

# Terminal 3: ML Platform
.\scripts\dev\backend\start-ml-platform.ps1

# Terminal 4: Pipeline Services
.\scripts\dev\backend\start-ingest.ps1
.\scripts\dev\backend\start-ml.ps1
.\scripts\dev\backend\start-embedding.ps1
.\scripts\dev\backend\start-database.ps1
```

### 7. Start Kafka Consumers

```powershell
.\scripts\dev\backend\start-consumers.ps1
```

This starts 3 consumer processes:
- `ml-consumer` - transforms raw articles (sentiment, entities, topics)
- `embedding-consumer` - generates vector embeddings
- `db-consumer` - stores in PostgreSQL + Elasticsearch

### 8. Verify Services Are Healthy

```powershell
# Health checks for all services
curl http://localhost:8000/health     # Modular API
curl http://localhost:8006/health     # Energy Service
curl http://localhost:8007/health     # ML Platform
curl http://localhost:8001/health     # Ingest Service
curl http://localhost:8002/health     # ML Service
curl http://localhost:8005/health     # Embedding Service
curl http://localhost:8003/health     # Database Service
```

Expected: All return `{"status":"healthy",...}`.

### 9. Ingest News Data

```powershell
# Trigger news fetch from GNews API -> Kafka
curl http://localhost:8001/fetch-real-news
```

This fetches 10 articles and publishes to `raw_articles` Kafka topic. The pipeline then:
1. ML service consumes → sentiment/entity/topic analysis → `processed_articles`
2. Database service consumes → stores in PostgreSQL + indexes in Elasticsearch
3. Embedding service consumes → generates vector embeddings

### 10. Seed Energy Data

```powershell
# Energy data loads automatically if ENERGY_LOAD_SEED=1 in .env
# Verify seed data:
curl http://localhost:8006/api/v1/energy/locations
curl http://localhost:8006/api/v1/energy/organizations
```

### 11. Start Frontend

```powershell
.\scripts\dev\frontend\start-frontend.ps1
```

This starts Vite dev server on port 8080.

**Prod build (alternative):**

```powershell
cd services/frontend
npm run build
npx serve -s dist -l 8080
```

### 12. Run Smoke Tests

```powershell
# Auth test
curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d "{\"email\":\"test@test.com\",\"username\":\"test\",\"password\":\"Test1234!\"}"
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"email\":\"test@test.com\",\"password\":\"Test1234!\"}"

# Health check
curl http://localhost:8000/health

# Articles
curl http://localhost:8000/articles/ -H "Authorization: Bearer <token>"

# Analytics
curl http://localhost:8000/analytics/summary -H "Authorization: Bearer <token>"
```

---

## Shutdown Order

```powershell
# 1. Stop frontend (Ctrl+C in its terminal window)

# 2. Stop backend services (Ctrl+C in each terminal window, or:)
.\scripts\dev\stop-local.ps1

# 3. Stop infrastructure
.\scripts\dev\infrastructure\stop-infra.ps1

# Or stop everything at once:
docker compose down
```

---

## Recovery From Failures

### Issue: Infrastructure won't start
```powershell
# Check port conflicts
netstat -ano | findstr ":5432 :9092 :9200"

# Reset infrastructure
docker compose down -v
.\scripts\dev\infrastructure\start-infra.ps1
```

### Issue: PostgreSQL fails on startup
```powershell
# Check logs
docker logs postgres-db

# Common fix: remove corrupted data volume
docker compose down -v
.\scripts\dev\infrastructure\start-infra.ps1
```

### Issue: Kafka topic missing
```powershell
# Topics auto-create on first produce, but verify:
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Create manually if needed:
docker exec kafka kafka-topics --create --topic raw_articles --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
docker exec kafka kafka-topics --create --topic processed_articles --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

### Issue: Service won't start (ModuleNotFoundError)
```powershell
# Activate venv and install missing packages
cd services/<service-name>
.venv\Scripts\pip install <missing-package>
```

### Issue: Database tables missing
```powershell
# Run schema bootstrap
cd services/<service-name>
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
.venv\Scripts\python -c "from backend.shared.schema_bootstrap import ensure_all_schemas; import asyncio; asyncio.run(ensure_all_schemas())"
```

### Issue: Elasticsearch not indexed
```powershell
# Check ES status
curl -u elastic:<password> http://localhost:9200/_cat/indices?v

# Force reindex by triggering database consumer
```

### Issue: AI/Copilot not working
```powershell
# Verify OPENAI_API_KEY is set
$env:OPENAI_API_KEY
# If empty, add to .env file and restart modular-api
```

---

## Common Debugging Commands

```powershell
# Check all running docker containers
docker ps

# View container logs
docker logs <container-name>

# Check PostgreSQL
docker exec postgres-db psql -U admin -d defenseintel -c "SELECT COUNT(*) FROM processed_articles;"

# Check Kafka messages
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_articles --from-beginning --max-messages 3

# Check ES documents
curl -u elastic:<password> http://localhost:9200/processed_articles/_count

# Check port status
netstat -ano | findstr ":8000 :8001 :8002 :8003 :8005 :8006 :8007 :8080"

# Kill a hung process on a port
$pid = (netstat -ano | findstr ":8000 " | findstr LISTENING | % { $_ -replace '.*LISTENING\s+(\d+)', '$1' })
Stop-Process -Id $pid -Force

# Reset everything cleanly
docker compose down -v
Remove-Item -Recurse -Force services/*/.venv -ErrorAction SilentlyContinue
.\scripts\dev\setup\setup.ps1
```

---

## Architecture Reference

```
┌──────────────┐    Kafka Topics    ┌──────────────┐
│ingest-service│ ─── raw_articles ──▶│ ml-service   │
│ (port 8001)  │                    │ (port 8002)   │
└──────────────┘                    └──────┬───────┘
                                          │ processed_articles
                                    ┌─────┴──────────┐
                                    ▼                ▼
                            ┌──────────────┐ ┌──────────────┐
                            │db consumer   │ │embed consumer│
                            │→ PostgreSQL  │ │→ pgvector    │
                            │→ Elastic     │ │  embeddings  │
                            └──────────────┘ └──────────────┘
```

### Service Dependencies

```
postgres ─┬─ modular-api (8000)
          ├─ energy-service (8006)
          ├─ ml-platform (8007)
          ├─ database-service (8003)
          └─ embedding-service (8005)

elasticsearch ─┬─ modular-api (8000)
               └─ database-service (8003)

kafka ─┬─ ingest-service (8001) [producer]
       ├─ ml-service (8002) [consumer+producer]
       ├─ database-service (8003) [consumer]
       └─ embedding-service (8005) [consumer]
```

---

## Service Port Map

| Service | Port | Purpose |
|---------|------|---------|
| modular-api | 8000 | REST API gateway |
| ingest-service | 8001 | News ingestion |
| ml-service | 8002 | NLP processing |
| database-service | 8003 | DB + ES storage |
| embedding-service | 8005 | Vector embeddings |
| energy-service | 8006 | Energy domain catalog |
| ml-platform | 8007 | ML training/prediction |
| Frontend (dev) | 8080 | Vite dev server |
| Frontend (prod) | 3000 | Nginx production |
| PostgreSQL | 5432 | Primary database |
| Kafka | 9092 | Message broker |
| Elasticsearch | 9200 | Full-text search |
| Zookeeper | 2181 | Kafka coordination |

---

## Validation Script

Run this after startup to verify everything:

```powershell
# Save as validate.ps1 and run
$tests = @(
    @("Infrastructure", "docker ps", "postgres-db|kafka|elasticsearch"),
    @("Modular API", "curl -s http://localhost:8000/health", "healthy"),
    @("Energy Service", "curl -s http://localhost:8006/health", "healthy"),
    @("ML Platform", "curl -s http://localhost:8007/health", "healthy"),
    @("Articles", "curl -s http://localhost:8000/articles/ -H 'Authorization: Bearer <token>'", "items"),
    @("Analytics", "curl -s http://localhost:8000/analytics/summary -H 'Authorization: Bearer <token>'", "total_articles"),
    @("PostgreSQL", "docker exec postgres-db psql -U admin -d defenseintel -c 'SELECT COUNT(*) FROM processed_articles;'", "1 row"),
    @("Kafka", "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092", "raw_articles"),
    @("Elasticsearch", "curl -u elastic:change-me http://localhost:9200/", "8.11.0"),
)
```
