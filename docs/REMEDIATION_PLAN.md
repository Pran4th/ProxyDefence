# ProxyDefence — Technical Debt Remediation Plan

> **Role:** Staff Software Engineer & Cloud Architect review.
> **Generated:** 2026-06-19. **Source of findings:** `docs/ARCHITECTURE_REPORT.md` plus full codebase inspection (`docker-compose.yml`, `infra/sql/init.sql`, `backend/shared/schema_bootstrap.py`, all service source, `.gitignore`, `.docker-config/`, `.env`, dependency manifests).
> **Constraint honored:** No code modified. Documentation only.

This plan converts every item from the architecture report (§7 Technical Debt, §8 Scalability Bottlenecks) plus additional findings discovered during remediation scoping into **42 actionable remediations** across **8 categories**, sequenced into a **4‑phase roadmap** with effort, priority, and dependency tracking.

---

## Priority & Difficulty Legend

| Priority | Meaning | Target SLA |
|---|---|---|
| **P0** | Security/data‑loss/blocker; fix before any further feature work or cloud promotion | Days |
| **P1** | High‑risk correctness/reliability; fix in current stabilization cycle | 1–2 weeks |
| **P2** | Important quality/scalability; schedule this quarter | 1–3 months |
| **P3** | Hygiene/tech‑modernization; opportunistic | Next 2 quarters |

| Difficulty | Meaning |
|---|---|
| **Low** | Config/infra change, no behavioral rewrite; reversible. |
| **Medium** | Code change across 1–3 modules; some test effort. |
| **High** | Architectural shift, multi‑service coordination, or data migration. |

Effort is given in **engineer‑weeks (EW)** at nominal velocity; ranges reflect risk bands.

---

## Category Index

| § | Category | Items | P0 | P1 | P2 | P3 |
|---|---|---|---|---|---|---|
| 1 | Security | S1–S7 (7) | 5 | 1 | 1 | — |
| 2 | Architecture | A1–A7 (7) | — | 3 | 3 | 1 |
| 3 | Reliability | R1–R6 (6) | — | 4 | 2 | — |
| 4 | Scalability | SC1–SC6 (6) | — | 1 | 5 | — |
| 5 | Code Quality | CQ1–C7 (7) | — | 1 | 4 | 2 |
| 6 | Cloud Readiness | CR1–CR4 (4) | — | — | 2 | 2 |
| 7 | DevOps | DO1–CR… DO1–DO3 (3) | 1 | 1 | 1 | — |
| 8 | Observability | OB1–OB2 (2) | — | 1 | 1 | — |

---

## 1. Security

### S1 — Hard‑coded secrets in compose & source
- **Root Cause:** Credentials (GNews `NEWS_API_KEY`, `POSTGRES_USER=admin / POSTGRES_PASSWORD=admin123`, `JWT_SECRET_KEY="proxydefence-dev-secret"`) embedded directly in `docker-compose.yml` and as Python defaults in `services/ingest-service/app.py` and `backend/shared/config.py`.
- **Business Impact:** P0 — API key abuse/billing surprise, full DB credential leak on any repo clone, JWT forgery (known HS256 secret ⇒ attacker mints any user/role).
- **Technical Impact:** No secret rotation path; cannot open‑source; audit/compliance failure.
- **Difficulty:** Low. **Priority:** **P0**.
- **Recommended Solution:**
  1. Remove all literal secrets from compose and source defaults.
  2. Move to an `.env` file (currently 0 bytes) loaded via docker‑compose `env_file:`; gitignore `.env`.
  3. Use a secrets manager for non‑dev (AWS Secrets Manager / Vault / Doppler).
  4. Rotate GNews key + Postgres password immediately upon merge; treat the committed values as compromised.
- **Estimated Effort:** 0.5 EW (code) + rotation ops.
- **Dependencies:** None. Unblocks S2, CR1.

### S2 — Committed secret seed (`.docker-config/.token_seed`)
- **Root Cause:** A token seed file lives at `.docker-config/.token_seed` (74 B) with a `.lock` sibling, tracked in the repo — outside the `.env` convention and outside `.gitignore`.
- **Business Impact:** P0 — seed leak enables deterministic token generation if it feeds any signing path; at minimum it normalizes committing secrets.
- **Technical Impact:** Same threat model as S1; inconsistent with the empty `.env`.
- **Difficulty:** Low. **Priority:** **P0**.
- **Recommended Solution:** Audit what consumes `.token_seed`; if live, move into the secrets manager; `git rm --cached`, purge from history (`git filter-repo`), rotate. Add `.docker-config/.token_seed*` to `.gitignore`.
- **Estimated Effort:** 0.5 EW + history rewrite.
- **Dependencies:** S1 (shared secret store).

### S3 — JWT present but unenforced on virtually all routes
- **Root Cause:** `backend/api_service/security.py` implements `get_current_user`/`require_admin`, but only `/auth/me` references it. All analytics, articles, events, cases, watchlists, alerts, reports, graph, and copilot routes are anonymous.
- **Business Impact:** P0 — any internet‑exposed instance leaks the entire intelligence dataset and allows unauthenticated case/report/alert mutation.
- **Technical Impact:** Audit middleware records `user_id=None` for every mutation → non‑attributable.
- **Difficulty:** Medium (route‑by‑route). **Priority:** **P0**.
- **Recommended Solution:**
  1. Add a global `Depends(get_current_user)` on the protected router group, or a middleware that whitelists `/auth/*`, `/health`, `/` and requires a valid bearer otherwise.
  2. Pass `current_user["id"]` into the audit middleware and into `created_by`/`owner_id` fields (currently hardcoded `None`).
  3. Enforce `require_admin` on destructive ops (`/rebuild-events`, watchlist delete, case delete).
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** None; do with S4.

