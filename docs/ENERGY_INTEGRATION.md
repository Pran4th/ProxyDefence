# Energy Intelligence Integration

## 1. Architecture Overview

ProxyDefence keeps the existing distributed pipeline intact and adds Energy Intelligence as an enrichment layer. The canonical energy catalog is owned by `energy-service` and stored in the `energy` PostgreSQL schema. The article-to-energy bridge is stored in public tables consumed by `database-service`, `modular-api`, Copilot, and the frontend.

```text
Frontend
  -> modular-api
  -> ingest-service
  -> Kafka raw_articles
  -> ml-service
  -> Kafka processed_articles
  -> database-service consumer
       -> processed_articles / entities / relationships
       -> event intelligence
       -> energy enrichment
       -> Elasticsearch indexing
  -> embedding-service semantic search
  -> Copilot
  -> Frontend
```

## 2. Pipeline Before Integration

Before Energy Intelligence, processed articles were stored, related entities and relationships were replaced, event intelligence was updated, and the article was indexed for search. Copilot used semantic search results, extracted entities, relationships, events, and entity profiles to build its response.

```text
processed_articles Kafka topic
  -> upsert_article
  -> replace_related_records
  -> update_event_intelligence
  -> index_article
```

## 3. Pipeline After Integration

The database consumer now links extracted entities to `energy.*` assets after event intelligence and before Elasticsearch indexing.

```text
processed_articles Kafka topic
  -> upsert_article
  -> replace_related_records
  -> update_event_intelligence
  -> enrich_energy_context
       -> energy_entity_mappings
       -> article_energy_enrichments
  -> index_article
```

## 4. Modified Files

Energy-specific or Energy-adjacent files reviewed and changed:

- `services/database-service/services/energy_enrichment.py`
- `services/database-service/consumer.py`
- `services/energy-service/models.py`
- `services/energy-service/routers/catalog.py`
- `services/energy-service/routers/relationships.py`
- `services/energy-service/routers/events.py`
- `services/energy-service/routers/history.py`
- `services/energy-service/routers/bulk.py`
- `backend/api/articles/repository.py`
- `backend/api/articles/service.py`
- `backend/api/copilot/repository.py`
- `backend/api/copilot/service.py`
- `backend/api/copilot/router.py`
- `backend/shared/migrations/versions/0005_energy_intelligence.py`
- `infra/sql/init.sql`
- `services/frontend/src/lib/api.ts`
- `services/frontend/src/lib/api-energy.ts`
- `services/frontend/src/types/energy.ts`

## 5. New APIs

Energy catalog APIs from `energy-service`:

- `GET /api/v1/energy/{table}`
- `GET /api/v1/energy/{table}/{uuid}`
- `POST /api/v1/energy/{table}`
- `PUT /api/v1/energy/{table}/{uuid}`
- `PATCH /api/v1/energy/{table}/{uuid}`
- `DELETE /api/v1/energy/{table}/{uuid}`
- `GET /api/v1/energy/{table}/{uuid}/relationships`
- `POST /api/v1/energy/relationships`
- `GET /api/v1/energy/graph/network`
- `GET /api/v1/energy/{table}/{uuid}/events`
- `POST /api/v1/energy/events`
- `GET /api/v1/energy/{table}/{uuid}/history`
- `POST /api/v1/energy/history`
- `POST /api/v1/energy/bulk/import`
- `GET /api/v1/energy/bulk/export`

Existing API responses extended:

- `GET /articles/{id}` includes `energy_context`.
- `POST /copilot/query` includes `energy_impact` and `energy_assessment`.
- `POST /copilot/query/stream` emits `energy_impact`.

## 6. Database Changes

Canonical Energy schema:

- Schema: `energy`
- Core tables: `locations`, `organizations`, `commodities`
- Infrastructure tables: `ports`, `oil_fields`, `gas_fields`, `pipelines`, `refineries`, `power_plants`, `storage_facilities`, `strategic_petroleum_reserves`, `import_corridors`, `shipping_routes`, `suppliers`
- Operational tables: `entity_relationships`, `infrastructure_events`, `capacity_history`

Bridge tables in `public`:

- `energy_entity_mappings`
- `article_energy_enrichments`

The bridge tables reference `processed_articles(id)` with `ON DELETE CASCADE`.

## 7. Migrations

- `0003_energy_domain.py` creates the `energy` schema, enums, tables, and indexes.
- `0005_energy_intelligence.py` creates public bridge tables and indexes.
- `infra/sql/init.sql` contains matching idempotent bridge-table DDL for fresh local databases.

Runtime validation found that the current local database had no `alembic_version` table and predated the `0005` bridge tables. To keep `start-local.ps1` production-ready for existing local databases, `energy_enrichment.py` now has a narrow, idempotent `ensure_energy_bridge_schema()` bootstrap before enrichment writes.

## 8. Kafka Interactions

Energy Intelligence does not add Kafka topics. It consumes the existing database-service stage:

- Input topic: `processed_articles`
- Consumer group: `db-service-group`
- Handler: `services/database-service/consumer.py`

The handler sequence is:

```text
upsert_article(data)
replace_related_records(article_id, data)
update_event_intelligence(article_id)
enrich_energy_context(article_id)
index_article(data)
```

## 9. Enrichment Stages

1. Read extracted entities for the article.
2. Match each entity against `energy.locations`, infrastructure tables, `energy.organizations`, `energy.commodities`, and `energy.suppliers`.
3. Store one row per match in `energy_entity_mappings`.
4. Aggregate matched locations, infrastructure, organizations, commodities, and recent infrastructure events.
5. Store the per-article JSON context in `article_energy_enrichments`.
6. Copilot aggregates contexts across semantically retrieved articles.

## 10. Complete Request Lifecycle

1. A user or scheduled job triggers article ingestion.
2. `ingest-service` publishes raw articles to Kafka.
3. `ml-service` classifies and enriches the article text.
4. `database-service` persists the processed article and extracted entities.
5. `database-service` links extracted entities to Energy assets.
6. `embedding-service` indexes article embeddings for semantic search.
7. `modular-api` serves article, search, Copilot, and graph requests.
8. Frontend renders article and Copilot responses.

## 11. Complete Response Lifecycle

Article detail:

```text
frontend -> modular-api /articles/{id}
  -> processed_articles
  -> article_energy_enrichments
  -> response.energy_context
```

Copilot:

```text
frontend -> modular-api /copilot/query
  -> embedding-service /search
  -> processed_articles ids
  -> entities / relationships / events
  -> article_energy_enrichments
  -> energy_impact + energy_assessment
```

## 12. How Copilot Uses Energy Data

Copilot loads `article_energy_enrichments` for semantic-search article IDs. It computes:

- `severity`
- `countries_involved`
- `infrastructure_affected`
- `organizations_involved`
- `commodities_involved`
- `infrastructure_event_count`
- `total_energy_articles`

The generated summary appends an Energy Impact section when context exists.

## 13. How Frontend Consumes Energy Data

Frontend types include:

- `Article.energy_context`
- `EnergyImpact`
- Energy catalog types in `services/frontend/src/types/energy.ts`
- Catalog client helpers in `services/frontend/src/lib/api-energy.ts`

The frontend dev server runs on `http://localhost:8080` in this workspace.

## 14. Testing Performed

Validated on July 5, 2026 local environment:

- `scripts/dev/start-local.ps1 -Force -SkipInfra` completed.
- Docker infrastructure healthy: PostgreSQL, Kafka, Elasticsearch.
- Health checks returned `200` for modular API, ingest, ML, database, embedding, energy, ML platform, and frontend.
- `energy-service` catalog query returned JSON objects for JSONB fields after restart.
- Controlled enrichment for article `455` produced:
  - `Russia` as a `location`
  - `Russia to Europe (Pipeline)` as `import_corridor`
  - `article_energy_enrichments.context` with `countries_mentioned` and `infrastructure_mentioned`
- Frontend `npm run build` passed.

Python pytest was attempted for targeted tests but blocked by missing local dependency `pytest_asyncio`.

## 15. Bugs Fixed

- Fixed location asset type mismatch: `energy.locations` now maps to `location`, not `locations`.
- Added suppliers to infrastructure aggregation instead of incorrectly grouping them as organizations.
- Fixed JSON serialization of UUID and datetime values from enrichment rows.
- Fixed UUID lookup failures by casting array and scalar UUID parameters in enrichment queries.
- Added idempotent bridge-table bootstrap for existing databases that have not run Alembic `0005`.
- Hardened Energy catalog, relationship, event, history, and bulk write endpoints with column allowlists.
- Normalized plural route table names to singular `energy.asset_type` enum values for relationship/event/history reads.
- Added asset-type validation for Energy relationship, event, and history writes.
- Converted JSONB request fields before dynamic asyncpg inserts and decoded JSONB response strings at the API boundary.

## 16. Remaining Technical Debt

- Alembic is not initialized in the current local database; a formal migration command should be added to local startup once the repo standardizes migration ownership.
- `start-local.ps1` can launch duplicate reload child processes if old windows survive cleanup.
- `scripts/dev/status.ps1` has a frontend reporting bug when a response object is accidentally used as a console color.
- Python test dependencies should be installed consistently so unit/integration tests can run without manual package repair.
- Energy entity matching is exact/partial string matching. It is deterministic but not semantic.

## 17. Future Improvements

- Add a migration gate to `start-local.ps1` that initializes Alembic safely and applies pending migrations.
- Add tests for Energy enrichment against a temporary Postgres schema.
- Add phrase/alias scoring for high-value infrastructure names.
- Add GIN indexes for bridge-table JSONB context if API filtering expands.
- Include Energy context in Elasticsearch documents if search result snippets need it directly.
