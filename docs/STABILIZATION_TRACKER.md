# ProxyDefence Release Hardening — Stabilization Tracker

**Sprint:** 8.5 (Release Hardening)
**Objective:** 100% system stability. No new features. No architecture changes.
**Started:** 2026-07-04
**Release Readiness:** 0%

---

## Phase 1 — Infrastructure

| Check | Status | Notes |
|-------|--------|-------|
| PostgreSQL clean startup | | |
| PostgreSQL clean shutdown | | |
| PostgreSQL restart safety | | |
| PostgreSQL health check | | |
| PostgreSQL readiness check | | |
| Kafka clean startup | | |
| Kafka clean shutdown | | |
| Kafka restart safety | | |
| Kafka health check | | |
| Kafka readiness check | | |
| Elasticsearch clean startup | | |
| Elasticsearch clean shutdown | | |
| Elasticsearch restart safety | | |
| Elasticsearch health check | | |
| Elasticsearch readiness check | | |
| Zookeeper clean startup | | |
| Zookeeper clean shutdown | | |
| No orphan resources after restart | | |

## Phase 2 — Environment

| Check | Status | Notes |
|-------|--------|-------|
| .env loads correctly | | |
| All startup scripts work | | |
| All .venvs exist | | |
| PYTHONPATH correct for all services | | |
| POSTGRES_* variables consistent | | |
| Docker Compose infra starts | | |
| Docker Compose full starts | | |

## Phase 3 — Database

| Check | Status | Notes |
|-------|--------|-------|
| public schema complete | | |
| energy schema complete | | |
| ml schema complete | | |
| All ENUMs created | | |
| All indexes created | | |
| All constraints valid | | |
| Foreign keys valid | | |
| Seed data loads | | |
| Schema init idempotent | | |
| No duplicate on repeated startup | | |

## Phase 4 — Backend Services

| Service | Status | Notes |
|---------|--------|-------|
| ingest-service | | |
| ml-service | | |
| database-service | | |
| embedding-service | | |
| energy-service | | |
| ml-platform | | |
| modular-api | | |

## Phase 5 — Kafka

| Check | Status | Notes |
|-------|--------|-------|
| Topics created | | |
| Consumers connect | | |
| Producers send | | |
| Offsets advance | | |
| Retries work | | |
| Malformed messages handled | | |
| Consumer survives restart | | |
| No consumer terminates on bad message | | |

## Phase 6 — Elasticsearch

| Check | Status | Notes |
|-------|--------|-------|
| Authentication works | | |
| Index created | | |
| Mappings correct | | |
| Search works | | |
| Reconnect works | | |
| Missing index handled gracefully | | |
| Connection failures handled | | |

---

## Issues

### I-001: ML consumer crashes on non-JSON message

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **Description** | ML consumer crashes entirely when it encounters a non-JSON message on raw_articles topic. The `except` block in `start_kafka_consumer()` logs the error then re-raises, killing the entire consumer process. |
| **Root Cause** | `services/ml-service/app.py:119-121` — `except Exception as exc: logger.exception(...); raise` — the `raise` propagates the exception out of the poll loop, terminating the consumer. Should be `continue` to skip the bad message and keep processing. |
| **Files Changed** | |
| **Fix Summary** | |
| **Verification** | |
| **Status** | OPEN |

### I-002: Search endpoint returns 500 (ES auth)

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **Description** | GET /search?q=... on database-service and modular-api both return 500 because Elasticsearch requires authentication credentials. |
| **Root Cause** | `docker-compose.yml` uses ES 8.11.0 with default security enabled. The ES client in both services does not pass credentials. `.env` has `ELASTICSEARCH_PASSWORD=change-me` but `elastic_client.py` reads `ELASTICSEARCH_USER` (default "elastic") and `ELASTICSEARCH_PASSWORD` from settings. The credentials may not be flowing correctly through the config chain. |
| **Files Changed** | |
| **Fix Summary** | |
| **Verification** | |
| **Status** | OPEN |

### I-003: Energy service route ordering shadows specific endpoints

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Description** | catalog.router included before relationships, events, history, bulk routers. Generic `/{table}` and `/{table}/{entity_uuid}` match before specific routes like `POST /events`, `GET /graph/network`, `POST /bulk/import`. |
| **Root Cause** | `services/energy-service/app.py:32-36` — router include order: catalog first, then relationships/events/history/bulk. Fix: include catalog LAST. |
| **Files Changed** | |
| **Fix Summary** | |
| **Verification** | |
| **Status** | OPEN |

### I-004: Entity sub-endpoints return 500 (entity_type ENUM mismatch)

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Description** | GET /ports/{uuid}/relationships, /events, /history all return 500. The entity_relationships query uses plural table names ("ports") but asset_type ENUM uses singular values ("port"). |
| **Root Cause** | `services/energy-service/routers/relationships.py`, `events.py`, `history.py` — entity_type filter uses table name (plural) instead of asset_type ENUM value (singular). |
| **Files Changed** | |
| **Fix Summary** | |
| **Verification** | |
| **Status** | OPEN |

### I-005: UUID validation missing — invalid UUID → 500

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Description** | GET /ports/not-a-uuid bypasses format validation, hits PostgreSQL with invalid UUID string → SQL cast error → 500. |
| **Root Cause** | `services/energy-service/routers/catalog.py` — no UUID format validation before SQL query. |
| **Files Changed** | |
| **Fix Summary** | |
| **Verification** | |
| **Status** | OPEN |

### I-006: Locations table missing columns for generic CRUD filters

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Description** | GET /locations?status=operational returns 500 (no status column in locations table). Same for criticality, deleted_by. |
| **Root Cause** | `energy.locations` table is missing columns that the generic catalog CRUD expects: status, operational_status, criticality, deleted_by, tags, last_verified. |
| **Files Changed** | |
| **Fix Summary** | |
| **Verification** | |
| **Status** | OPEN |

---

## Remaining Issues

(To be filled during stabilization)

## Blocked Issues

(To be filled during stabilization)

## Known Limitations

(To be filled during stabilization)