### S4 — Audit trail loses actor identity
- **Root Cause:** `main.py::audit_mutating_requests` hardcodes `user_id=None`; mutating handlers accept `owner_id: int | None = None` / `created_by: int | None = None` as query params instead of deriving from the token.
- **Business Impact:** P0 (paired with S3) — defense platform with no attributable audit log fails its core compliance premise.
- **Technical Impact:** `audit_logs.user_id` always null; reports/cases/watchlists orphaned to `owner_id=NULL`.
- **Difficulty:** Medium. **Priority:** **P0**.
- **Recommended Solution:** Inject `request.state.user` from the auth dependency; audit + repositories read it. Remove the `owner_id`/`created_by` query‑string params.
- **Estimated Effort:** 1 EW.
- **Dependencies:** S3.

### S5 — Elasticsearch & Kafka run with security disabled
- **Root Cause:** `xpack.security.enabled=false` (ES) and PLAINTEXT listeners with no auth/SASL (Kafka). Single‑node dev defaults shipped into the stack.
- **Business Impact:** P0 — any pod/container on `proxy_net` can read/modify the index and broker; lateral‑movement risk.
- **Technical Impact:** Cannot satisfy any data‑classification requirement; blocks cloud promotion.
- **Difficulty:** Medium. **Priority:** **P0** (pre‑cloud); P1 (dev).
- **Recommended Solution:** Enable ES security (TLS + native/oidc realm); Kafka SASL_SSL/SCRAM‑SHA‑512 + ACLs; mutualize via the secrets manager. Stage behind a feature flag for local dev (docker‑compose override).
- **Estimated Effort:** 2 EW.
- **Dependencies:** S1.

### S6 — No input‑rate protection / abuse limits
- **Root Cause:** No rate limiting, request size caps, or bot protection on any service; Copilot runs unbounded httpx + multi‑query fan‑out.
- **Business Impact:** P1 — DoS amplification, especially on `/copilot/query` and `/search`.
- **Technical Impact:** Resource exhaustion saturates the asyncpg pool (max 10).
- **Difficulty:** Medium. **Priority:** **P1**.
- **Recommended Solution:** Add `slowapi` (FastAPI limiter) keyed on authenticated user; bound copilot concurrency; set per‑route limits. Front with a WAF/CDN in cloud (CR2).
- **Estimated Effort:** 1 EW.
- **Dependencies:** S3 (limits are per‑user).

### S7 — Dependency‑supply‑chain hygiene
- **Root Cause:** Pinned versions but no `pip-audit`/Dependabot; `python-jose` (under deprecation discussion) used for JWT; transitive `torch` pulled via `transformers` without pinning.
- **Difficulty:** Low. **Priority:** **P2**.
- **Recommended Solution:** Enable Dependabot; add `pip-audit` to CI; evaluate migration `python-jose` → `PyJWT` or `authlib`; pin `torch` explicitly.
- **Estimated Effort:** 0.5 EW setup + ongoing.
- **Dependencies:** DO1 (CI must exist first).

---

## 2. Architecture

### A1 — Triplicated, drifted schema definitions
- **Root Cause:** Three independent schema sources: `infra/init.sql`, `infra/sql/init.sql`, `backend/shared/schema_bootstrap.py` (authoritative, 18 statements), and `services/database-service/app.py::create_tables()`. `article_embeddings` exists only at runtime (embedding‑service). FK delete rules diverge (e.g. `extracted_entities.article_id` is `NO ACTION` in bootstrap but absent/`ON DELETE` varies in init.sql).
- **Business Impact:** P1 — schema drift ⇒ silent data integrity bugs; onboarding pain; impossible to reason about migrations.
- **Technical Impact:** Every service bootstraps the same DB differently; rollback impossible.
- **Difficulty:** High. **Priority:** **P1**.
- **Recommended Solution:** Adopt **Alembic** as the single source of truth. Bootstrap baseline revision = current production schema (autogenerate). Remove runtime DDL from all three services; services assume schema is migrated out‑of‑band. Keep one `init.sql` for greenfield dev only, generated from Alembic.
- **Estimated Effort:** 2 EW.
- **Dependencies:** None; unblocks A3, R5, SC2.

### A3 — Parallel/legacy `database-service` HTTP API
- **Root Cause:** `database-service` exposes `/api/articles`, `/api/analytics/summary`, `/api/search`, `/api/articles/{id}`, `/rebuild-events` that duplicate modular‑api. Frontend only calls modular‑api (`VITE_API_URL=:8000`).
- **Business Impact:** P2 — duplicate surface to secure/test/maintain; inconsistent behavior between two implementations.
- **Technical Impact:** Two code paths reading/writing the same DB with subtly different SQL.
- **Difficulty:** Medium. **Priority:** **P2**.
- **Recommended Solution:** Split database‑service responsibilities: keep **only** the Kafka consumer + persistence logic; delete its HTTP API (move `/rebuild-events` into modular‑api under admin guard). Optionally rename to `persistence-worker` to signal its true role.
- **Estimated Effort:** 1 EW.
- **Dependencies:** A1, A2, S4 (admin guard for `/rebuild-events`).

