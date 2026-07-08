# Local Development Guide

## Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Python | 3.11+ | `python --version` |
| Docker Desktop | Latest | `docker info` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| PowerShell | 5.1+ (Windows), 7+ (recommended) | `$PSVersionTable.PSVersion` |
| Git | Latest | `git --version` |

## Quick Start (From Scratch)

### 1. Clone the repository
```powershell
git clone <repo-url> ProxyDefence
cd ProxyDefence
```

### 2. Create .env file
```powershell
# Copy example if one exists, or create manually:
@"
NEWS_API_KEY=your_gnews_api_key_here
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123
POSTGRES_DB=defenseintel
ELASTIC_PASSWORD=changeme
ELASTICSEARCH_PASSWORD=changeme
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
"@ | Out-File -Encoding UTF8 .env
```

Get a free GNews API key at https://gnews.io.

### 3. Run setup script
```powershell
.\scripts\dev\setup\setup.ps1
```

This creates Python virtual environments for all 7 services, installs dependencies, and downloads the spaCy NLP model. Takes 3-10 minutes on first run.

### 4. Start infrastructure (PostgreSQL, Kafka, Elasticsearch)
```powershell
.\scripts\dev\infrastructure\start-infra.ps1
```

Wait for all containers to become healthy (usually 30-60 seconds).

### 5. Start all services
```powershell
.\scripts\dev\backend\start-all.ps1
# OR for a single service:
.\scripts\dev\backend\start-ingest.ps1
```

### 6. Start Kafka consumers (separate terminals)
```powershell
# Each in its own terminal:
.\scripts\dev\backend\start-consumers.ps1
```

### 7. Start frontend
```powershell
.\scripts\dev\frontend\start-frontend.ps1
```

### 8. Start everything at once (steps 4-7 combined)
```powershell
.\scripts\dev\start-local.ps1
```

### 9. Trigger the pipeline
```powershell
curl http://localhost:8001/fetch-real-news
```

## Port Reference

| Service | Port | URL |
|---------|------|-----|
| Modular API | 8000 | http://localhost:8000 |
| Ingest Service | 8001 | http://localhost:8001 |
| ML Service | 8002 | http://localhost:8002 |
| Database Service | 8003 | http://localhost:8003 |
| Embedding Service | 8005 | http://localhost:8005 |
| Energy Service | 8006 | http://localhost:8006 |
| ML Platform | 8007 | http://localhost:8007 |
| Frontend (Vite) | 8080 | http://localhost:8080 |
| PostgreSQL | 5432 | localhost:5432 |
| Kafka | 9092 | localhost:9092 |
| Elasticsearch | 9200 | http://localhost:9200 |

## Development Scripts

| Script | Purpose |
|--------|---------|
| `scripts/dev/start-local.ps1` | Start everything: infra + services + consumers + frontend |
| `scripts/dev/stop-local.ps1` | Stop everything gracefully |
| `scripts/dev/restart-local.ps1` | Restart all services (keeps infra) |
| `scripts/dev/status.ps1` | Check health of all services |
| `scripts/dev/logs.ps1` | View service logs |
| `scripts/dev/infrastructure/start-infra.ps1` | Start Docker containers |
| `scripts/dev/infrastructure/stop-infra.ps1` | Stop Docker containers |
| `scripts/dev/backend/start-all.ps1` | Start all API services (separate windows) |
| `scripts/dev/backend/start-consumers.ps1` | Start all Kafka consumers |
| `scripts/dev/frontend/start-frontend.ps1` | Start Vite dev server |
| `scripts/dev/setup/setup.ps1` | Initial setup (venvs, deps, spaCy) |

## Common Issues and Solutions

### "Port already in use"
Stop the conflicting service or change the port in the start script.

```powershell
# Find what's using a port
netstat -ano | findstr :8000
# Kill the process
taskkill /PID <pid> /F
```

### "Docker not detected"
Start Docker Desktop and wait for the whale icon to stop animating.

### ".venv not found"
Run `.\scripts\dev\setup\setup.ps1` to create virtual environments.

### "ModuleNotFoundError: backend.shared"
Ensure `PYTHONPATH` is set to the repo root. The start scripts do this automatically:
```powershell
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
```

### Kafka consumer not receiving messages
Check consumer group status:
```powershell
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group ml-service-group --describe
```
If lag is high, consumers may be down. Restart them.

### PostgreSQL connection refused
Wait for the container to become healthy:
```powershell
docker compose ps
# Or check logs:
docker compose logs postgres
```

### Elasticsearch not starting
Elasticsearch 8.11 requires increased virtual memory:
```powershell
# On Windows WSL2:
wsl -d docker-desktop sysctl -w vm.max_map_count=262144
```

### "Missing required environment variable"
Ensure `.env` exists in the repo root with all required variables.

### Virtual environment issues
```powershell
# Force recreate all venvs
.\scripts\dev\setup\setup.ps1 -Force
```

## VS Code Debugging

### Launch Configurations
Open the Run and Debug view (Ctrl+Shift+D). Pre-configured launch configurations exist in `.vscode/launch.json` for all 7 services:

| Configuration | Service |
|--------------|---------|
| `modular-api` | API Gateway (port 8000) |
| `ingest-service` | News Ingestion (port 8001) |
| `ml-service` | ML Processing (port 8002) |
| `database-service` | Database + ES (port 8003) |
| `embedding-service` | Embedding (port 8005) |
| `energy-service` | Energy Catalog (port 8006) |
| `ml-platform` | ML Platform (port 8007) |

### Debugging Steps
1. Set breakpoints in your code
2. Select the service from the Run dropdown
3. Press F5
4. The service starts with hot reload and breakpoints enabled
5. Environment variables are pre-configured

### Debugging a Kafka Consumer
Launch `consumer.py` from VS Code:
```json
{
    "name": "ml-consumer",
    "type": "python",
    "request": "launch",
    "program": "${workspaceFolder}/services/ml-service/consumer.py",
    "console": "integratedTerminal",
    "env": {"PYTHONPATH": "${workspaceFolder}"}
}
```

## Running Tests

### Unit Tests
```powershell
# Run all unit tests
python -m pytest tests/unit -v

# Run a specific test file
python -m pytest tests/unit/test_articles.py -v

# Run with coverage
python -m pytest tests/unit --cov=backend --cov-report=term-missing
```

### Integration Tests
```powershell
# Requires PostgreSQL + Elasticsearch running
python -m pytest tests/integration --run-integration -v
```

### All Tests
```powershell
python -m pytest tests/ -v
```

## Logs

Logs are written to the `logs/` directory when using `start-local.ps1`:

```powershell
# View all logs
.\scripts\dev\logs.ps1

# Tail a specific log
Get-Content logs\ingest-service.log -Tail 20 -Wait

# Search logs for errors
Select-String -Path logs\*.log -Pattern "error|exception|failed"
```

## Stopping Everything

```powershell
# Stop services + infrastructure
.\scripts\dev\stop-local.ps1

# Stop services only (keep infra running)
.\scripts\dev\stop-local.ps1 -SkipInfra
```

## Research Environment

```powershell
cd research
pip install -r requirements-research.txt
python datasets/fetch_data.py
jupyter notebook
```

Research notebooks are for experimentation only — never installed inside Docker containers.

## Makefile (Alternative)

A Makefile is provided at the repo root for Unix-like environments:
```bash
make setup          # Run setup.ps1
make infra-start    # Start Docker infrastructure
make start          # Start all services
make stop           # Stop all services
make status         # Check service health
make test           # Run all tests
make lint           # Run ruff linter
make format         # Run ruff formatter
```
