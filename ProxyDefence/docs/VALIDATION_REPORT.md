# ProxyDefence Validation Report

Generated 2026-06-19. Documentation only. No code was modified to produce this report.

Scope:
- Validate the explicit issues called out in [ARCHITECTURE_REPORT.md](ARCHITECTURE_REPORT.md) and [REMEDIATION_PLAN.md](REMEDIATION_PLAN.md).
- Confirm what Phase 1 Security Hardening fixed in the live codebase.
- Record what remains unresolved after Phase 1.

## Validation Summary

| Totals | Count |
|---|---:|
| Fixed | 2 |
| Partially Fixed | 0 |
| Remaining | 12 |

## Issue Catalog

### ARCH-01
| Field | Value |
|---|---|
| Severity | Critical |
| Category | Architecture |
| Exact Location | [services/database-service/app.py](../services/database-service/app.py#L81) and [docs/ARCHITECTURE_REPORT.md](ARCHITECTURE_REPORT.md#L447) |
| Current State | Schema DDL is still split across multiple places; `services/database-service/app.py` still defines tables and alters columns inline. |
| Why It Is A Problem | Schema drift causes inconsistent constraints, FK behavior, and boot-time surprises across services. |
| Evidence | `create_tables()` in [services/database-service/app.py](../services/database-service/app.py#L81) still issues `CREATE TABLE` / `ALTER TABLE IF NOT EXISTS` statements. |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-02
| Field | Value |
|---|---|
| Severity | Critical |
| Category | Architecture |
| Exact Location | [openapi.json](../openapi.json#L1) and [docs/ARCHITECTURE_REPORT.md](ARCHITECTURE_REPORT.md#L448) |
| Current State | The committed OpenAPI snapshot still reflects an older route set and is not regenerated from the live gateway. |
| Why It Is A Problem | Generated clients will miss current routes and security metadata, producing broken integrations. |
| Evidence | [openapi.json](../openapi.json#L1) still shows the older path set while [backend/api_service/main.py](../backend/api_service/main.py#L41) now includes more routers. |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-03
| Field | Value |
|---|---|
| Severity | Critical |
| Category | Security |
| Exact Location | [backend/api_service/main.py](../backend/api_service/main.py#L41-L95) and [backend/api_service/routes/*.py](../backend/api_service/routes/) |
| Current State | Phase 1 now applies `Depends(get_current_user)` to all protected modular-api routers and records the authenticated user in audit middleware. |
| Why It Is A Problem | This was the primary authentication bypass; without it, the intelligence dataset and mutation endpoints were callable anonymously. |
| Evidence | Protected routers are included with `dependencies=[Depends(get_current_user)]` in [backend/api_service/main.py](../backend/api_service/main.py#L73); `audit_mutating_requests` now writes `request.state.current_user.id` at [backend/api_service/main.py](../backend/api_service/main.py#L80-L95). |
| Status | Fixed |
| Validation Result | Pass |

### ARCH-04
| Field | Value |
|---|---|
| Severity | Critical |
| Category | Security |
| Exact Location | [backend/shared/config.py](../backend/shared/config.py#L4-L18), [docker-compose.yml](../docker-compose.yml#L56-L176), [services/ingest-service/app.py](../services/ingest-service/app.py#L17-L19), [.env.example](../.env.example#L3-L21) |
| Current State | Hardcoded JWT/database/API-key values were removed from runtime code and compose, and the workspace no longer contains the committed token-seed files. |
| Why It Is A Problem | Embedded secrets enable credential theft, JWT forgery, and irreversible leakage through source control. |
| Evidence | `backend/shared/config.py` now requires `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `JWT_SECRET_KEY`; `ingest-service` now requires `NEWS_API_KEY`; `.docker-config/.token_seed*` is absent from the workspace; `.env.example` contains placeholders only. |
| Status | Fixed |
| Validation Result | Pass |

### ARCH-05
| Field | Value |
|---|---|
| Severity | Critical |
| Category | Architecture |
| Exact Location | [services/conflict-api/app/main.py](../services/conflict-api/app/main.py#L1-L53) and [services/database-service/app.py](../services/database-service/app.py#L1-L120) |
| Current State | `conflict-api` still boots even though it registers no routes, and `database-service` still exposes a separate HTTP API that overlaps the main gateway. |
| Why It Is A Problem | Dead/parallel services increase operational surface area and create ownership confusion for the API contract. |
| Evidence | `conflict-api` only wires CORS, DB, and Elasticsearch startup; `database-service` still exposes `/api/*` endpoints and `POST /rebuild-events`. |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-06
| Field | Value |
|---|---|
| Severity | High |
| Category | Reliability |
| Exact Location | [services/database-service/app.py](../services/database-service/app.py#L869-L872) |
| Current State | Kafka consumers still run in daemon threads spawned from FastAPI startup events. |
| Why It Is A Problem | An uncaught exception kills the consumer thread while the HTTP service remains up, so pipeline failure can go unnoticed. |
| Evidence | `threading.Thread(target=start_kafka_consumer, daemon=True).start()` remains at [services/database-service/app.py](../services/database-service/app.py#L872); the same pattern also exists in the other worker-style services. |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-07
| Field | Value |
|---|---|
| Severity | High |
| Category | Reliability |
| Exact Location | [services/database-service/app.py](../services/database-service/app.py#L39-L46) |
| Current State | Every SQL operation still opens a new `psycopg2` connection instead of reusing a pool. |
| Why It Is A Problem | Connection churn dominates write latency and limits throughput under ingest load. |
| Evidence | `get_postgres_connection()` is called repeatedly throughout [services/database-service/app.py](../services/database-service/app.py#L273-L1013). |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-08
| Field | Value |
|---|---|
| Severity | High |
| Category | Reliability |
| Exact Location | [services/embedding-service/app.py](../services/embedding-service/app.py#L23-L126) |
| Current State | `article_embeddings` is still created lazily via the embedding service rather than being guaranteed at boot. |
| Why It Is A Problem | Semantic search and copilot can return empty results if the embedding service has not initialized the table. |
| Evidence | The embedding service exposes `/generate` and `/search`, but there is no boot-time schema guarantee in [services/embedding-service/app.py](../services/embedding-service/app.py#L23-L126). |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-09
| Field | Value |
|---|---|
| Severity | High |
| Category | Reliability |
| Exact Location | [services/database-service/app.py](../services/database-service/app.py#L901-L913) |
| Current State | `/rebuild-events` still deletes all event tables directly. |
| Why It Is A Problem | A mid-run failure can leave the event model partially rebuilt and inconsistent. |
| Evidence | The handler still executes `DELETE FROM event_entities`, `DELETE FROM event_articles`, and `DELETE FROM events`. |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-10
| Field | Value |
|---|---|
| Severity | High |
| Category | Reliability |
| Exact Location | [services/database-service/app.py](../services/database-service/app.py#L81-L150) |
| Current State | Schema changes remain additive-only (`ADD COLUMN IF NOT EXISTS`) with no migration/down-path framework. |
| Why It Is A Problem | Rename/drop changes cannot be deployed safely, which blocks controlled schema evolution. |
| Evidence | The table bootstrap still uses `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` throughout [services/database-service/app.py](../services/database-service/app.py#L107-L150). |
| Status | Not Fixed |
| Validation Result | Fail |

### ARCH-11
| Field | Value |
|---|---|
| Severity | Medium |
| Category | Code Quality |
| Exact Location | [backend/api_service/repositories/intelligence.py](../backend/api_service/repositories/intelligence.py#L13) |
| Current State | `IntelligenceRepository` remains a very large monolith that mixes unrelated aggregates and report-generation helpers. |
| Why It Is A Problem | The class is difficult to reason about, test, and change without introducing cross-domain regressions. |
| Evidence | The class starts at [backend/api_service/repositories/intelligence.py](../backend/api_service/repositories/intelligence.py#L13) and still contains events, entities, watchlists, alerts, cases, reports, audit, and graph logic. |
| Status | Not Fixed |
| Validation Result | Fail |

### SEC-01
| Field | Value |
|---|---|
| Severity | Critical |
| Category | Security |
| Exact Location | [docker-compose.yml](../docker-compose.yml#L20-L44) and [docs/REMEDIATION_PLAN.md](REMEDIATION_PLAN.md#L90-L95) |
| Current State | Elasticsearch still runs with `xpack.security.enabled=false`, and Kafka still uses PLAINTEXT listeners. |
| Why It Is A Problem | Any container on the bridge network can access or manipulate data and broker traffic without authentication. |
| Evidence | `docker-compose.yml` still sets PLAINTEXT Kafka listeners and disables Elasticsearch security in the infrastructure section. |
| Status | Not Fixed |
| Validation Result | Fail |

### SEC-02
| Field | Value |
|---|---|
| Severity | High |
| Category | Security |
| Exact Location | [backend/api_service/main.py](../backend/api_service/main.py#L1-L101), [docs/REMEDIATION_PLAN.md](REMEDIATION_PLAN.md#L99-L105) |
| Current State | There is still no rate limiter or request-abuse guard installed in the FastAPI gateway. |
| Why It Is A Problem | Unbounded `/copilot/query` and search traffic can exhaust the async pool or amplify denial-of-service conditions. |
| Evidence | No limiter middleware or dependency is installed in [backend/api_service/main.py](../backend/api_service/main.py#L1-L101). |
| Status | Not Fixed |
| Validation Result | Fail |

### SEC-03
| Field | Value |
|---|---|
| Severity | Medium |
| Category | Security |
| Exact Location | [docs/REMEDIATION_PLAN.md](REMEDIATION_PLAN.md#L108-L111) |
| Current State | Dependency-supply-chain hardening is still pending; there is no `pip-audit` / Dependabot workflow in place. |
| Why It Is A Problem | Known CVEs and risky transitive dependencies can remain undetected in production builds. |
| Evidence | The remediation plan still calls for `pip-audit`, Dependabot, and possible JWT library migration. |
| Status | Not Fixed |
| Validation Result | Fail |

## Remaining Critical Issues

- `ARCH-01` schema definitions are still duplicated and can drift.
- `ARCH-02` the committed OpenAPI snapshot is stale.
- `ARCH-05` the dead `conflict-api` and duplicate `database-service` HTTP surface remain live.
- `ARCH-06` consumer threads can still die silently.
- `ARCH-07` database-service still opens a fresh PostgreSQL connection for each operation.
- `ARCH-08` `article_embeddings` is still created lazily.
- `ARCH-09` `/rebuild-events` is still destructive and unguarded.
- `ARCH-10` there is still no migration / down-path framework.
- `SEC-01` Elasticsearch and Kafka are still running with security disabled.
- `SEC-02` there is still no rate limiting / abuse control.

## Remaining Security Risks

- Authentication bypasses: none observed in the modular-api route layer after Phase 1.
- Authorization bypasses: none observed in the modular-api route layer after Phase 1.
- Ownership bypasses: watchlist/case/report ownership checks now derive from the authenticated user; no bypass remains in the touched routes.
- Hardcoded secrets: none remain in the live code paths; placeholders live only in [.env.example](../.env.example#L3-L21).
- Privilege escalation paths: `/alerts/generate` remains admin-only; no other admin-only guard gaps were found in Phase 1 scope.
- Missing admin checks: none remain in the Phase 1-touched modular-api routes.

## Route Protection Audit

### Modular API (`backend/api_service`)

| Route | Protection |
|---|---|
| `GET /` | Public |
| `POST /auth/register` | Public |
| `POST /auth/login` | Public |
| `GET /auth/me` | Authenticated |
| `GET /health` | Public |
| `GET /articles/` | Authenticated |
| `GET /articles/{id}` | Authenticated |
| `GET /articles/{id}/entities` | Authenticated |
| `GET /analytics/dashboard` | Authenticated |
| `GET /analytics/threat-trends` | Authenticated |
| `GET /analytics/summary` | Authenticated |
| `GET /analytics/graph` | Authenticated |
| `GET /analytics/dashboard-v2` | Authenticated |
| `GET /analytics/timeseries` | Authenticated |
| `GET /analytics/entities` | Authenticated |
| `GET /analytics/topics` | Authenticated |
| `GET /search/` | Authenticated |
| `GET /semantic-search` | Authenticated |
| `GET /graph/network` | Authenticated |
| `GET /graph/{entity}` | Authenticated |
| `GET /events/` | Authenticated |
| `GET /events/{event_id}` | Authenticated |
| `GET /events/{event_id}/articles` | Authenticated |
| `GET /entities/` | Authenticated |
| `GET /entities/{entity_name}` | Authenticated |
| `GET /entities/{entity_name}/articles` | Authenticated |
| `GET /entities/{entity_name}/relationships` | Authenticated |
| `GET /reports/` | Authenticated |
| `GET /reports/{report_id}` | Authenticated |
| `POST /reports/case/{case_id}` | Authenticated |
| `GET /watchlists/` | Authenticated |
| `GET /watchlists/{watchlist_id}` | Authenticated |
| `POST /watchlists/` | Authenticated |
| `DELETE /watchlists/{watchlist_id}` | Authenticated |
| `POST /watchlists/{watchlist_id}/entities` | Authenticated |
| `DELETE /watchlists/{watchlist_id}/entities/{entity_text}` | Authenticated |
| `GET /alerts/` | Authenticated |
| `GET /alerts/{alert_id}` | Authenticated |
| `PATCH /alerts/{alert_id}/status` | Authenticated |
| `POST /alerts/generate` | Admin Only |
| `GET /cases/` | Authenticated |
| `POST /cases/` | Authenticated |
| `GET /cases/{case_id}` | Authenticated |
| `POST /cases/{case_id}/items` | Authenticated |
| `DELETE /cases/{case_id}/items/{item_type}/{item_id}` | Authenticated |
| `GET /cases/{case_id}/notes` | Authenticated |
| `POST /cases/{case_id}/notes` | Authenticated |
| `POST /copilot/query` | Authenticated |

### Internal Services

| Service | Route(s) | Protection |
|---|---|---|
| ingest-service | `GET /`, `GET /health`, `GET /fetch-real-news` | Public / internal-only by deployment convention |
| embedding-service | `GET /search`, `GET /generate`, `GET /health` | Public / internal-only by deployment convention |
| database-service | `GET /`, `GET /health`, `GET /api/articles*`, `GET /api/analytics*`, `GET /api/search`, `POST /rebuild-events` | Public / internal-only by deployment convention |
| conflict-api | no registered routes | N/A |

## Secret Audit

| Item | Current State |
|---|---|
| Hardcoded secrets | None remain in the live code paths for JWT, Postgres, or GNews. |
| Fallback secrets | None in `backend/shared/config.py`; it now raises if `POSTGRES_USER`, `POSTGRES_PASSWORD`, or `JWT_SECRET_KEY` are missing. |
| Default credentials | No live default credentials remain in compose/service code. Placeholder values exist only in [.env.example](../.env.example#L3-L21). |
| Committed credentials | `.docker-config/.token_seed*` is not present in the workspace after Phase 1. |
| Environment variable usage | `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`, `NEWS_API_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `VITE_API_URL`. |

## Validation Notes

- Phase 1 security hardening is validated as **partially complete**: authentication/authorization and secret externalization are fixed, but infrastructure security, abuse limits, and dependency hygiene remain open.
- The report and remediation plan still describe additional lower-priority reliability and scalability work that was not part of Phase 1.