### A4 — Mixed sync/async DB drivers against the same DB
- **Root Cause:** database‑service uses sync `psycopg2` inside an async FastAPI process (consumer thread); modular‑api uses `asyncpg`. Two drivers, two pooling stories, two bootstraps.
- **Business Impact:** P2 — inconsistent latency, double connection budget, hard to reason about transactions.
- **Technical Impact:** `psycopg2` blocking calls can stall the event loop; asyncpg pool (`max_size=10`) and psycopg2 churn contend for PG `max_connections`.
- **Difficulty:** High. **Priority:** **P2**.
- **Recommended Solution:** Standardize on **asyncpg** for all services (or SQLAlchemy 2.0 async). Extract a shared `backend/shared/db_pool.py` (already exists for modular‑api) and reuse it in database‑service's consumer.
- **Estimated Effort:** 2 EW.
- **Dependencies:** A1, A3.

### A5 — No bounded context / module separation between ingest and API
- **Root Cause:** `backend/` (modular‑api) and `services/*` (pipelines) are separate packages but share no contract library; Pydantic models are redefined inline everywhere.
- **Business Impact:** P2 — Kafka payload drift between producer (ingest/ml) and consumer (database) is undetectable until runtime.
- **Technical Impact:** DTOs duplicated in `dto.py` (mostly dead), routes, ml-service, database-service.
- **Difficulty:** Medium. **Priority:** **P2**.
- **Recommended Solution:** Create a `contracts/` (or `backend/shared/contracts/`) package: Pydantic `RawArticle`, `ProcessedArticle`, `Entity`, `Relationship` published to all services. Optionally enforce with a JSON Schema registry (§A6). Wire `dto.py` to use them.
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** None; pairs with OB1 schema checks.

### A6 — No Kafka schema registry / no contract enforcement
- **Root Cause:** Plain JSON payloads, `auto.create.topics.enable=true`, no Confluent Schema Registry, no consumer‑side validation.
- **Business Impact:** P2 — a producer field rename silently breaks the consumer.
- **Technical Impact:** No compatibility mode (BACKWARD/FORWARD), no evolution story.
- **Difficulty:** High. **Priority:** **P2**.
- **Recommended Solution:** Introduce Schema Registry + Avro/Protobuf (or at minimum Pydantic‑validated JSON with a schema topic). Disable topic auto‑creation; provision `raw_articles`/`processed_articles` explicitly with partitioning.
- **Estimated Effort:** 3 EW.
- **Dependencies:** A5.

### A7 — Coupling: heavy ML inference in the consumer thread
- **Root Cause:** ml-service runs DistilBERT + BERT‑large NER synchronously in the same process that polls Kafka; no batching, no readiness gate.
- **Business Impact:** P3 — throughput ceiling, but not a correctness risk today.
- **Technical Impact:** Consumer blocked during model load → `session.timeout.ms=6000` rebalance storms.
- **Difficulty:** High. **Priority:** **P3**.
- **Recommended Solution:** Externalize ML to a model server (NVIDIA Triton / HuggingFace TEI / a dedicated worker pool with dynamic batching). ml-service becomes a thin orchestrator.
- **Estimated Effort:** 4 EW.
- **Dependencies:** SC4 (broker scaling).

---

## 3. Reliability

### R1 — Kafka consumer threads die silently
- **Root Cause:** Both consumers run in `threading.Thread(daemon=True)` started in `@app.on_event("startup")`. An exception logs and exits the thread; FastAPI stays "healthy" while the pipeline is dead. No `/health` reflects consumer lag.
- **Business Impact:** P1 — silent data‑pipeline outage; ingestion appears fine, no articles flow.
- **Technical Impact:** No restart, no alerting, no consumer‑group lag visibility.
- **Difficulty:** Medium. **Priority:** **P1**.
- **Recommended Solution:**
  1. Move consumers out of the API process into a dedicated worker (or `aiokafka`/`confluent-kafka` in a managed task with supervision).
  2. Expose `/livez` (process up) vs `/readyz` (consumer caught up / model loaded / DB reachable).
  3. Crash the process on consumer failure so the orchestrator restarts it (let Docker/k8s do the restart).
- **Estimated Effort:** 2 EW.
- **Dependencies:** OB1 (metrics to detect lag), DO2 (restart policy).

### R2 — No connection pooling in database-service
- **Root Cause:** `get_postgres_connection()` opens a fresh `psycopg2` connection per SQL operation (upsert, replace‑related, each sub‑query in `update_event_intelligence`, indexing).
- **Business Impact:** P1 — connection churn dominates write latency; PG `max_connections` exhaustion under burst.
- **Technical Impact:** Per‑message TCP + auth handshake × (5–20) queries.
- **Difficulty:** Low–Medium. **Priority:** **P1**.
- **Recommended Solution:** Use `psycopg2.pool.SimpleConnectionPool`/`ThreadedConnectionPool`, or migrate to asyncpg (A4) and reuse `shared/db_pool`.
- **Estimated Effort:** 1 EW.
- **Dependencies:** A4 (preferred path).

### R3 — `/rebuild-events` is destructive and unguarded
- **Root Cause:** `POST /rebuild-events` issues `DELETE FROM event_entities; DELETE FROM event_articles; DELETE FROM events;` then re‑clusters sequentially. No transaction, no auth, no lock.
- **Business Impact:** P1 — a stray call wipes the event graph mid‑run; partial state on crash.
- **Technical Impact:** Long lock‑holding deletes; no idempotency.
- **Difficulty:** Medium. **Priority:** **P1**.
- **Recommended Solution:** Move to modular‑api behind `require_admin`; wrap in a single transaction with savepoints; ship a "stage then swap" pattern (write to a `_next` table, rename). Add advisory lock.
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** S3, A3.

