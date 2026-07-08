# Database Guide

## Connection

**Database:** `defenseintel`
**Default credentials:** `admin` / `admin123`
**Host:** `localhost:5432` (dev) or `postgres:5432` (Docker)

**Connection string format:**
```
postgresql://admin:admin123@localhost:5432/defenseintel
```

Programmatic DSN construction uses `build_dsn()` from `backend.shared.database.postgres`:
```python
from backend.shared.database import build_dsn
dsn = build_dsn(host="localhost", port=5432, db="defenseintel", user="admin", password="admin123")
```

## Schema Initialization Flow

1. **Docker startup:** PostgreSQL container runs `infra/sql/init.sql` via `docker-entrypoint-initdb.d/`, creating the `public` schema tables
2. **Energy service startup:** `bootstrap()` calls `infra/sql/energy_schema.sql` — creates `energy` schema, ENUM types, tables, indexes, and optionally loads seed data
3. **ML Platform startup:** `ensure_schema()` calls `infra/sql/ml_schema.sql` — creates `ml` schema, ENUM types, tables, indexes

---

## Public Schema

Owned by **database-service** (writer), read by **modular-api** (reader). Created via `infra/sql/init.sql`.

### Tables

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `users` | User accounts | `id`, `email`, `username`, `password_hash`, `role` |
| `processed_articles` | Main article store | `id`, `title`, `content`, `source`, `published_at`, `ml_processed`, `confidence`, `sentiment`, `topic`, `threat_score`, `risk_level`, `dedupe_key` |
| `extracted_entities` | NER entities per article | `id`, `article_id` (FK), `entity_text`, `entity_type`, `confidence` |
| `article_sentiments` | Sentiment per article | `id`, `article_id` (FK), `sentiment_label`, `sentiment_score` |
| `relationships` | Entity relationships | `id`, `article_id` (FK), `source_entity`, `target_entity`, `relationship_type`, `confidence`, `evidence` |
| `events` | Correlated event clusters | `id`, `title`, `summary`, `topic`, `risk_score`, `risk_level`, `first_seen`, `last_seen`, `article_count` |
| `event_articles` | Many-to-many: events × articles | `event_id` (FK), `article_id` (FK), `similarity_score` |
| `event_entities` | Entities per event | `event_id` (FK), `entity_text`, `entity_type`, `mention_count` |
| `entity_profiles` | Entity aggregation | `entity_text` (PK), `entity_type`, `aliases`, `mention_frequency`, `risk_trend` |
| `reports` | Generated intelligence reports | `id`, `title`, `executive_summary`, `key_actors` (JSONB), `key_events` (JSONB), `recommendations` (JSONB) |
| `watchlists` | Entity watchlists | `id`, `name`, `description`, `owner_id` (FK) |
| `watchlist_entities` | Entities on watchlists | `watchlist_id` (FK), `entity_text` |
| `alerts` | Generated alerts | `id`, `watchlist_id` (FK), `event_id` (FK), `alert_type`, `message`, `risk_score`, `status` |
| `cases` | Investigation cases | `id`, `title`, `description`, `status`, `priority`, `owner_id` (FK) |
| `case_items` | Items linked to cases | `case_id` (FK), `item_type`, `item_id` |
| `case_notes` | Notes on cases | `id`, `case_id` (FK), `note_text`, `created_by` (FK) |
| `audit_logs` | Mutation audit trail | `id`, `user_id` (FK), `action`, `resource`, `metadata` (JSONB) |
| `article_embeddings` | pgvector embeddings | `id`, `article_id` (FK, UNIQUE), `embedding vector(384)` |
| `copilot_conversations` | AI copilot chat sessions | `id`, `user_id` (FK), `title` |
| `copilot_messages` | Chat messages | `id`, `conversation_id` (FK), `role`, `content`, `metadata` (JSONB) |

### Key Indexes

- `idx_processed_articles_dedupe_key` — UNIQUE on `dedupe_key`
- `idx_processed_articles_published_at DESC` — time-ordered queries
- `idx_processed_articles_topic`, `risk_level`, `sentiment` — filtered queries
- `idx_article_embeddings_embedding_hnsw` — HNSW index on `vector(384)` for similarity search
- Lowercase indexes on `watchlist_entities.entity_text` and `event_entities.entity_text`

