# Local Development Setup

This is the first-time setup guide for running ProxyDefence entirely on your
own machine (no Docker for the app services — only infra runs in containers).

## Prerequisites

- Python 3.10+ (3.11 recommended, matches the Docker images)
- Node.js 18+ (20+ recommended)
- Docker Desktop (for PostgreSQL, Kafka, Elasticsearch)
- Git
- Windows: PowerShell 5.1+ (built in). macOS/Linux: bash.

## 1. Clone and get API keys

```powershell
git clone <repo-url>
cd ProxyDefence
```

You'll need two external API keys before the pipeline can do anything real
(the app *starts* without them, but ingestion and the AI copilot/agents will
fail at call time):

- **GNews API key** — free tier at https://gnews.io — sets `NEWS_API_KEY`.
  Without a real key, `ingest-service` fails every fetch with
  `apikey=replace-me` style 400 errors.
- **Groq API key** — free tier at https://console.groq.com — sets
  `OPENAI_API_KEY` (yes, that variable name, even for Groq — it's read by an
  OpenAI-compatible SDK pointed at Groq's endpoint). Powers the copilot/agents/
  RAG features in `modular-api`. Any other OpenAI-compatible provider works
  too — just change `OPENAI_BASE_URL`/`LLM_DEFAULT_MODEL` to match.

## 2. Create your `.env`

```powershell
cp .env.example .env
```

Then edit `.env`:
- Set `NEWS_API_KEY` and `OPENAI_API_KEY` to the real keys from step 1.
- **`.env.example`'s committed defaults are tuned for the Docker network,
  not local dev** — for a local (non-Docker services) setup, also change:
  - `ENERGY_SERVICE_URL=http://energy-service:8000` → `http://127.0.0.1:8006`
  - `EMBEDDING_SERVICE_URL=http://embedding-service:8000` → `http://127.0.0.1:8005`
  - `KAFKA_BOOTSTRAP_SERVERS=kafka:9092` → `127.0.0.1:9092`
  - `POSTGRES_HOST`/`ELASTICSEARCH_HOST` → `127.0.0.1` (or `localhost`)
  - `CORS_ORIGINS` must include the port the frontend actually runs on
    (`http://localhost:8080` — check `services/frontend/vite.config.ts` if
    that ever changes). A mismatched port here is a common first-run bug:
    the frontend loads but every API call fails with a CORS error in the
    browser console.
- Leave `ENERGY_LOAD_SEED=1` if you want the energy-domain demo data
  (20+ countries, ports, pipelines, refineries, etc.) seeded on first boot.

**Important:** if you edit `.env` while services are already running, you
must restart them — every service reads env vars once at process startup,
they are not hot-reloaded.

## 3. One-time dependency install

```powershell
scripts/dev/setup/setup.ps1
```

This creates a separate `.venv` per Python service, installs each
`requirements.txt`, downloads the spaCy model `ml-service` needs, installs
shared dev tooling (pytest, ruff, pyright), and installs pre-commit hooks.
Safe to re-run; pass `-Force` to recreate all venvs from scratch.

(macOS/Linux: `scripts/dev/setup/setup.sh`, and use the `.sh` twin of every
script below instead of `.ps1`.)

## 4. Start everything

```powershell
scripts/dev/start-local.ps1
```

This is the one-command launcher: it pre-flight-checks your environment
(Python/Node/Docker versions, `.env` exists, venvs exist), starts
PostgreSQL/Kafka/Elasticsearch via `docker compose`, then starts all 7 API
services, all 3 Kafka consumers, and the frontend — each gated on its port
and health endpoint responding before moving to the next, so it fails fast
with a diagnosis (last 50-100 log lines + a guessed failure category) instead
of hanging. First run also does `npm install` for the frontend, so expect it
to take a few minutes.

Useful flags: `-SkipInfra` (Postgres/Kafka/ES already running),
`-SkipFrontend`, `-SkipCleanup` (skip killing stray old processes / port
checks), `-Force` (non-interactive, auto-confirm prompts).

## 5. Verify it's working

```powershell
scripts/dev/status.ps1
```

Shows health-endpoint status for every service plus infra port checks. Then:

- Open http://localhost:8080 — the frontend should load and let you register/log in.
- `curl http://localhost:8001/fetch-real-news` — manually triggers a news
  fetch; should return fetched articles, not a `replace-me` API-key error.
- `scripts/dev/logs.ps1 -Follow` — tail all service logs merged together if
  anything looks off.

## 6. Stopping

```powershell
scripts/dev/stop-local.ps1
```

Stops all tracked service processes and (unless `-SkipInfra`) runs
`docker compose down`.

## Manual / single-service alternative

If you only need one service running (e.g. for focused debugging), you can
start it directly instead of using `start-local.ps1`:

```powershell
cd services/energy-service
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
.venv\Scripts\uvicorn app:app --host 0.0.0.0 --port 8006 --reload
```

Or use the per-service script, e.g. `scripts/dev/backend/start-energy.ps1`
(each one sources `.env` itself, so you don't need to set `PYTHONPATH`
manually). Note this opens its own terminal window and does **not**
redirect its logs to `logs/` the way `start-local.ps1`'s consumers do —
expect to read its output directly in that window.

## Service Ports

| Service | Port | Uvicorn Module |
|---------|------|----------------|
| Modular API (gateway) | 8000 | `backend.api_service.main:app` |
| Ingest Service | 8001 | `app:app` |
| ML Service | 8002 | `app:app` |
| Database Service | 8003 | `app:app` |
| Embedding Service | 8005 | `app:app` |
| Energy Service | 8006 | `app:app` |
| ML Platform | 8007 | `app:app` |
| Frontend (Vite) | 8080 | `npm run dev` |
| PostgreSQL | 5432 | — |
| Kafka | 9092 | — |
| Elasticsearch | 9200 | — |

## Next steps

- `02_ARCHITECTURE.md` — how the pieces fit together
- `03_DEVELOPMENT_WORKFLOW.md` — day-to-day dev loop
- `04_DEBUGGING.md` — VS Code debug configs
- `06_ENVIRONMENT_VARIABLES.md` — full env var reference
