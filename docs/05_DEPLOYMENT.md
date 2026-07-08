# Deployment

## Production Docker Deployment

The full production deployment uses `docker-compose.full.yml`:

```powershell
# Build and start all services
docker compose -f docker-compose.full.yml up --build -d

# View logs
docker compose -f docker-compose.full.yml logs -f

# Stop all services
docker compose -f docker-compose.full.yml down
```

## What's Included

The full deployment includes:
- All infrastructure (PostgreSQL, Kafka, Elasticsearch)
- All Python FastAPI services (7 services)
- The React frontend (served via nginx)
- Healthchecks on all services
- Persistent volumes for PostgreSQL and Elasticsearch

## Differences from Development

| Aspect | Development | Production |
|--------|-------------|------------|
| Services run via | Python .venv | Docker containers |
| Infrastructure | Docker (docker-compose.yml) | Docker (same) |
| Frontend | `npm run dev` (Vite) | nginx serving built files |
| Hot reload | Yes (`--reload`) | No |
| Debugging | VS Code attach | Container logs |
| File changes | Instant restart | Requires rebuild |

## Building Individual Services

```powershell
# Build a specific service
docker compose -f docker-compose.full.yml build energy-service

# Build all services
docker compose -f docker-compose.full.yml build
```

## Kubernetes (Future)

The `docker-compose.full.yml` is designed to be the foundation for Kubernetes migration.
Each service in the compose file maps to a Kubernetes Deployment.
The `proxy_net` network maps to a Kubernetes NetworkPolicy.

## Research Models

Trained models from `research/` are exported to `research/models/`.
The ML Platform loads models from a configurable path.
Research notebooks never execute inside production containers.