---

## Energy Schema

Owned by **energy-service**. Created via `infra/sql/energy_schema.sql`. Lives in the `energy.` namespace.

### ENUM Types

| Enum | Values |
|------|--------|
| `energy.lifecycle_state` | `draft`, `verified`, `operational`, `deprecated`, `archived` |
| `energy.operational_status` | `active`, `maintenance`, `offline`, `damaged`, `under_construction`, `mothballed`, `decommissioned` |
| `energy.criticality_level` | `low`, `medium`, `high`, `critical` |
| `energy.organization_type` | `national_oil_company`, `international_oil_company`, `independent`, `trader`, `utility`, `government`, `regulatory_body`, `consortium` |
| `energy.relationship_type` | `supplies`, `connects_to`, `located_in`, `owned_by`, `operated_by`, `feeds_into`, `receives_from`, `monitored_by`, `regulated_by`, `adjacent_to`, `crosses` |
| `energy.event_type` | `shutdown`, `maintenance`, `cyber_attack`, `expansion`, `inspection`, `explosion`, `natural_disaster`, `sanctions`, `conflict`, `piracy`, `labor_strike`, `oil_spill` |
| `energy.severity_level` | `low`, `medium`, `high`, `critical` |
| `energy.location_type` | `country`, `eez`, `sea`, `region`, `economic_zone`, `strategic_area`, `strait`, `canal`, `territory` |
| `energy.asset_type` | `port`, `oil_field`, `gas_field`, `pipeline`, `refinery`, `power_plant`, `storage_facility`, `strategic_petroleum_reserve`, `import_corridor`, `shipping_route`, `supplier`, `location`, `organization` |

### Infrastructure Entity Tables

All 14 entity tables share a common column pattern:

| Column Pattern | Description |
|----------------|-------------|
| `id BIGSERIAL` | Auto-increment PK |
| `uuid UUID UNIQUE DEFAULT gen_random_uuid()` | Stable public identifier |
| `name TEXT NOT NULL`, `slug TEXT UNIQUE NOT NULL` | Human + URL identifiers |
| `latitude DOUBLE PRECISION`, `longitude DOUBLE PRECISION` | Coordinates (no PostGIS) |
| `geojson JSONB` | GeoJSON for polygons/lines |
| `status energy.lifecycle_state` | Lifecycle tracking |
| `operational_status energy.operational_status` | Operational state |
| `criticality energy.criticality_level` | Importance rating |
| `is_deleted BOOLEAN`, `deleted_at TIMESTAMPTZ` | Soft delete |
| `version INTEGER DEFAULT 1` | Optimistic locking |
| `source_type`, `source_name`, `source_url`, `source_version` | Data provenance |
| `tags TEXT[]`, `external_references JSONB` | Metadata |
| `risk_metadata JSONB`, `graph_metadata JSONB` | Risk + graph context |
| `created_by`, `updated_by TEXT DEFAULT 'system'` | Audit trail |

Entity-specific tables:

| Table | Specific Columns |
|-------|-----------------|
| `energy.locations` | `location_type`, `parent_location_id`, `iso_code`, `iso_code_3`, `region` |
| `energy.organizations` | `organization_type`, `country_id` |
| `energy.commodities` | `commodity_type`, `unit`, `benchmark_price`, `api_gravity`, `sulfur_content` |
| `energy.ports` | `port_type`, `throughput_mtpa`, `storage_capacity_barrels`, `max_draft_m` |
| `energy.oil_fields` | `reserve_estimate_barrels`, `production_bpd`, `api_gravity`, `sulfur_content` |
| `energy.gas_fields` | `reserve_estimate_cf`, `production_mcfd` |
| `energy.pipelines` | `length_km`, `capacity_bpd`, `diameter_inches`, `commodity_type`, `flow_direction` |
| `energy.refineries` | `capacity_bpd`, `nelson_complexity_index`, `crude_types_accepted` |
| `energy.power_plants` | `capacity_mw`, `fuel_type`, `plant_type` |
| `energy.storage_facilities` | `capacity_barrels`, `facility_type` |
| `energy.strategic_petroleum_reserves` | `capacity_barrels`, `current_inventory_barrels`, `max_drawdown_rate_bpd` |
| `energy.import_corridors` | `origin_location_id`, `destination_location_id`, `distance_km`, `transit_time_days` |
| `energy.shipping_routes` | `origin_port_id`, `destination_port_id`, `distance_nm`, `insurance_multiplier`, `risk_score` |
| `energy.suppliers` | `supplier_type`, `market_share_pct` |

