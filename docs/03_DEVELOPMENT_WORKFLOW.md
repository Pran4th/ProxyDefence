# Development Workflow

## Daily Workflow

### 1. Start Infrastructure

```powershell
scripts/dev/infrastructure/start-infra.ps1
```

This starts PostgreSQL, Kafka, Zookeeper, and Elasticsearch in Docker.
Wait for health checks to pass (~30 seconds).

### 2. Start Services

Choose one:

```powershell
# All services (separate windows)
scripts/dev/backend/start-all.ps1

# Or start individual services:
scripts/dev/backend/start-energy.ps1
scripts/dev/backend/start-ml-platform.ps1
```

### 3. Start Frontend

```powershell
scripts/dev/frontend/start-frontend.ps1
```

Opens at http://localhost:8080

### 4. Develop

- Edit code in VS Code
- `uvicorn --reload` automatically restarts on file changes
- Set breakpoints in VS Code for debugging
- Run tests with `scripts/testing/run-tests.ps1`

### 5. Stop

```powershell
scripts/dev/infrastructure/stop-infra.ps1
```

## Consumer Processes

Some services have background Kafka consumers:

| Consumer | Command |
|----------|---------|
| ml-consumer | `python services/ml-service/consumer.py` |
| embedding-consumer | `python services/embedding-service/consumer.py` |
| db-consumer | `python services/database-service/consumer.py` |

Run these in separate terminals with PYTHONPATH set:

```powershell
cd services/ml-service
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
.venv\Scripts\python consumer.py
```

## Environment Variables

The `.env` file in the repo root is the single source of truth.
Docker Compose and local scripts both read from it.
Never commit `.env` — it is gitignored.

Required variables:
```
POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
ELASTICSEARCH_PASSWORD, ELASTIC_PASSWORD
JWT_SECRET_KEY
KAFKA_BOOTSTRAP_SERVERS
```

## Service Configuration

Each service reads its configuration from environment variables.
No hardcoded credentials or URLs in any service.

| Service | Key Variables |
|---------|--------------|
| ingest-service | NEWS_API_KEY, KAFKA_BOOTSTRAP_SERVERS |
| ml-service | KAFKA_BOOTSTRAP_SERVERS |
| embedding-service | POSTGRES_*, KAFKA_BOOTSTRAP_SERVERS |
| database-service | POSTGRES_*, ELASTICSEARCH_*, JWT_* |
| modular-api | POSTGRES_*, ELASTICSEARCH_*, JWT_*, CORS_* |
| energy-service | POSTGRES_*, ENERGY_LOAD_SEED |
| ml-platform | POSTGRES_*, ENERGY_SERVICE_URL, MLFLOW_* |

## PYTHONPATH

All Python services import from `backend/shared/`.
You must set `PYTHONPATH` to the repo root when running locally:

```powershell
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
```

The startup scripts and VS Code launch configs handle this automatically.