### R4 — Idempotency gaps beyond dedupe_key
- **Root Cause:** `processed_articles` upsert is idempotent on `dedupe_key`, but `replace_related_records` does delete+reinsert of entities/sentiments/relationships — safe per‑article, but `update_event_intelligence` mutates aggregates (event_entities mention_count++, entity_profiles mention_frequency++) that are **not** idempotent across redeliveries.
- **Business Impact:** P1 — redelivery (at‑least‑once Kafka) inflates mention counts and aggregate stats.
- **Technical Impact:** Drifting analytics; non‑reproducible rebuilds.
- **Difficulty:** Medium. **Priority:** **P1**.
- **Recommended Solution:** Track processed `(article_db_id, content_hash)` in a `processed_markers` table; skip aggregate updates when hash unchanged. Make counters `recompute‑from‑base` (compute from `extracted_entities` rather than `+1`).
- **Estimated Effort:** 2 EW.
- **Dependencies:** A1.

### R5 — No database migrations / no rollback path
- **Root Cause:** Schema changes are additive `ADD COLUMN IF NOT EXISTS`; renames/drops can't ship. No Alembic, no `downgrade()`.
- **Business Impact:** P2 — schema evolution risk; can't safely remove deprecated columns.
- **Technical Impact:** Schema bloat; dead columns accumulate.
- **Difficulty:** Medium. **Priority:** **P2** (folded into A1).
- **Recommended Solution:** Delivered by A1 (Alembic with up/down revisions + CI gate that migrations apply on a clean DB).
- **Estimated Effort:** included in A1.
- **Dependencies:** A1.

### R6 — Frontend has no error‑boundary / API resilience strategy
- **Root Cause:** Axios interceptor only handles 401; no retry/backoff, no global error boundary, no skeleton fallback contract beyond ad‑hoc usage.
- **Business Impact:** P2 — degraded UX during partial outages.
- **Technical Impact:** Hard‑edged failures on any 5xx.
- **Difficulty:** Low. **Priority:** **P2**.
- **Recommended Solution:** Add React error boundary, TanStack Query retry policies, and a unified toast/toast‑error pipeline. Add a `/health`‑aware banner.
- **Estimated Effort:** 1 EW.
- **Dependencies:** None.

---

## 4. Scalability

### SC1 — `update_event_intelligence` is O(articles × events) N+1
- **Root Cause:** For each consumed article, scans up to 25 candidate events, computes Jaccard/token/time scores, then runs ~5 queries per entity in Python loops, single‑threaded, on the write path.
- **Business Impact:** P1 — write throughput collapses as event/entity counts grow; backlog → stale intelligence.
- **Technical Impact:** Pipeline bottleneck; backpressure into Kafka.
- **Difficulty:** High. **Priority:** **P1**.
- **Recommended Solution:**
  1. **Short term:** batch the per‑entity queries into set‑based SQL (one `… WHERE entity_text = ANY($1)`).
  2. **Medium term:** move clustering out of the synchronous write path — append to `event_articles` with a provisional score, then run clustering as a periodic batch job (every N minutes) that recomputes aggregates from base tables (idempotent — pairs with R4).
  3. **Long term:** use the pgvector embeddings (SC2) for semantic clustering instead of token Jaccard.
- **Estimated Effort:** 3 EW.
- **Dependencies:** R4, SC2.

### SC2 — pgvector has no ANN index (exact NN scan)
- **Root Cause:** `article_embeddings.embedding vector` lacks HNSW/IVFFlat; `/search` and `/copilot/query` sort by `embedding <=> q` over the whole table.
- **Business Impact:** P2 — semantic search latency grows linearly; Copilot becomes unusable past ~50k articles.
- **Technical Impact:** Sequential vector scan per query.
- **Difficulty:** Low. **Priority:** **P2**.
- **Recommended Solution:** `CREATE INDEX … USING hnsw (embedding vector_cosine_ops)` with tuned `m`/`ef_construction`; bump `ef_search` at query time. Consider IVFFlat for very large corpora. Add this as an Alembic revision.
- **Estimated Effort:** 0.5 EW.
- **Dependencies:** A1.

### SC3 — Missing indexes on hot columns
- **Root Cause:** `processed_articles.sentiment` (filter param in `/articles`) and `extracted_entities.entity_text` (aggregated in `/entities`, `/analytics/entities`, copilot, profile fallback) are unindexed.
- **Business Impact:** P2 — query latency degrades with row count; dashboard/copilot slow.
- **Technical Impact:** Seq scans on analytic queries.
- **Difficulty:** Low. **Priority:** **P2**.
- **Recommended Solution:** Add `btree(sentiment)` on processed_articles; `btree(entity_text)` and `btree(LOWER(entity_text))` on extracted_entities. Ship as Alembic revisions.
- **Estimated Effort:** 0.3 EW.
- **Dependencies:** A1.

### SC4 — Single Kafka broker, RF=1, tight session timeout
- **Root Cause:** `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1`, one broker, `session.timeout.ms=6000`, 1 effective partition.
- **Business Impact:** P2 — no durability (one broker loss = data loss), no consumer parallelism, rebalance storms during model load.
- **Technical Impact:** Cannot scale consumers horizontally.
- **Difficulty:** High. **Priority:** **P2**.
- **Recommended Solution:** Run 3 brokers, RF=3, increase `processed_articles`/`raw_articles` partitions to 6–12, set `session.timeout.ms=30000` + `max.poll.interval`, deploy one consumer per partition.
- **Estimated Effort:** 2 EW (infra + code partition‑awareness).
- **Dependencies:** A6, R1.

