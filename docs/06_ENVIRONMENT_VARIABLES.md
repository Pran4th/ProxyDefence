# Environment Variables

## Source of Truth

The `.env` file in the repository root is the single source of truth.
All services read environment variables via `os.getenv()`.
Docker Compose reads from the same `.env` file via `${VAR}` syntax.

## Required Variables

These fail fast — services crash on startup if missing:

| Variable | Default | Used By |
|----------|---------|---------|
| `POSTGRES_USER` | — (required) | All database services |
| `POSTGRES_PASSWORD` | — (required) | All database services |
| `ELASTICSEARCH_PASSWORD` | — (required) | database-service, modular-api |
| `JWT_SECRET_KEY` | — (required) | database-service, modular-api |
| `ELASTIC_PASSWORD` | — (required) | elasticsearch container |

## Optional Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_HOST` | postgres | PostgreSQL hostname |
| `POSTGRES_DB` | defenseintel | PostgreSQL database name |
| `POSTGRES_PORT` | 5432 (code default; `.env` sets **5434** — docker-compose.yml maps the container's 5432 to host 5434, see 01_LOCAL_SETUP.md) | PostgreSQL port |
| `ELASTICSEARCH_HOST` | elasticsearch | Elasticsearch hostname |
| `ELASTICSEARCH_USER` | elastic | Elasticsearch username |
| `JWT_ALGORITHM` | HS256 | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | JWT token expiry |
| `CORS_ORIGINS` | localhost:3000 | Allowed CORS origins |
| `KAFKA_BOOTSTRAP_SERVERS` | kafka:9092 | Kafka broker address |
| `NEWS_API_KEY` | — | GNews API key |
| `ENERGY_LOAD_SEED` | 0 | Load seed data (1=yes) |
| `ENERGY_SERVICE_URL` | http://energy-service:8006 | Energy Service URL |
| `MLFLOW_TRACKING_URI` | file:./mlruns | MLflow tracking URI |
| `DVC_REMOTE` | ./data/dvc-store | DVC remote storage |
| `SERVICE_VERSION` | 1.0.0 | Service version metadata |
| `GIT_COMMIT` | unknown | Git commit hash |
| `ENVIRONMENT` | development | Runtime environment |
| `LOG_LEVEL` | INFO | Logging level |
| `VITE_API_URL` | http://localhost:8000 | Frontend API URL |

## Development-Specific

When running locally (not Docker), the following overrides apply:

- `KAFKA_BOOTSTRAP_SERVERS` = `localhost:9092` (in `.env`)
- `ELASTICSEARCH_HOST` = `localhost` (in `.env`)
- `POSTGRES_HOST` = `localhost` (in `.env`)
- `ENERGY_SERVICE_URL` = `http://localhost:8006` (set by startup scripts)

## Legacy Naming (Removed)

The `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` convention has been fully replaced with `POSTGRES_*`.
No `DB_*` variables should exist anywhere in the repository.

## Testing

Set `ENVIRONMENT=test` to use test configurations.
Tests use `backend/shared/config.py` which reads the same environment variables.
