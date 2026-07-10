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

Optional (Tier 2 data acquisition — only needed if you're re-running the
ml-platform ingestion scripts, not required to just run the app):
`NEWSDATA_API_KEY` (https://newsdata.io), `EIA_API_KEY`
(https://www.eia.gov/opendata), `AISSTREAM_API_KEY` (https://aisstream.io),
`CRUDE_PRICE_API_KEY` (https://www.crudepriceapi.com).

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
  - `POSTGRES_PORT` → **`5434`, not `5432`**. `docker-compose.yml` maps
    Postgres to host port 5434 (5432 is deliberately avoided in case another
    project on your machine already has a native Postgres there). Every
    script and service in this repo expects 5434 — if you ever see
    connection-refused errors on 5432, that's a stale assumption, not a
    real target.
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

**Watch out for line merges.** If you ever hand-edit `.env` in an editor that
reformats on save, double check no two lines got joined into one — e.g.
`CORS_ORIGINS=...,http://localhost:8081ELASTICSEARCH_PASSWORD=change-me` is a
real failure mode that happened on this machine: it silently deletes the
`ELASTICSEARCH_PASSWORD` variable (swallowed into the previous line's value)
while also corrupting the last CORS origin. Since `ELASTICSEARCH_PASSWORD` is
a *required* variable (`backend/shared/settings.py`), every service that
touches Elasticsearch fails at startup with a "missing required environment
variable" error that has nothing obviously to do with CORS. Quick sanity
check after any manual edit:
```powershell
Get-Content .env | Select-String "=" | Measure-Object | Select-Object -ExpandProperty Count
```
should roughly match the number of variables you expect — a sudden drop
means something got merged.

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
PostgreSQL/Kafka/Elasticsearch via `docker compose`, then starts all 6 API
services, all 3 Kafka consumers, and the frontend — each gated on its port
and health endpoint responding before moving to the next, so it fails fast
with a diagnosis (last 50-100 log lines + a guessed failure category) instead
of hanging. First run also does `npm install` for the frontend, so expect it
to take a few minutes.

Useful flags: `-SkipInfra` (Postgres/Kafka/ES already running),
`-SkipFrontend`, `-SkipCleanup` (skip killing stray old processes / port
checks), `-Force` (non-interactive, auto-confirm prompts).

**ml-platform takes longer to become healthy than the other five services** — it
imports torch/transformers/spaCy/xgboost at startup, which routinely takes
60-90s on a cold start (Python import, not model download). The launcher
gives it a 90s health-check window (vs 30s for the others); if you ever
start it manually and it looks stuck, that's normal — wait, don't restart it.

**If infra containers keep disappearing between sessions:** `kafka`,
`elasticsearch`, and `zookeeper` used to have no restart policy in
`docker-compose.yml`, so a Docker Desktop restart silently dropped them
while `postgres` (which had `restart: always`) came back. All four
containers now have `restart: always` — if you still see this, it means
someone ran `docker compose down` (which removes containers regardless of
restart policy) rather than just stopping Docker Desktop. Bring them back
with `docker compose up -d`; your data survives either way since it's on
named volumes (`postgres_data`, `elasticsearch_data`).

## 5. Verify it's working

```powershell
scripts/dev/status.ps1
```

Shows health-endpoint status for every service plus infra port checks. Then:

- Open http://localhost:8080 — the frontend should load and let you register/
  log in. The landing page itself works even logged out (it calls a public,
  unauthenticated preview endpoint) — if it's blank, that's a real bug, not
  expected behavior.
- `curl http://localhost:8001/fetch-real-news` — manually triggers a news
  fetch; should return fetched articles, not a `replace-me` API-key error.
- `curl http://localhost:8000/public/preview` — should return real article
  previews + stats with **no auth token**. A 500 here almost always means
  Postgres or Elasticsearch isn't actually reachable (check `.env` ports).
- `scripts/dev/logs.ps1 -Follow` — tail all service logs merged together if
  anything looks off.

### Running the test suite

```powershell
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
services/modular-api/.venv/Scripts/python.exe -m pytest tests/unit -q

# Integration tests are skipped by default -- need the full stack up first,
# and the flag to opt in:
services/modular-api/.venv/Scripts/python.exe -m pytest tests/integration -q --run-integration

# ml-platform has its own test tree, run from its own venv (has
# numpy/pandas/xgboost/confluent-kafka that modular-api's venv doesn't):
$env:PYTHONPATH = "C:\path\to\ProxyDefence;C:\path\to\ProxyDefence\services\ml-platform"
services/ml-platform/.venv/Scripts/python.exe -m pytest services/ml-platform -q
```

Unit tests (`tests/unit/`) need no running services — they're pure logic
tests. `tests/integration/` needs the full stack up (Postgres/ES/Kafka +
`modular-api` running) since they hit real HTTP endpoints; most use a mocked
DB pool, but `test_auth_api.py` connects to the real dev database (register/
login need genuine INSERT...RETURNING behavior a mock can't simulate). If
pytest reports a collection error (`AttributeError: 'Package' object has no
attribute 'obj'`) instead of running any tests, your venv has the broken
`pytest==8.0.0` + `pytest-asyncio==0.23.x` combo — re-run
`scripts/dev/setup/setup.ps1 -Force` to pick up the pinned fix
(`pytest-asyncio==0.24.0`).

### Full end-to-end validation (beyond pytest)

`validation/` is a separate, standalone framework (not pytest-based) that
exercises every live service over real HTTP/DB/ES/Kafka in one pass —
infra connectivity, all 6 services' health, the full ingest→Kafka→ML→DB→ES
pipeline, dataset catalog, feature store, model registry, inference,
AI/agents/copilot/RAG, GDELT pipeline, and the frontend + the endpoints it
depends on:

```powershell
$env:PYTHONPATH = "C:\path\to\ProxyDefence"
services/modular-api/.venv/Scripts/python.exe -m validation.runner
```

Needs the full stack running (see step 4). Writes `validation_report.json`
and `.html` with a pass/fail/warning breakdown per category. It registers
its own `validation-suite@proxydefence-test.io` account to get an auth
token for protected routes, so no manual login is needed first.

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
| Modular API (gateway) | 8000 | `backend.api.app:app` |
| Ingest Service | 8001 | `app:app` |
| Database Service | 8003 | `app:app` |
| Embedding Service | 8005 | `app:app` |
| Energy Service | 8006 | `app:app` |
| ML Platform (also runs the article-enrichment Kafka consumer) | 8007 | `app:app` |
| Frontend (Vite) | 8080 | `npm run dev` |
| PostgreSQL | **5434** (not 5432 — see note above) | — |
| Kafka | 9092 | — |
| Elasticsearch | 9200 | — |

There is no port 8002 / `ml-service` anymore — it was retired and its
article-enrichment duties (topic classification, threat scoring, sentiment,
NER) were absorbed into ml-platform's own Kafka consumer
(`services/ml-platform/consumer/article_enrichment.py`), which
`start-local.ps1` launches alongside the other two consumers
(`db-consumer`, `embedding-consumer`).

## Next steps

- `02_ARCHITECTURE.md` — how the pieces fit together
- `03_DEVELOPMENT_WORKFLOW.md` — day-to-day dev loop
- `04_DEBUGGING.md` — VS Code debug configs
- `06_ENVIRONMENT_VARIABLES.md` — full env var reference