### SC5 — Single PostgreSQL with no read replica
- **Root Cause:** Every analytic/dashboard query competes with the ingest consumer on the same instance.
- **Business Impact:** P2 — dashboard latency spikes during ingestion bursts.
- **Technical Impact:** Read/write contention; `dashboard-v2` issues ~13 sequential `fetchval` calls.
- **Difficulty:** High. **Priority:** **P2**.
- **Recommended Solution:** Add a PG read replica (or Postgres‑style pooling via PgBouncer + replica); route read‑only routes via a `read_pool`; consolidate `dashboard-v2` stats into a single query or materialized view refreshed every minute.
- **Estimated Effort:** 2.5 EW.
- **Dependencies:** A4.

### SC6 — Elasticsearch single‑node, implicit mapping, 512 MB heap
- **Root Cause:** Single‑node ES, `ES_JAVA_OPTS=-Xms512m -Xmx512m`, auto‑mapped `processed_articles` index with no tuned analyzers.
- **Business Impact:** P2 — search quality and capacity ceiling; OOM risk.
- **Technical Impact:** No replica shards; field‑weight boosts (`title^3`) applied against default analyzer.
- **Difficulty:** Medium. **Priority:** **P2**.
- **Recommended Solution:** Define an explicit index template (custom analyzers, `multi_match` field weights as field boosts, replicas=1); add a second node; bump heap to 50% of 2 GB container. Reindex once.
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** None.

---

## 5. Code Quality

### CQ1 — `IntelligenceRepository` 1,386‑line god class
- **Root Cause:** Single class holding events, entities, watchlists, alerts, cases, reports, dashboard, timeline, graph, audit, and report‑text generation.
- **Business Impact:** P1 — every change risks unrelated regressions; onboarding is slow.
- **Technical Impact:** Merge conflicts, untestable units.
- **Difficulty:** Medium. **Priority:** **P1**.
- **Recommended Solution:** Split per aggregate (`EventsRepository`, `WatchlistsRepository`, `CasesRepository`, `ReportsRepository`, `AnalyticsRepository`, `AuditRepository`); keep `record_to_dict` in a shared util.
- **Estimated Effort:** 2 EW.
- **Dependencies:** CQ5 (tests to refactor safely).

### CQ2 — `routes/copilot.py` 390‑line route with inline SQL + `print()`
- **Root Cause:** Business logic in the route layer; debug `print()` statements shipped to prod; repeated alias/blacklist maps.
- **Business Impact:** P2 — untestable, slow to evolve, log noise hides signal.
- **Technical Impact:** N+1 `entity_profiles` queries in a Python loop.
- **Recommended Solution:** Extract `CopilotService`; replace prints with structured logging (OB1); consolidate aliases into `shared/contracts/entity_aliases.py` (A5); batch entity‑profile fetch.
- **Difficulty:** Medium. **Priority:** **P2**.
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** CQ1, A5, OB1.

### CQ3 — Duplicated entity alias/blacklist maps (4 places)
- **Root Cause:** `ml-service/app.py`, `database-service/app.py`, `routes/copilot.py`, `routes/graph.py` each redefine aliases/blacklists with divergent contents.
- **Business Impact:** P2 — inconsistent entity normalization across pipeline stages ⇒ split entity profiles, wrong alerts.
- **Technical Impact:** Silent data fragmentation.
- **Recommended Solution:** Single source in `shared/contracts`; load at all sites. Make data‑driven (DB/seed file) so analysts can update without deploys.
- **Difficulty:** Low. **Priority:** **P2**.
- **Estimated Effort:** 0.5 EW.
- **Dependencies:** A5.

### CQ4 — Dead DTO module & inline model duplication
- **Root Cause:** `backend/api_service/dto.py` defines `PageParams`, `ReportGenerateRequest`, `WatchlistCreateRequest`, `AlertCreateRequest`, `CopilotQueryRequest` — mostly unused; routes declare their own inline models.
- **Business Impact:** P3 — confusion, drift between docs and code.
- **Recommended Solution:** Either delete unused DTOs or adopt them everywhere; wire OpenAPI generation to live from the code (DO1 regenerates `openapi.json`).
- **Difficulty:** Low. **Priority:** **P3**.
- **Estimated Effort:** 0.3 EW.
- **Dependencies:** DO1.

### CQ5 — No tests anywhere
- **Root Cause:** No `tests/`, no pytest config, no JS test setup. No coverage gate.
- **Business Impact:** P1 — refactors (most of this plan) are high‑risk without a safety net.
- **Technical Impact:** Regressions ship undetected.
- **Difficulty:** Medium (bootstrapping). **Priority:** **P1**.
- **Recommended Solution:** Add pytest + `pytest-asyncio` + `httpx.AsyncClient` for modular‑api; testcontainers for PG/ES/Kafka. Target 60% coverage on repositories/routes before SC1/CQ1 work. Add Vitest for frontend.
- **Estimated Effort:** 3 EW (initial) + ongoing.
- **Dependencies:** DO1.

### CQ6 — Mixed deprecated lifecycle hooks
- **Root Cause:** `@app.on_event("startup"/"shutdown")` in 4 services; modular‑api correctly uses `lifespan`. Mixed patterns.
- **Recommended Solution:** Migrate all services to the `lifespan` async context manager.
- **Difficulty:** Low. **Priority:** **P2**.
- **Estimated Effort:** 0.5 EW.
- **Dependencies:** R1 (rewrite startup anyway).