### Relationship & Event Tables

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `energy.entity_relationships` | Links between entities | `source_entity_type`, `source_entity_id`, `target_entity_type`, `target_entity_id`, `relationship_type`, `confidence`, `valid_from`, `valid_to` |
| `energy.infrastructure_events` | Events affecting entities | `entity_type`, `entity_id`, `event_type`, `severity`, `occurred_at`, `resolved_at` |
| `energy.capacity_history` | Time-series capacity data | `entity_type`, `entity_id`, `metric_type`, `value`, `unit`, `recorded_at` |

---

## ML Schema

Owned by **ml-platform**. Created via `infra/sql/ml_schema.sql`. Lives in the `ml.` namespace.

### ENUM Types

| Enum | Values |
|------|--------|
| `ml.feature_type` | `numerical`, `categorical`, `boolean`, `timestamp`, `geospatial`, `entity_statistics`, `relationship_statistics`, `historical_capacity`, `infrastructure`, `embedding_reference`, `graph_placeholder` |
| `ml.model_stage` | `development`, `validation`, `staging`, `production`, `archived` |
| `ml.model_type` | `logistic_regression`, `decision_tree`, `random_forest`, `xgboost`, `lightgbm`, `catboost` |
| `ml.split_type` | `train`, `validation`, `test` |

### Tables

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `ml.feature_definitions` | Versioned feature registry | `name`, `version`, `feature_type`, `transform_config` (JSONB), `is_active` — UNIQUE(`name`, `version`) |
| `ml.datasets` | Dataset metadata | `name`, `version`, `path`, `schema_json` (JSONB), `feature_versions` (JSONB), `total_records`, split counts — UNIQUE(`name`, `version`) |
| `ml.model_versions` | Model registry with lifecycle | `name`, `version`, `model_type`, `stage`, `metrics` (JSONB), `parameters` (JSONB), `mlflow_run_id`, `artifact_path`, `git_commit_hash` — UNIQUE(`name`, `version`) |
| `ml.predictions` | Prediction audit log | `model_version_id` (FK), `model_name`, `input_data` (JSONB), `prediction`, `confidence`, `probabilities` (JSONB), `latency_ms` |

---

## Common Queries for Debugging

### Check table sizes
```sql
SELECT schemaname, relname, n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;
```

### Recent articles
```sql
SELECT id, title, source, sentiment, topic, risk_level, published_at
FROM processed_articles
ORDER BY published_at DESC
LIMIT 20;
```

### Articles not yet ML-processed
```sql
SELECT COUNT(*) FROM processed_articles WHERE ml_processed = FALSE;
```

### Consumer lag (check via Kafka tools — see KAFKA_GUIDE.md)
```bash
kafka-consumer-groups --bootstrap-server localhost:9092 --group ml-service-group --describe
```

### Entities by type
```sql
SELECT entity_type, COUNT(*) as count
FROM extracted_entities
GROUP BY entity_type
ORDER BY count DESC;
```

### Energy entities by type
```sql
SELECT table_name, (SELECT COUNT(*) FROM energy.ports) as ports,
       (SELECT COUNT(*) FROM energy.oil_fields) as oil_fields,
       (SELECT COUNT(*) FROM energy.pipelines) as pipelines
FROM information_schema.tables
WHERE table_schema = 'energy' AND table_type = 'BASE TABLE';
```

### ML model versions in production
```sql
SELECT name, version, model_type, stage, metrics->>'accuracy' as accuracy
FROM ml.model_versions
WHERE stage = 'production';
```

### Check for schema existence
```sql
SELECT schema_name FROM information_schema.schemata
WHERE schema_name IN ('public', 'energy', 'ml');
```

### Connection pool status
```sql
SELECT state, COUNT(*) as count
FROM pg_stat_activity
WHERE datname = 'defenseintel'
GROUP BY state;
```
