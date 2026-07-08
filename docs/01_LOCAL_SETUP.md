# Local Development Setup

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop
- VS Code (recommended)

## Quick Start

```powershell
# 1. Clone and enter the repo
git clone <repo-url>
cd ProxyDefence

# 2. One-time setup (creates venvs, installs deps)
scripts/dev/setup/setup.ps1

# 3. Edit environment variables
# Edit .env with your credentials (NEWS_API_KEY, etc.)

# 4. Start infrastructure (PostgreSQL, Kafka, Elasticsearch)
scripts/dev/infrastructure/start-infra.ps1

# 5. Start all backend services (opens multiple terminals)
scripts/dev/backend/start-all.ps1

# 6. Start frontend
scripts/dev/frontend/start-frontend.ps1
```

## Manual Setup

### Python Virtual Environments

Each service has its own `.venv`:

```powershell
# Example: setting up energy-service
cd services/energy-service
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Environment Variables

The `.env` file in the repo root is the single source of truth.
All services read from it via `os.getenv()`. Copy from `.env.example`:

```powershell
cp .env.example .env
# Edit .env with your credentials
```

### Starting a Single Service

```powershell
cd services/energy-service
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
.venv\Scripts\uvicorn app:app --host 0.0.0.0 --port 8006 --reload
```

### Service Ports

| Service | Port | Uvicorn Module |
|---------|------|----------------|
| Ingest Service | 8001 | app:app |
| ML Service | 8002 | app:app |
| Database Service | 8003 | app:app |
| Embedding Service | 8005 | app:app |
| Energy Service | 8006 | app:app |
| ML Platform | 8007 | app:app |
| Modular API | 8000 | backend.api_service.main:app |
| Frontend (Vite) | 8080 | npm run dev |

## Linux/macOS

Equivalent `.sh` scripts exist alongside every `.ps1` script:

```bash
./scripts/dev/setup/setup.sh
./scripts/dev/infrastructure/start-infra.sh
./scripts/dev/frontend/start-frontend.sh
```