### CQ7 — Fake‑data fallbacks in production paths
- **Root Cause:** `routes/analytics.py::get_attack_graph` returns a hardcoded Iran/Israel/Saudi/USA graph when the query is empty; `score_threat`/sentiment have silent fallbacks; analytics returns hardcoded empty shapes on error in some places.
- **Business Impact:** P2 — misleading intel (analysts see phantom graph), silent quality degradation.
- **Recommended Solution:** Return honest empty states; remove the mock graph; gate fallbacks behind an explicit `dev_mode` flag with logged warnings.
- **Difficulty:** Low. **Priority:** **P2**.
- **Estimated Effort:** 0.3 EW.
- **Dependencies:** None.

---

## 6. Cloud Readiness

### CR1 — Configuration not externalized (12‑factor)
- **Root Cause:** All config defaults hard‑coded in compose/source; `.env` empty; no `pydantic-settings`/`dynaconf`; frontend baked `VITE_API_URL` at build time via Docker ARG.
- **Business Impact:** P2 — cannot promote the same image across dev/stage/prod; secrets baked into layers.
- **Technical Impact:** Re‑build per environment; config drift.
- **Difficulty:** Medium. **Priority:** **P2**.
- **Recommended Solution:** Introduce `pydantic-settings` `Settings` per service (env‑driven, typed); inject runtime config to frontend via `window.__ENV__` / a `/config.js` served by nginx, not build args. Wire to Secrets Manager/SSM in cloud.
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** S1.

### CR2 — Stateful services not ready for orchestrated environments
- **Root Cause:** Postgres, ES, Kafka defined as single containers with local volumes; no persistent‑volume strategy, backups, or HA topology.
- **Business Impact:** P3 — no HA, no snapshots, can't survive node loss.
- **Recommended Solution:** Replace stateful containers with **managed services** in cloud (RDS Postgres w/ pgvector support, Amazon OpenSearch / Elastic Cloud, Amazon MSK); keep stateless app containers on ECS/EKS. Define IaC (Terraform) for parity.
- **Difficulty:** High. **Priority:** **P3**.
- **Estimated Effort:** 4 EW.
- **Dependencies:** S1, S5, SC4, SC5, SC6.

