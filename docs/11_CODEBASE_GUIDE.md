# ProxyDefence Codebase Guide

## What this system does

ProxyDefence is an India-first energy supply-chain resilience application. Its
operator workflow is: **Monitor → Assess → Decide → Approve → Learn**.

1. Monitor disruption signals and infrastructure/source status.
2. Assess a matching disruption scenario in the digital twin.
3. Decide on SPR and procurement alternatives.
4. Record human review/approval in an evidence bundle.
5. Retain telemetry and historical replay results for evaluation.

It is decision support. It does not execute trading, cargo nominations, or
government reserve releases.

## Runtime topology

| Component | Port | Responsibility |
| --- | ---: | --- |
| Frontend | 8080 | React operator UI, including Command Center |
| Modular API | 8000 | Authenticated gateway and API composition |
| Ingest service | 8001 | News fetching and `raw_articles` Kafka publishing |
| Database service | 8003 | Processed article storage and Elasticsearch indexing |
| Embedding service | 8005 | Embeddings/vector processing |
| Energy service | 8006 | Catalog, risk, twin, SPR, procurement, evidence, replay |
| ML platform | 8007 | Model serving, data acquisition, enrichment consumer |
| PostgreSQL | 5434 | Operational data; `energy.` and `ml.` schemas |
| Kafka | 9092 | Article pipeline transport |
| Elasticsearch | 9200 | Article search |

## Primary request path

```text
Command Center
  → modular-api (JWT gateway)
  → energy-service /command/respond
  → signal selection + scenario match
  → digital twin
  → India-only SPR optimisation
  → procurement alternatives
  → evidence bundle + draft approval + telemetry
```

An optional `refinery_uuid` records the target refinery's catalog capacity,
Nelson complexity, and accepted crude labels. It does **not** certify a
supplier's cargo grade until a verified cargo-specification source is loaded.

## Request-to-code map

This table is the shortest route from a product behaviour to the code that owns
it. It is intentionally an operating map, rather than a line-by-line API
reference.

| Behaviour | Primary implementation | Persistent record / external dependency |
| --- | --- | --- |
| Login and protected gateway routes | `backend/api/app.py`, `backend/api_service/security.py` | PostgreSQL user records; JWT secret from environment |
| News ingestion | `services/ingest-service/app.py` | GNews/NewsData when configured; Kafka `raw_articles` |
| Article enrichment | `services/ml-platform/consumer/article_enrichment.py` | Kafka `raw_articles` to `processed_articles`; model-serving API |
| Article search and indexing | `services/database-service/app.py` | PostgreSQL plus Elasticsearch |
| Energy catalog and decision APIs | `services/energy-service/app.py`, `routers/` | `energy.` PostgreSQL schema |
| Hormuz response orchestration | `services/energy-service/routers/command_center.py` | Response telemetry, evidence bundle, approval state |
| Risk, twin, SPR, procurement | `services/energy-service/services/` | Catalog constraints, source-status records, model bridge |
| Evidence and historical replay | `services/energy-service/services/evidence.py`, `historical_replays.py` | `energy.response_evidence_bundles`, `energy.historical_replay_runs` |
| ML API and model registry | `services/ml-platform/app.py`, `training/`, `routers/` | `ml.` PostgreSQL schema and model artifacts |
| Operator interface | `services/frontend/src/pages/CommandCenter.tsx` | Modular API; browser golden-path test |
| Schema bootstrap | `infra/sql/` | PostgreSQL DDL, seed and pilot-readiness tables |

## Data ownership and boundaries

- `public` holds the shared application/article data used by gateway services.
- `energy` holds infrastructure catalog, signals, response telemetry, source
  status, evidence, approvals, and replay records.
- `ml` holds registered datasets, feature/model metadata, predictions, and
  model-governance records.
- Elasticsearch is a search index, not the authoritative decision record;
  PostgreSQL stores the auditable state.
- Kafka is transport for articles. A decision response remains reproducible from
  its stored assumptions and evidence bundle even if a connector later fails.

## Key directories

| Path | Purpose |
| --- | --- |
| `services/energy-service/` | Decision engines and domain APIs |
| `services/ml-platform/` | Data acquisition, model registry, serving, Kafka enrichment |
| `services/frontend/` | React UI and Playwright golden-path coverage |
| `backend/` | Shared auth, settings, gateway, database, logging |
| `infra/sql/` | Canonical PostgreSQL schema/bootstrap SQL |
| `validation/` | Live-environment validation framework |
| `tests/` | Unit/integration tests |
| `scripts/demo/` | Deterministic pilot start, replay, and verification commands |
| `docs/` | Product, deployment, pilot, and public-data records |

## Reproducible pilot commands

```powershell
scripts/demo/start-pilot.ps1
scripts/demo/verify-pilot-readiness.ps1
scripts/demo/run-hormuz-replay.ps1 -Case abqaiq-2019
```

`verify-pilot-readiness.ps1` authenticates through the gateway and checks the
scenario selection, evidence-bundle persistence, approval history, telemetry,
and a procurement-volume guard.

## Data truth contract

Every decision evidence bundle records source, observation time, ingestion time,
freshness, mode, and fallback reason. Modes are `live`, `cached`, `replay`, or
`fallback`; a disabled connector is shown explicitly in provenance. Do not call
a cached snapshot a live feed.

## Public-data boundaries

The public demo uses PPAC refinery figures, ISPRL facility capacity, IEA Hormuz
context, OFAC/UN sanctions datasets, GDELT, public market benchmarks, and public
infrastructure data. It does not contain an operator's contracts, inventory,
assays, berth windows, or approval authorities. See
[Public Demo Profile](10_PUBLIC_DEMO_PROFILE.md).

## Verification inventory

- Python pilot-readiness unit tests: `tests/test_pilot_readiness.py`
- Browser command-center golden path: `cd services/frontend; npm run test:e2e`
- Frontend production build: `cd services/frontend; npm run build`
- Live service checks: `python -m validation.runner` with the full stack running
- Authenticated replay/evidence verification: `scripts/demo/verify-pilot-readiness.ps1`

## Security baseline

- Passwords use the shared password hashing utility; JWT secrets are environment
  supplied, not hard-coded.
- Protected UI routes require a stored bearer token and the gateway enforces
  protected API routes.
- Current frontend production dependency audit is clean (`npm audit --omit=dev`).
- Treat `.env`, customer data, and production keys as deployment secrets; never
  commit them to this repository.