### CR3 — Docker images not production‑grade
- **Root Cause:** `python:3.11-slim` bases run as root, no `HEALTHCHECK` except modular‑api, no multi‑stage for Python services, no image labels/digests, no SBOM.
- **Recommended Solution:** Non‑root user, distroless/`python:slim` + `uv`/`pip` wheels, `HEALTHCHECK` on every service (per R1's `/livez`+`/readyz`), pin images by digest, emit SBOM (`syft`), scan (`grype`) in CI.
- **Difficulty:** Medium. **Priority:** **P3**.
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** R1, DO1.

### CR4 — Multi‑region / DR not designed
- **Root Cause:** No defined RPO/RTO; single AZ implicitly.
- **Recommended Solution:** Define DR objectives; design cross‑region PG read replica + MSK mirror + S3/ES snapshot/restore; document runbook. Driven by product SLA.
- **Difficulty:** High. **Priority:** **P3**.
- **Estimated Effort:** 3 EW (design + IaC).
- **Dependencies:** CR2.

---

## 7. DevOps

### DO1 — No CI/CD pipeline
- **Root Cause:** No `.github/workflows`, no GitLab CI, no `.circleci`. `openapi.json` committed and stale; no lint/test gate.
- **Business Impact:** P0 (process) — every item in this plan depends on a CI gate to land safely.
- **Technical Impact:** Regression risk; untracked schema drift; stale specs.
- **Difficulty:** Medium. **Priority:** **P0** (DO1) → enables S7, CQ4, CQ5, A1.
- **Recommended Solution:** GitHub Actions: lint (ruff/flake8, eslint) → test (pytest/vitest) → `pip-audit`/`npm audit` → **Alembic apply on a throwaway PG** → **regenerate `openapi.json` from modular‑api and diff against committed** → SBOM/scan → build images. Block merges on red.
- **Estimated Effort:** 2 EW.
- **Dependencies:** None.

### DO2 — `.gitignore` is a corrupted ASCII tree
- **Root Cause:** `.gitignore` literally contains a pasted project tree (`defense-intel-platform/ │── docker-compose.yml …`) instead of ignore rules. `.dockerignore` likewise begins with prose. Effective ignores rely on luck.
- **Business Impact:** P0 — secrets, `node_modules`, build artifacts, and `.venv` may be tracked or leak into images; S1/S2 mitigations partly ineffective until this is fixed.
- **Technical Impact:** Repo bloat, accidental commits, larger images.
- **Difficulty:** Low. **Priority:** **P0**.
- **Recommended Solution:** Replace `.gitignore` with a proper template (Python + Node + Vite + JetBrains/VSCode + `.env*`, `dist/`, `__pycache__/`, `.docker-config/`); fix `.dockerignore` to be rule‑based. Audit `git ls-files` for things that should never have been tracked; purge.
- **Estimated Effort:** 0.5 EW + history audit.
- **Dependencies:** None; unblocks S1.

### DO3 — No CD / environment promotion strategy
- **Root Cause:** Manual `docker-compose up`; no image registry, no env separation, no IaC.
- **Business Impact:** P2 — no reproducible deploys, no rollback.
- **Recommended Solution:** Push images to a registry tagged by git SHA; define `docker-compose.{dev,stg,prod}.yml` overrides; promote via IaC (Terraform for infra, Helm/Kustomize or ECS task defs for apps). Add rollback runbook.
- **Difficulty:** Medium. **Priority:** **P2**.
- **Estimated Effort:** 2.5 EW.
- **Dependencies:** DO1, CR3.

---

## 8. Observability

### OB1 — No structured logging, metrics, or tracing
- **Root Cause:** Plain `logging.basicConfig` + `print()`; no metrics, no traces, no OTel, no Sentry. Grep‑the‑logs is the only diagnosis path.
- **Business Impact:** P1 — outages (esp. R1 silent consumer death) are invisible until users complain.
- **Technical Impact:** No SLOs, no latency percentiles, no consumer‑lag alert.
- **Difficulty:** Medium. **Priority:** **P1**.
- **Recommended Solution:** Introduce **OpenTelemetry** (auto‑instrumentation for FastAPI + asyncpg + httpx + confluent‑kafka) → OTLP collector → Tempo/Jaeger + Loki + Prometheus; export **consumer lag**, **DB pool saturation**, **ES query latency**, **ml inference latency**, **per‑route p95**. Structured JSON logs (structlog). Sentry for frontend + backend errors.
- **Estimated Effort:** 3 EW.
- **Dependencies:** DO1 (CI to ship it).

### OB2 — No dashboards, alerts, or SLOs
- **Root Cause:** No Grafana/dashboards as code; no alert rules.
- **Business Impact:** P2 — MTTR high; no proactive detection.
- **Recommended Solution:** Grafana dashboards (provisioned via IaC): pipeline health (lag, throughput, errors), API p95/error rate, DB/ES resource usage, model load state. Define SLOs (e.g. dashboard p95 < 500 ms, end‑to‑end ingest < 5 min p95) with PagerDuddy/Slack alerts.
- **Difficulty:** Low. **Priority:** **P2**.
- **Estimated Effort:** 1.5 EW.
- **Dependencies:** OB1.

---

## Roadmap

Roadmap is sequenced so that **each phase unblocks the next**, with P0 work front‑loaded. Total ≈ **55–60 EW** of engineering effort across the four phases; assume parallelism within a phase where dependencies allow (dep chart below).

### Phase 1 — Critical (Weeks 1–4) — *stop the bleeding*
Goal: eliminate security/blocker risk and stand up the safety rails that make every later change shippable.

| Wk | Item | Pri | Diff | EW | Depends |
|---|---|---|---|---|---|
| 1 | **DO2** Fix `.gitignore`/`.dockerignore` + tracked‑file audit | P0 | L | 0.5 | — |
| 1 | **S1** Strip secrets from compose/source → `.env` + manager | P0 | L | 0.5 | DO2 |
| 1 | **S2** Remove + history‑purge `.docker-config/.token_seed`, rotate | P0 | L | 0.5 | S1 |
| 1–2 | **DO1** Stand up CI (lint/test/audit/Alembic‑apply/openapi‑diff/build) | P0 | M | 2 | DO2 |
| 2 | **S3** Enforce JWT on all non‑public routes | P0 | M | 1.5 | — |
| 2 | **S4** Attribute audit + `owner/created_by` from token | P0 | M | 1 | S3 |
| 3 | **S5** Enable ES + Kafka security (flag‑gated for dev) | P0 | M | 2 | S1 |
| 3–4 | **OB1** OTel + structured logs + Sentry | P1 | M | 3 | DO1 |
| 4 | **R1** Supervised consumers + `/livez` `/readyz` | P1 | M | 2 | OB1 |

**Exit criteria:** No secret in repo history; CI green‑blocks merges; no anonymous route; pipeline outage raises an alert within 1 min.

### Phase 2 — Stabilization (Weeks 5–10) — *correctness & testability*
Goal: remove drift, parallel surfaces, silent‑failure modes; build the test net.

| Wk | Item | Pri | Diff | EW | Depends |
|---|---|---|---|---|---|
| 5 | **CQ5** Bootstrap pytest + testcontainers (60% repo/route coverage) | P1 | M | 3 | DO1 |
| 5–6 | **A1** Alembic baseline; remove runtime DDL from 3 services | P1 | H | 2 | DO1 |
| 6 | **R5** Migrations w/ rollback (delivered via A1) | P2 | M | — | A1 |
| 6 | **R2** Connection pool in database‑service | P1 | L–M | 1 | — |
| 6–7 | **R3** Safe + guarded `/rebuild-events` | P1 | M | 1.5 | S3, A3 |
| 7 | **R4** Idempotent aggregates + content‑hash markers | P1 | M | 2 | A1 |
| 7 | **A3** Retire database‑service HTTP API (move `/rebuild-events`) | P2 | M | 1 | A1, S4 |
| 8 | **CQ1** Split `IntelligenceRepository` | P1 | M | 2 | CQ5 |
| 8 | **SC1a** Set‑based SQL to kill N+1 in event intelligence | P1 | M | 1.5 | R4 |
| 9 | **SC3** Add missing indexes (Alembic revisions) | P2 | L | 0.3 | A1 |
| 9 | **SC2** HNSW index on `article_embeddings` | P2 | L | 0.5 | A1 |
| 9–10 | **CQ2** Refactor copilot service + remove prints | P2 | M | 1.5 | CQ1, OB1 |
| 10 | **OB2** Dashboards + SLOs + alerts | P2 | L | 1.5 | OB1 |

**Exit criteria:** Single schema source; one API gateway; tests gate merges; `/rebuild-events` safe; consumer lag + p95 under SLO.

### Phase 3 — Scalability (Weeks 11–18) — *grow safely*
Goal: remove the architectural ceilings so the platform can 10× its data and traffic.

| Wk | Item | Pri | Diff | EW | Depends |
|---|---|---|---|---|---|
| 11 | **SC4** Kafka 3‑broker, RF=3, multi‑partition consumers | P2 | H | 2 | A6, R1 |
| 11–12 | **A6** Schema Registry + Avro/Protobuf (or JSON‑schema gate) | P2 | H | 3 | A5 |
| 12 | **A5** Shared `contracts` package (Pydantic) across services | P2 | M | 1.5 | — |
| 13 | **CQ3** Single entity‑alias/blacklist source | P2 | L | 0.5 | A5 |
| 13 | **SC1b** Move clustering to periodic batch job (idempotent) | P2 | H | 1.5 | SC1a, R4 |
| 14 | **A4** Unify on asyncpg shared pool | P2 | H | 2 | A1, A3 |
| 14–15 | **SC5** PG read replica + read‑pool routing + dashboard‑v2 MV | P2 | H | 2.5 | A4 |
| 15 | **SC6** ES template + 2‑node cluster + heap bump + reindex | P2 | M | 1.5 | — |
| 16 | **R6** Frontend resilience (boundary, retry, toast pipeline) | P2 | L | 1 | — |
| 16 | **CQ6** Migrate to `lifespan` everywhere | P2 | L | 0.5 | R1 |
| 17 | **CQ7** Remove fake‑data fallbacks | P2 | L | 0.3 | — |
| 17 | **CR1** 12‑factor settings + runtime frontend config | P2 | M | 1.5 | S1 |
| 18 | **S6** Rate limiting + concurrency caps | P1 | M | 1 | S3 |
| 18 | **DO3** Image registry + env overrides + IaC promote/rollback | P2 | M | 2.5 | DO1 |

**Exit criteria:** Horizontal consumer scale‑out works; semantic search p95 stable at 100k articles; analytics served from replica; same image runs in dev/stage/prod.

### Phase 4 — Cloud Migration (Weeks 19–28) — *production‑grade + DR*
Goal: move stateful services to managed platforms, harden images, and stand up DR.

| Wk | Item | Pri | Diff | EW | Depends |
|---|---|---|---|---|---|
| 19–20 | **CR2** Managed Postgres (RDS, pgvector) + OpenSearch + MSK via Terraform | P3 | H | 4 | S1, S5, SC4, SC5, SC6 |
| 21 | **CR3** Hardened images (non‑root, distroless, SBOM, digest‑pinned, HEALTHCHECK) | P3 | M | 1.5 | R1, DO1 |
| 22 | **S7** Supply‑chain: Dependabot + pip‑audit + jose→PyJWT | P2 | L | 0.5 | DO1 |
| 22 | **CQ4** DTO consolidation + live OpenAPI generation | P3 | L | 0.3 | DO1 |
| 23–24 | **A7** Externalize ML to Triton/TEI; ml-service becomes orchestrator | P3 | H | 4 | SC4 |
| 25–26 | **CR4** DR design + IaC: cross‑region replica, MSK mirror, ES snapshots; runbook | P3 | H | 3 | CR2 |
| 27 | Cost & capacity review; autoscaling policies (ECS/EKS HPA on lag + CPU) | P3 | M | 1.5 | CR2, CR3 |
| 28 | Production cutover + sign‑off; deprecate docker‑compose prod path | P3 | M | 1.5 | all |

**Exit criteria:** Stateful services managed/HA; images SBOM‑scanned; DR runbook tested; autoscaling on lag/CPU.

---

## Dependency Graph (phase‑to‑phase)

```
Phase 1 (P0 enablers)
  DO2 ─┬─► S1 ─┬─► S2
       │       ├─► S5 ─────────────────┐
       │       └─► CR1 (P3)            │
  DO1 ─┼─► CQ5, A1, OB1, S7            │
  S3 ──┴─► S4                          │
  OB1 ─► R1                            │
        │                              │
        ▼ Phase 2                      ▼
  A1 ─┬─► R5, SC3, SC2, R4             │
  CQ5 ┴─► CQ1, CQ2                     │
  R4 ──► SC1a ─► SC1b                  │
  A2,A3,S4 ─► R3                       │
  OB1 ─► OB2                            │
        │                              │
        ▼ Phase 3                      │
  A5 ─┬─► A6 ─► SC4 ──────────────────┘
  A4 ─► SC5 ;  SC6 ;  CR1, DO3, S6     │
        │                              │
        ▼ Phase 4                      ▼
  CR2 ─► CR3, CR4, A7 ; S7, CQ4
```

## Quick‑Win Batch (first 5 days, before Phase 1 formally starts)
These are near‑zero‑risk changes that immediately reduce blast radius and can ship in a single PR each:
1. **DO2** — replace broken `.gitignore`/`.dockerignore`.
2. **S1 + S2** — externalize all secrets, rotate GNews + DB password, purge `.token_seed`.
3. **SC3** — add `sentiment` and `extracted_entities(entity_text)` indexes.
4. **CQ7** — delete the fake Iran/Israel graph fallback.

---

## Risk Notes for Planning
- **Alembic baseline (A1) is the single highest‑leverage item** — it de‑risks A3, R4, R5, SC1, SC2, SC3, A4. Do not let Phase 2 slip on it.
- **R1 + OB1 are joint P1s**: supervising consumers without lag metrics just moves the blind spot. Land together.
- **SC1 is split deliberately** (a: kill N+1 in‑place; b: relocate clustering to a batch job). The "b" step must follow R4 or redeliveries will double‑count.
- **CR2 (managed services) absorbs SC4/SC5/SC6 effort** — if Phase 4 is funded early, downgrade Phase 3 stateful items to "good‑enough" and let the managed services deliver the real scaling.

*No source, schema, or configuration files were modified in the production of this plan.*
