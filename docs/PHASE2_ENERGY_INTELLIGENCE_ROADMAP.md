# Phase 2: Energy Intelligence Platform — Architecture & Implementation Roadmap

> **Status:** Planning document — no code has been implemented for Phase 2.
>
> **Prerequisite:** Phase 1 complete (Energy Service catalog, enrichment pipeline, modular-api gateway, frontend pages).
>
> **Design principle:** All Phase 2 capabilities extend the existing Energy Service (port 8006) and the `energy.` database schema. No new microservices are created unless explicitly stated. ML models are planned but NOT implemented in Phase 2 — Phase 2 builds the intelligence *architecture* that future ML models will consume.

---

## Table of Contents

1. [Architectural Overview](#1-architectural-overview)
2. [Capability 1: Geopolitical Risk Intelligence Agent](#2-capability-1-geopolitical-risk-intelligence-agent)
3. [Capability 2: Energy Supply Chain Knowledge Graph](#3-capability-2-energy-supply-chain-knowledge-graph)
4. [Capability 3: Infrastructure Event Intelligence](#4-capability-3-infrastructure-event-intelligence)
5. [Capability 4: Supply Chain Digital Twin](#5-capability-4-supply-chain-digital-twin)
6. [Capability 5: Procurement Recommendation Engine](#6-capability-5-procurement-recommendation-engine)
7. [Capability 6: Strategic Petroleum Reserve Optimizer](#7-capability-6-strategic-petroleum-reserve-optimizer)
8. [Implementation Phasing](#8-implementation-phasing)
9. [Cross-Cutting Concerns](#9-cross-cutting-concerns)
10. [Appendix: Current Schema Reference](#10-appendix-current-schema-reference)

---

## 1. Architectural Overview

### 1.1 Current State (Phase 1 Complete)

```
Frontend (port 8080)
  └─ modular-api (port 8000)          ← Gateway / auth / routing
       ├─ articles service            ← Article CRUD + energy context injection
       ├─ copilot service             ← Energy impact + assessment (rule-based)
       ├─ graph service               ← Article-based knowledge graph
       └─ energy proxy                ← Reverse proxy to Energy Service

Kafka pipeline
  ingest → ml → database-service      ← Article processing + enrichment
       └─ enrich_energy_context()     ← NER → energy_entity_mappings → article_energy_enrichments

Energy Service (port 8006)
  ├─ 14 entity tables (locations → suppliers)
  ├─ entity_relationships
  ├─ infrastructure_events
  └─ capacity_history
```

### 1.2 Phase 2 Additions

```
Energy Service (port 8006) — EXTENDED with:
  ├─ risk_scores                      ← NEW table (per-entity, per-dimension)
  ├─ supply_chain_graph               ← NEW table (typed edges with weight/propagation)
  ├─ incident_detection               ← NEW table (article-derived infrastructure events)
  ├─ simulation_scenarios             ← NEW table (digital twin what-if state)
  ├─ procurement_recommendations      ← NEW table (alternative suppliers, routes)
  └─ spr_optimization_runs            ← NEW table (drawdown/replenishment plans)

Energy Intelligence Worker (NEW consumer, port 8007 or embedded)
  └─ Subscribes to processed_articles (Kafka)
  └─ Runs risk scoring, event detection, graph propagation

Modular API — EXTENDED with:
  ├─ /api/v1/intelligence/*           ← Risk, recommendations, SPR, digital twin
  └─ /api/v1/energy/*                 ← Existing (unchanged)

Frontend — EXTENDED with:
  ├─ /intelligence/*                  ← Risk dashboards, recommendations, SPR, digital twin
  └─ /energy/*                        ← Existing pages enhanced with risk overlays

Future ML Platform (Phase 3+)
  ← Consumes risk_scores, incident_detection, simulation_results for training
```

### 1.3 Service Ownership Map

| Capability | Primary Owner | Supporting Services |
|---|---|---|
| Geopolitical Risk Intelligence | Energy Service (new module) | Database Service (article pipeline) |
| Supply Chain Knowledge Graph | Energy Service (new module) | — |
| Infrastructure Event Intelligence | Database Service (extended) | Energy Service (event storage) |
| Supply Chain Digital Twin | Energy Service (new module) | — |
| Procurement Recommendation Engine | Energy Service (new module) | — |
| SPR Optimizer | Energy Service (new module) | — |

### 1.4 Key Design Decisions

1. **Energy Service is the single source of truth** for all energy domain data. Every intelligence capability lives here or is owned here.
2. **No new microservices** — all capabilities are modules within the Energy Service or extensions of the Database Service pipeline. The exception is a lightweight `energy-intelligence-worker` if Kafka subscription is needed.
3. **Rule-based first, ML later** — all risk scoring, recommendations, and optimization begin with deterministic rules. ML models (Phase 3+) replace or augment rules as data accumulates.
4. **Extend the `energy.` schema** — all new tables use the existing `energy.` schema, dual identifiers (BIGSERIAL+UUID), soft delete, and data provenance columns.
5. **Risk scores are persisted, not computed on-the-fly** — each entity gets periodic risk recalculations stored in `energy.risk_scores`. Query-time aggregation is avoided for performance.
6. **Kafka is the pipeline backbone** — the existing `processed_articles` topic is consumed by energy intelligence workers. New topics are added only if processing volume justifies decoupling.

---

## 2. Capability 1: Geopolitical Risk Intelligence Agent

### 2.1 Description

A risk scoring system that assigns geopolitical risk scores across five dimensions for every energy infrastructure entity:

| Risk Dimension | Description | Example |
|---|---|---|
| **Corridor Risk** | Likelihood of disruption along an import corridor | Strait of Hormuz blockage probability |
| **Supplier Risk** | Reliability/stability of a supplier country or organization | Russia sanctions risk |
| **Country Risk** | Geopolitical stability of a country | Iran political instability score |
| **Maritime Route Risk** | Piracy, chokepoint, insurance cost risk | Malacca Strait transit risk |
| **Infrastructure Risk** | Physical/cyber vulnerability of an asset | Pipeline sabotage risk score |

### 2.2 How It Fits Into the Existing Architecture

- **Risk scoring module** lives in `services/energy-service/routers/risk.py` and `services/energy-service/services/risk_engine.py`
- **Consumes** existing entity data (locations, suppliers, shipping_routes, import_corridors, infrastructure events)
- **Outputs** persisted risk scores in `energy.risk_scores` table
- **Triggered** by:
  - On-demand API call (`POST /api/v1/intelligence/risk/score-all`)
  - Periodic schedule (configurable cron via background task)
  - New infrastructure event (recalculates affected entities)
- **Copilot integration**: The existing `compute_energy_impact()` in `backend/api/copilot/service.py` is augmented to read risk scores from `energy.risk_scores` instead of the current simple count-based severity

### 2.3 Required Database Schema Changes

```sql
-- Schema: energy
-- New ENUM type
CREATE TYPE energy.risk_dimension AS ENUM (
    'corridor', 'supplier', 'country', 'maritime_route', 'infrastructure'
);

-- New table: per-entity risk scores
CREATE TABLE energy.risk_scores (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    entity_type     energy.asset_type NOT NULL,       -- which kind of entity
    entity_id       BIGINT NOT NULL,                   -- FK to the entity table's id
    dimension       energy.risk_dimension NOT NULL,     -- which risk dimension
    score           DOUBLE PRECISION NOT NULL,          -- 0.0 (safe) to 1.0 (critical)
    confidence      DOUBLE PRECISION DEFAULT 0.5,       -- 0.0 to 1.0
    factors         JSONB DEFAULT '[]'::jsonb,          -- [{name, weight, contribution}]
    trend           VARCHAR(10) DEFAULT 'stable',       -- 'improving', 'stable', 'worsening'
    score_updated   TIMESTAMPTZ DEFAULT NOW(),
    valid_until     TIMESTAMPTZ,                        -- NULL = current, non-NULL = superseded
    created_by      TEXT DEFAULT 'risk-engine',
    updated_by      TEXT DEFAULT 'risk-engine',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (entity_type, entity_id, dimension, valid_until)
);

-- Indexes
CREATE INDEX idx_risk_scores_entity ON energy.risk_scores (entity_type, entity_id);
CREATE INDEX idx_risk_scores_dimension ON energy.risk_scores (dimension);
CREATE INDEX idx_risk_scores_score_desc ON energy.risk_scores (score DESC) WHERE valid_until IS NULL;
CREATE INDEX idx_risk_scores_current ON energy.risk_scores (entity_type, dimension) WHERE valid_until IS NULL;

-- New table: risk factor definitions (model registry for risk factors)
CREATE TABLE energy.risk_factors (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,              -- e.g. 'proximity_to_conflict', 'chokepoint_dependency'
    description     TEXT,
    weight          DOUBLE PRECISION DEFAULT 1.0,       -- default weight in composite score
    data_source     TEXT,                               -- 'fixed', 'event_count', 'article_sentiment', etc.
    config          JSONB DEFAULT '{}'::jsonb,          -- parameters for this factor
    is_active       BOOLEAN DEFAULT TRUE,
    version         INTEGER DEFAULT 1,
    created_by      TEXT DEFAULT 'system',
    updated_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**Modifications to existing tables:**
- `energy.shipping_routes` — add `risk_score` field per-dimension (currently has a single `risk_score DOUBLE PRECISION`, used as baseline)
- `energy.import_corridors` — add `risk_score DOUBLE PRECISION DEFAULT 0.0`
- `energy.suppliers` — add `risk_score DOUBLE PRECISION DEFAULT 0.0`

### 2.4 Kafka Event Changes

**No new topics.** The risk engine recalculates on:
- API trigger — `POST /api/v1/intelligence/risk/score-all`
- Infrastructure event created — inline recalculation in the event POST handler
- Periodic background task — every 15 minutes via `asyncio.create_task` in the Energy Service lifespan

**Future consideration:** If recalculation volume becomes high, introduce `energy.risk_recalculation_requests` as a Kafka topic consumed by a dedicated `energy-intelligence-worker`.

### 2.5 API Changes

**New endpoints** (Energy Service, port 8006):

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/intelligence/risk/{entity_type}/{uuid}` | Get all risk dimensions for one entity |
| `GET` | `/api/v1/intelligence/risk/{entity_type}` | List entities sorted by risk score (dimension filter) |
| `GET` | `/api/v1/intelligence/risk/summary` | Aggregate risk overview (total critical, high, medium, low per dimension) |
| `POST` | `/api/v1/intelligence/risk/score-all` | Trigger full recalculation of all risk scores |
| `GET` | `/api/v1/intelligence/risk/factors` | List active risk factors (for UI configuration) |
| `PUT` | `/api/v1/intelligence/risk/factors/{name}` | Update risk factor weight/config |

**Note:** These endpoints are on the Energy Service. They must be proxied through the modular-api (same pattern as the current energy proxy router), so the frontend calls `http://localhost:8000/api/v1/intelligence/risk/*`.

**Modular API change** (in `backend/api/energy/router.py`):
- The existing catch-all proxy `/{path:path}` already handles any path under `/api/v1/energy/`. A second proxy router with prefix `/api/v1/intelligence` is needed for the new endpoints.

### 2.6 Frontend Changes

**New page:**
- `/intelligence/risk` — Risk Dashboard with:
  - Heatmap grid (entity types × risk dimensions)
  - Entity type filter, dimension filter
  - Sortable table of highest-risk entities
  - Trend indicators (improving/stable/worsening)

**New component:**
- `RiskBadge` — Color-coded severity badge (used in existing EnergyAssetDetail, EnergyImpactCard, EnergyMap popups)

**Modified pages:**
- `EnergyAssetDetail.tsx` — Add "Risk Scores" section showing all 5 dimensions
- `EnergyMap.tsx` — Add risk overlay mode (color assets by risk score instead of type)
- `EnergyImpactCard.tsx` — Read from risk_scores API for severity instead of current rule-based count
- `EnergyAnalytics.tsx` — Add "Risk Overview" panel showing high-risk counts

### 2.7 Future ML Models (Phase 3+)

| Model | Input Features | Prediction Target |
|---|---|---|
| **Corridor Risk Predictor** | Historical events, shipping_route.risk_score, insurance_multiplier, transit_time_days, origin/destination country risk | Probability of disruption within N days |
| **Supplier Reliability Model** | Supplier market_share_pct, organization type, country risk, historical sanctions events, contract fulfillment rate | Supplier reliability score (0-1) |
| **Country Instability Model** | Article sentiment trend, event frequency, sanctions severity, conflict proximity | Country risk score next quarter |
| **Maritime Risk Forecaster** | Piracy event frequency, insurance_multiplier trend, weather data, naval presence | Route risk score for next voyage |
| **Infrastructure Vulnerability Model** | Physical security score, cyber event frequency, age, location risk, historical incidents | Infrastructure breach probability |

---

## 3. Capability 2: Energy Supply Chain Knowledge Graph

### 3.1 Description

A directed, typed knowledge graph representing the end-to-end energy supply chain:

```
Supplier → Import Corridor → Port → Pipeline → Refinery → SPR / Storage → End Consumer
                ↓                                              ↓
           Chokepoint                                    Distribution
```

The graph supports:
- **Risk propagation** — a risk at any node propagates to downstream/dependent nodes with configurable decay
- **Path finding** — find all viable supply routes from a supplier to a refinery
- **Dependency analysis** — which refineries depend on a specific chokepoint?

### 3.2 How It Fits Into the Existing Architecture

- **Supply chain module** lives in `services/energy-service/services/supply_chain.py` and `services/energy-service/routers/supply_chain.py`
- **Extends** the existing `energy.entity_relationships` table with a specific `supply_chain` relationship type and adds a dedicated `energy.supply_chain_edges` table for weighted, directed edges
- **Consumes** existing entity data — the 14 entity types are linked via their natural relationships (import_corridors connect locations, shipping_routes connect ports, pipelines connect to refineries, etc.)
- **Creates** the supply chain graph automatically from existing data (not manually curated)
- **Risk propagation** reads from `energy.risk_scores` (Capability 1) and propagates through the graph

### 3.3 Required Database Schema Changes

```sql
-- Schema: energy

-- New table: directed supply chain edges with weights
CREATE TABLE energy.supply_chain_edges (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    source_type     energy.asset_type NOT NULL,
    source_id       BIGINT NOT NULL,                    -- FK to entity table's id
    target_type     energy.asset_type NOT NULL,
    target_id       BIGINT NOT NULL,                    -- FK to entity table's id
    edge_type       VARCHAR(50) NOT NULL,                -- 'supplies', 'transports', 'processes', 'stores', 'receives', 'feeds', 'exports', 'imports'
    weight          DOUBLE PRECISION DEFAULT 1.0,        -- throughput fraction / importance
    max_capacity    DOUBLE PRECISION,                    -- max throughput (barrels/day, tons/year, etc.)
    current_utilization DOUBLE PRECISION,                -- current throughput / max_capacity
    risk_multiplier DOUBLE PRECISION DEFAULT 1.0,        -- risk propagation factor (0 = blocks, 1 = passes through fully)
    is_active       BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_by      TEXT DEFAULT 'system',
    updated_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_type, source_id, target_type, target_id, edge_type)
);

-- Indexes
CREATE INDEX idx_supply_chain_source ON energy.supply_chain_edges (source_type, source_id);
CREATE INDEX idx_supply_chain_target ON energy.supply_chain_edges (target_type, target_id);
CREATE INDEX idx_supply_chain_active ON energy.supply_chain_edges (is_active) WHERE is_active = TRUE;

-- New table: risk propagation results (cached)
CREATE TABLE energy.risk_propagation (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    root_type       energy.asset_type NOT NULL,          -- the source of the risk
    root_id         BIGINT NOT NULL,                     -- the entity that has the risk
    affected_type   energy.asset_type NOT NULL,           -- the affected entity type
    affected_id     BIGINT NOT NULL,                      -- the affected entity
    propagated_risk DOUBLE PRECISION NOT NULL,             -- propagated risk score (0-1)
    path_length     INTEGER NOT NULL,                     -- number of hops
    propagation_path JSONB DEFAULT '[]'::jsonb,           -- the chain of edges
    calculated_at   TIMESTAMPTZ DEFAULT NOW(),
    valid_until     TIMESTAMPTZ,
    UNIQUE (root_type, root_id, affected_type, affected_id, valid_until)
);

CREATE INDEX idx_risk_propagation_affected ON energy.risk_propagation (affected_type, affected_id);
CREATE INDEX idx_risk_propagation_root ON energy.risk_propagation (root_type, root_id);
```

**Automatic edge generation logic:**
The supply chain graph is built by traversing existing relationships:

| Source | Relationship | Target | Generated via |
|---|---|---|---|
| Supplier | `supplies` | Import Corridor | supplier.organization_id + import_corridor.origin_location_id |
| Import Corridor | `connects_to` | Port | import_corridor.destination_location_id = port.location_id |
| Port | `feeds_into` | Pipeline | port → pipeline via relationship |
| Pipeline | `feeds_into` | Refinery | pipeline → refinery via relationship |
| Refinery | `feeds_into` | Storage/SPR | refinery → storage via relationship |
| Storage/SPR | `stores` | Distribution | storage → location via relationship |

Additional edges require manual curation via the API or seed data updates until ML-based edge inference is built (Phase 3+).

### 3.4 Kafka Event Changes

No new Kafka topics. The supply chain graph is:
- Built on-demand (`POST /api/v1/intelligence/supply-chain/build`)
- Automatically rebuilt when entity relationships change (via the relationship POST handler)

### 3.5 API Changes

**New endpoints** (Energy Service, port 8006):

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/intelligence/supply-chain/graph` | Full supply chain graph (paginated) |
| `GET` | `/api/v1/intelligence/supply-chain/from/{type}/{uuid}` | All downstream paths from an entity |
| `GET` | `/api/v1/intelligence/supply-chain/to/{type}/{uuid}` | All upstream paths to an entity |
| `GET` | `/api/v1/intelligence/supply-chain/path` | Find path between two entities (query params: from_type, from_id, to_type, to_id) |
| `GET` | `/api/v1/intelligence/supply-chain/dependencies/{type}/{uuid}` | All entities dependent on this entity |
| `GET` | `/api/v1/intelligence/supply-chain/critical-path` | Highest-risk path analysis |
| `POST` | `/api/v1/intelligence/supply-chain/propagate` | Trigger risk propagation calculation |
| `GET` | `/api/v1/intelligence/supply-chain/propagation/{type}/{uuid}` | Get propagation results for an entity |
| `POST` | `/api/v1/intelligence/supply-chain/edges` | Create a manual supply chain edge |
| `PATCH` | `/api/v1/intelligence/supply-chain/edges/{uuid}` | Update edge capacity/utilization |

### 3.6 Frontend Changes

**New page:**
- `/intelligence/supply-chain` — Supply Chain Graph Explorer with:
  - Interactive directed graph (D3.js or vis.js) showing entity nodes and weighted edges
  - Risk heat overlay (color nodes/edges by risk score)
  - Path highlighting when clicking source/destination
  - Dependency impact view (highlight all entities affected by a node risk)

**Modified pages:**
- `GraphExplorer.tsx` — Add toggle between "Intelligence Graph" (article-based) and "Supply Chain Graph" (energy infrastructure)
- `EnergyAssetDetail.tsx` — Add "Supply Chain Position" section showing upstream suppliers and downstream consumers
- `EnergyMap.tsx` — Add supply chain overlay mode (draw edges as bezier curves between asset locations)

### 3.7 Future ML Models (Phase 3+)

| Model | Input Features | Prediction Target |
|---|---|---|
| **Edge Weight Predictor** | Entity attributes, historical throughput, relationship patterns | Edge weight (throughput fraction) |
| **Missing Edge Detector** | Entity attributes, spatial proximity, known graph patterns | Probability of missing supply chain edge |
| **Criticality Score Model** | Graph centrality, risk propagation, dependency count | Entity criticality to supply chain resilience |
| **Bottleneck Predictor** | Utilization trends, capacity, upstream/downstream constraints | Probability of becoming a bottleneck in N days |

---

## 4. Capability 3: Infrastructure Event Intelligence

### 4.1 Description

An event detection and intelligence system that:
1. Detects infrastructure-related events (shutdowns, cyber attacks, natural disasters, sanctions, conflicts) from article NER entities
2. Links detected events to specific energy assets in the `energy.` schema
3. Maintains event timelines per asset with severity progression
4. Generates alerts when critical events are detected for watched entities

### 4.2 How It Fits Into the Existing Architecture

- **Event intelligence module** extends the existing `services/database-service/services/event_intelligence.py` pipeline
- **Currently**: `update_event_intelligence()` clusters articles into events using `events`, `event_articles`, `event_entities`, `entity_profiles`, and `alerts` tables (public schema)
- **Phase 2 change**: Add `enrich_infrastructure_events()` step that checks each clustered event against energy entities and creates `energy.infrastructure_events` records
- **The existing `energy.infrastructure_events` table** is used directly (it already has the correct schema)
- **Event linking** uses the existing `energy_entity_mappings` table to match article entities to energy assets
- **Event timeline** leverages the existing `energy.infrastructure_events` table with `occurred_at` and `resolved_at` timestamps

### 4.3 Required Database Schema Changes

**Minimal changes needed** — the existing `energy.infrastructure_events` table is designed for this purpose.

```sql
-- New table: link infrastructure events to articles
CREATE TABLE energy.event_article_links (
    id                  BIGSERIAL PRIMARY KEY,
    uuid                UUID UNIQUE DEFAULT gen_random_uuid(),
    infrastructure_event_id BIGINT NOT NULL REFERENCES energy.infrastructure_events(id) ON DELETE CASCADE,
    article_id          INTEGER NOT NULL REFERENCES public.processed_articles(id) ON DELETE CASCADE,
    match_confidence    DOUBLE PRECISION DEFAULT 0.5,
    matched_by          VARCHAR(20) DEFAULT 'entity_link',  -- 'entity_link', 'keyword', 'semantic'
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (infrastructure_event_id, article_id)
);

CREATE INDEX idx_event_article_links_event ON energy.event_article_links (infrastructure_event_id);
CREATE INDEX idx_event_article_links_article ON energy.event_article_links (article_id);

-- Extend existing infrastructure_events with article-derived fields
ALTER TABLE energy.infrastructure_events
    ADD COLUMN IF NOT EXISTS article_derived BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_event_id INTEGER REFERENCES public.events(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS article_count INTEGER DEFAULT 0;
```

**Provenance tracking for auto-detected events:**
- When an infrastructure event is auto-detected from articles, `article_derived = TRUE` and `source_event_id` references the originating cluster event in the `public.events` table.
- Manual events (created via API/UI) remain `article_derived = FALSE`.

### 4.4 Kafka Event Changes

**New consumer** in the Database Service or a dedicated `energy-intelligence-worker`:

| Topic | Publisher | Consumer | Purpose |
|---|---|---|---|
| `processed_articles` | ml-service | db-service (existing) + energy-intelligence-worker (NEW) | Detect infrastructure events from article entities |

**Option A (recommended for Phase 2):** Add the infrastructure event detection as a synchronous step in the existing `handle_message()` chain in `consumer.py` (alongside `enrich_energy_context`). This avoids adding a new consumer.

**Option B:** Create a new `energy-intelligence-worker` service that subscribes to `processed_articles` independently. Use this if event detection becomes computationally expensive.

### 4.5 API Changes

**New endpoints** (Energy Service, port 8006):

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/intelligence/events` | List infrastructure events (filterable by severity, entity_type, date range) |
| `GET` | `/api/v1/intelligence/events/timeline/{type}/{uuid}` | Full event timeline for one asset |
| `GET` | `/api/v1/intelligence/events/recent` | Recent high-severity events (dashboard widget data) |
| `GET` | `/api/v1/intelligence/events/summary` | Event count aggregation (by type, by severity) |
| `POST` | `/api/v1/intelligence/events/detect` | Trigger article-based event detection for unprocessed articles |

**Existing endpoints** that remain:
- `GET /api/v1/energy/{table}/{uuid}/events` — kept as lightweight per-entity view
- `POST /api/v1/energy/events` — kept for manual event creation

### 4.6 Frontend Changes

**New page:**
- `/intelligence/events` — Infrastructure Events Dashboard with:
  - Timeline view (Gantt-like chart of events by asset)
  - Severity filter (critical/high/medium/low)
  - Asset type filter
  - Event cards with severity badge, date, description, linked articles
  - Click-to-detail for each event

**New component:**
- `EventTimeline` — Horizontal timeline showing events for one or more assets with severity color coding

**Modified pages:**
- `EnergyAssetDetail.tsx` — Replace the simple events panel with the full `EventTimeline` component
- `EnergyAnalytics.tsx` — Add "Recent Critical Events" section
- `ArticleDetail.tsx` — The existing `EnergyContextSection` already shows `infrastructure_events`; enhance with links to `/intelligence/events/{id}`
- `Copilot.tsx` — The existing `EnergyImpactCard` already shows `infrastructure_event_count`; enhance with drill-down links

### 4.7 Future ML Models (Phase 3+)

| Model | Input Features | Prediction Target |
|---|---|---|
| **Event Type Classifier** | Article content, NER entities, sentiment, source | Infrastructure event type (shutdown, cyber_attack, etc.) |
| **Event Severity Predictor** | Article content, entity criticality, historical events, source credibility | Event severity (low/medium/high/critical) |
| **Event Propagation Model** | Event type, affected entity, supply chain position, historical propagation | Expected downstream events within N days |
| **False Positive Reducer** | Article metadata, entity match confidence, historical precision | Probability that detected event is real |

---

## 5. Capability 4: Supply Chain Digital Twin

### 5.1 Description

A dynamic, queryable digital twin of India's energy import network that:

1. **Represents the current state** of the supply chain (active suppliers, routes, ports, pipelines, refineries, SPR levels)
2. **Supports "what-if" simulations** — e.g., "What if the Strait of Hormuz is blocked for 30 days? Which refineries run out of crude first?"
3. **Runs on a tick-based simulation engine** — time can be advanced by hours, days, or weeks
4. **Outputs impact metrics** — supply gap (barrels/day), refinery downtime days, SPR depletion rate, economic impact

### 5.2 How It Fits Into the Existing Architecture

- **Digital twin module** lives in `services/energy-service/services/digital_twin/` with its own sub-modules:
  - `engine.py` — Tick-based simulation engine
  - `models.py` — Simulation state models
  - `scenarios.py` — Pre-built scenario definitions
  - `routers/digital_twin.py` — API endpoints
- **Consumes** the supply chain graph (Capability 2), risk scores (Capability 1), and entity data
- **Is a simulation layer** — it does NOT modify real entity data. All simulation state is stored in `energy.simulation_scenarios` and `energy.simulation_runs`
- **Each simulation run** creates a snapshot of entity state at that point in time, then applies scenario events and advances the clock

### 5.3 Required Database Schema Changes

```sql
-- Schema: energy

-- New table: pre-built simulation scenarios
CREATE TABLE energy.simulation_scenarios (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    category        VARCHAR(50) NOT NULL DEFAULT 'custom',  -- 'chokepoint', 'sanctions', 'natural_disaster', 'conflict', 'cyber', 'custom'
    config          JSONB NOT NULL DEFAULT '{}'::jsonb,    -- scenario parameters
    is_template     BOOLEAN DEFAULT FALSE,                  -- reusable template
    created_by      TEXT DEFAULT 'system',
    updated_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- New table: simulation run results
CREATE TABLE energy.simulation_runs (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    scenario_id     BIGINT REFERENCES energy.simulation_scenarios(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending',          -- 'pending', 'running', 'completed', 'failed'
    tick_interval   VARCHAR(20) DEFAULT 'day',              -- 'hour', 'day', 'week'
    max_ticks       INTEGER DEFAULT 90,                     -- simulate N ticks
    current_tick    INTEGER DEFAULT 0,
    config          JSONB DEFAULT '{}'::jsonb,              -- simulation parameters
    summary         JSONB DEFAULT '{}'::jsonb,              -- aggregate results after completion
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      TEXT DEFAULT 'system',
    updated_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- New table: per-tick simulation events
CREATE TABLE energy.simulation_tick_events (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    run_id          BIGINT NOT NULL REFERENCES energy.simulation_runs(id) ON DELETE CASCADE,
    tick            INTEGER NOT NULL,
    event_type      VARCHAR(50) NOT NULL,                   -- 'supply_disruption', 'price_shock', 'sanctions', etc.
    entity_type     energy.asset_type,
    entity_id       BIGINT,                                  -- affected entity
    description     TEXT,
    impact          JSONB DEFAULT '{}'::jsonb,              -- {supply_gap_bpd, price_impact_pct, etc.}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sim_tick_events_run ON energy.simulation_tick_events (run_id, tick);
CREATE INDEX idx_sim_tick_events_entity ON energy.simulation_tick_events (entity_type, entity_id);

-- New table: per-tick entity state snapshots
CREATE TABLE energy.simulation_entity_state (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    run_id          BIGINT NOT NULL REFERENCES energy.simulation_runs(id) ON DELETE CASCADE,
    tick            INTEGER NOT NULL,
    entity_type     energy.asset_type NOT NULL,
    entity_id       BIGINT NOT NULL,
    state           JSONB NOT NULL DEFAULT '{}'::jsonb,     -- {current_inventory, throughput, risk_score, etc.}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sim_entity_state_run ON energy.simulation_entity_state (run_id, tick);
CREATE INDEX idx_sim_entity_state_entity ON energy.simulation_entity_state (entity_type, entity_id);
```

### 5.4 Kafka Event Changes

**No new Kafka topics.** The digital twin is an on-demand simulation tool, not a streaming pipeline.

**Future consideration:** If real-time simulation updates are needed (e.g., live risk adjustment), introduce an `energy.simulation_events` Kafka topic for real-time event injection.

### 5.5 API Changes

**New endpoints** (Energy Service, port 8006):

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/intelligence/digital-twin/scenarios` | List available simulation templates |
| `POST` | `/api/v1/intelligence/digital-twin/scenarios` | Create a new scenario |
| `GET` | `/api/v1/intelligence/digital-twin/scenarios/{uuid}` | Get scenario detail |
| `POST` | `/api/v1/intelligence/digital-twin/run` | Start a new simulation run |
| `GET` | `/api/v1/intelligence/digital-twin/runs` | List previous simulation runs |
| `GET` | `/api/v1/intelligence/digital-twin/runs/{uuid}` | Get run results (tick events + state) |
| `GET` | `/api/v1/intelligence/digital-twin/runs/{uuid}/tick/{n}` | Get state at specific tick |
| `DELETE` | `/api/v1/intelligence/digital-twin/runs/{uuid}` | Delete a simulation run |

**Pre-built scenario templates** (seeded):

| Scenario Name | Description | Parameters |
|---|---|---|
| `strait_of_hormuz_blockade` | Full blockade of Strait of Hormuz for N days | duration_days, severity |
| `russia_sanctions_escalation` | Escalation of sanctions on Russian energy exports | tariff_pct, export_ban_countries[] |
| `south_china_sea_tensions` | Military conflict disrupting South China Sea routes | duration_days, affected_ports[] |
| `cyclone_gujarat_coast` | Natural disaster damaging Gujarat refineries | cyclone_category, refineries_offline[] |
| `suez_canal_disruption` | Blockage of the Suez Canal | duration_days |
| `custom` | User-defined combination of events | events[] |

### 5.6 Frontend Changes

**New page:**
- `/intelligence/digital-twin` — Digital Twin Dashboard with:
  - Scenario selector (pre-built templates or custom)
  - Parameter configuration form (duration, severity, entities affected)
  - "Run Simulation" button
  - Results view: supply gap chart (barrels/day over time), refinery status timeline, SPR depletion curve, impact summary metrics
  - Comparison mode (run multiple scenarios side by side)

**New components:**
- `SimulationConfigurator` — Form to configure scenario parameters
- `SimulationResultsChart` — Recharts-based line/area chart for simulation outputs
- `SimulationComparisonTable` — Side-by-side scenario comparison

### 5.7 Future ML Models (Phase 3+)

| Model | Input Features | Prediction Target |
|---|---|---|
| **Disruption Impact Estimator** | Historical simulation runs, entity attributes, disruption type/duration | Expected supply gap (barrels/day) for given scenario |
| **Recovery Time Predictor** | Entity type, disruption severity, alternative capacity, historical recovery | Days to full recovery after disruption |
| **Optimal Mitigation Searcher** | Simulation engine as environment, RL agent | Optimal SPR drawdown schedule during disruption |
| **Scenario Likelihood Model** | Geopolitical events, news sentiment, risk scores | Probability of each scenario occurring in next N days |

---

## 6. Capability 5: Procurement Recommendation Engine

### 6.1 Description

A recommendation system that helps procurement officers make optimal sourcing decisions by:

1. **Finding alternative suppliers** for a given crude grade or commodity
2. **Ranking shipping routes** by cost, risk, and transit time
3. **Checking refinery compatibility** — which refineries can process which crude grades
4. **Trade-off analysis** — cost vs. risk vs. transit time trade-off visualization

### 6.2 How It Fits Into the Existing Architecture

- **Recommendation module** lives in `services/energy-service/services/procurement.py` and `services/energy-service/routers/procurement.py`
- **Consumes**: suppliers, commodities, shipping_routes, refineries, ports, risk_scores, supply_chain_edges
- **Uses**: The supply chain graph (Capability 2) for path finding, risk scores (Capability 1) for risk weighting
- **Is rule-based** in Phase 2 — ranking uses configurable weight formulas. ML replaces weights in Phase 3+.

### 6.3 Required Database Schema Changes

```sql
-- Schema: energy

-- New table: refinery-crude compatibility matrix
CREATE TABLE energy.refinery_crude_compatibility (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    refinery_id     BIGINT NOT NULL REFERENCES energy.refineries(id) ON DELETE CASCADE,
    commodity_id    BIGINT NOT NULL REFERENCES energy.commodities(id) ON DELETE CASCADE,
    compatibility   DOUBLE PRECISION NOT NULL,              -- 0.0 (incompatible) to 1.0 (ideal)
    max_blend_pct   DOUBLE PRECISION,                       -- max % in blend
    notes           TEXT,
    created_by      TEXT DEFAULT 'system',
    updated_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (refinery_id, commodity_id)
);

-- New table: procurement recommendations (cached results)
CREATE TABLE energy.procurement_recommendations (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    query_id        TEXT,                                   -- client-generated idempotency key
    commodity_id    BIGINT REFERENCES energy.commodities(id),
    destination_refinery_id BIGINT REFERENCES energy.refineries(id),
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,     -- [{supplier, route, cost_bbl, risk_score, transit_days, score}]
    parameters      JSONB DEFAULT '{}'::jsonb,              -- query parameters (weight_cost, weight_risk, etc.)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_procurement_recs_query ON energy.procurement_recommendations (query_id);
```

### 6.4 Kafka Event Changes

No new Kafka topics. Recommendations are computed on-demand and optionally cached.

### 6.5 API Changes

**New endpoints** (Energy Service, port 8006):

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/intelligence/procurement/alternatives/{supplier_uuid}` | Find alternative suppliers for a given supplier's commodity |
| `GET` | `/api/v1/intelligence/procurement/routes` | Rank shipping routes (query params: origin_port, destination_port, commodity) |
| `GET` | `/api/v1/intelligence/procurement/compatibility/{refinery_uuid}` | Crude grades compatible with a refinery |
| `GET` | `/api/v1/intelligence/procurement/compatibility/by-crude/{commodity_uuid}` | Refineries compatible with a crude grade |
| `POST` | `/api/v1/intelligence/procurement/recommend` | Full recommendation request (commodity, destination, weights) |
| `GET` | `/api/v1/intelligence/procurement/tradeoff` | Cost vs risk vs transit time trade-off data for visualization |

**Recommendation input schema:**

```json
{
    "commodity_slug": "brent_crude",
    "destination_region": "India",
    "destination_refinery": "jamnagar",
    "weights": {
        "cost": 0.4,
        "risk": 0.3,
        "transit_time": 0.2,
        "reliability": 0.1
    },
    "filters": {
        "max_risk_score": 0.7,
        "max_transit_days": 45,
        "exclude_countries": ["CountryA", "CountryB"]
    }
}
```

**Recommendation output schema:**

```json
{
    "recommendations": [
        {
            "rank": 1,
            "overall_score": 0.87,
            "supplier": {"name": "Saudi Aramco", "uuid": "...", "country": "Saudi Arabia"},
            "route": {
                "description": "Ras Tanura → Strait of Hormuz → Arabian Sea → Gulf of Khambhat → Jamnagar",
                "distance_nm": 2450,
                "transit_days": 14,
                "chokepoints": ["Strait of Hormuz"]
            },
            "cost_per_bbl": 72.50,
            "risk_score": 0.35,
            "reliability": 0.92,
            "refinery_compatibility": 0.95,
            "breakdown": {"cost_score": 0.88, "risk_score": 0.75, "transit_score": 0.80, "reliability_score": 0.95}
        }
    ],
    "parameters_used": {"weights": {...}, "filters": {...}}
}
```

### 6.6 Frontend Changes

**New page:**
- `/intelligence/procurement` — Procurement Recommendation Center with:
  - Search/select commodity, destination, refinery
  - Weight sliders (cost, risk, transit time, reliability)
  - Filter panel (max risk, max transit, exclude countries)
  - Results table sorted by overall score with detailed breakdown
  - Trade-off scatter plot (cost vs risk, bubble = transit time)
  - Route visualization on the Energy Map overlay

**New components:**
- `WeightSlider` — Interactive weight configuration with drag-to-adjust
- `RecommendationCard` — Single recommendation result with score breakdown
- `TradeOffChart` — Scatter chart for cost/risk/time trade-off visualization

### 6.7 Future ML Models (Phase 3+)

| Model | Input Features | Prediction Target |
|---|---|---|
| **Cost Predictor** | Historical pricing, route distance, insurance multiplier, sanctions impact | Expected cost per barrel for a route-supplier combination |
| **Reliability Score Model** | Supplier historical delivery %, country stability, route disruption frequency | Supplier reliability score (0-1) |
| **Crude Compatibility Model** | Crude API gravity, sulfur content, refinery nelson_complexity_index, crude_types_accepted | Refinery compatibility score |
| **Recommendation Ranker** | All recommendation attributes, historical user choices | Optimal ranking of alternatives |

---

## 7. Capability 6: Strategic Petroleum Reserve Optimizer

### 7.1 Description

An optimization engine for India's Strategic Petroleum Reserves that:

1. **Drawdown logic** — given a disruption scenario, calculate optimal SPR drawdown schedule to maximize days of import cover
2. **Replenishment planning** — given market conditions, calculate optimal replenishment schedule considering budget constraints and price forecasts
3. **Supply gap estimation** — given a disruption, calculate how long existing SPRs can cover the gap, considering refinery-specific consumption rates

### 7.2 How It Fits Into the Existing Architecture

- **SPR optimizer module** lives in `services/energy-service/services/spr_optimizer.py` and `services/energy-service/routers/spr_optimizer.py`
- **Consumes**: `energy.strategic_petroleum_reserves` (capacity, current_inventory, drawdown/replenishment rates), `energy.supply_chain_edges` (refinery consumption), `energy.risk_scores`, and the digital twin simulation results
- **Integrates with**: Digital Twin (Capability 4) — SPR optimizer runs as a post-processing step on simulation results
- **Is formula-based** in Phase 2 (Inventory / DailyDraw = DaysRemaining). Linear programming optimization is Phase 3+.

### 7.3 Required Database Schema Changes

```sql
-- Schema: energy

-- New table: SPR optimization runs
CREATE TABLE energy.spr_optimization_runs (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    scenario_id     BIGINT REFERENCES energy.simulation_runs(id) ON DELETE SET NULL,  -- linked digital twin run
    status          VARCHAR(20) DEFAULT 'pending',   -- 'pending', 'completed', 'failed'
    config          JSONB DEFAULT '{}'::jsonb,       -- optimization parameters

    -- Input: disruption scenario
    disruption_type        VARCHAR(50),               -- 'chokepoint', 'sanctions', etc.
    disruption_duration_days INTEGER,
    affected_import_bpd    DOUBLE PRECISION,          -- barrels/day of import affected

    -- Input: SPR state snapshot
    total_spr_capacity     DOUBLE PRECISION,
    total_current_inventory DOUBLE PRECISION,
    total_max_drawdown_bpd DOUBLE PRECISION,
    total_replenishment_bpd DOUBLE PRECISION,

    -- Output: drawdown plan
    recommended_daily_draw DOUBLE PRECISION,          -- optimal drawdown rate (bpd)
    days_of_cover          INTEGER,                   -- how many days SPR can cover
    depletion_date         DATE,
    critical_date          DATE,                      -- date when first refinery idles

    -- Output: replenishment plan
    replenishment_volume   DOUBLE PRECISION,          -- barrels to purchase
    replenishment_days     INTEGER,                   -- days to replenish at max rate
    estimated_cost         DOUBLE PRECISION,          -- estimated procurement cost

    -- Output: gap analysis
    supply_gap_bpd         DOUBLE PRECISION,          -- uncovered gap after SPR
    refinery_impact        JSONB DEFAULT '[]'::jsonb, -- [{refinery, days_until_idle, gap_bpd}]
    economic_impact_bpd    DOUBLE PRECISION,          -- estimated $/day economic impact

    created_by      TEXT DEFAULT 'system',
    updated_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_spr_opt_runs_scenario ON energy.spr_optimization_runs (scenario_id);
```

**Modifications to existing table `energy.strategic_petroleum_reserves`:**
- Ensure `current_inventory_barrels`, `max_drawdown_rate_bpd`, and `replenishment_rate_bpd` have realistic seed values
- Add `last_inventory_update TIMESTAMPTZ` for tracking data freshness

### 7.4 Kafka Event Changes

**No new Kafka topics.** The SPR optimizer is invoked on-demand or as a post-step to digital twin simulations.

### 7.5 API Changes

**New endpoints** (Energy Service, port 8006):

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/intelligence/spr/optimize` | Run SPR optimization for a given disruption scenario |
| `GET` | `/api/v1/intelligence/spr/runs` | List previous optimization runs |
| `GET` | `/api/v1/intelligence/spr/runs/{uuid}` | Get optimization run details |
| `GET` | `/api/v1/intelligence/spr/status` | Current SPR status overview (total inventory, days of cover) |
| `GET` | `/api/v1/intelligence/spr/gap-analysis` | Supply gap analysis based on current risks |

**Optimization input schema:**

```json
{
    "scenario_name": "Hormuz Blockade - 30 Day",
    "disruption_type": "chokepoint",
    "disruption_duration_days": 30,
    "affected_import_bpd": 3500000,
    "spr_ids": ["uuid1", "uuid2"],           -- which SPRs to include (omit = all)
    "strategic_reserve_days": 90              -- minimum days of cover to maintain
}
```

**Optimization output schema:**

```json
{
    "run_id": "...",
    "status": "completed",
    "summary": {
        "total_spr_inventory_barrels": 38500000,
        "total_import_bpd": 4500000,
        "affected_import_bpd": 3500000,
        "days_of_cover_without_spr": 0,
        "days_of_cover_with_optimal_draw": 38,
        "optimal_daily_draw_bpd": 850000,
        "critical_date": "2026-08-12",
        "depletion_date": "2026-09-15"
    },
    "drawdown_schedule": [
        {"day": 1, "draw_bpd": 850000, "inventory_remaining": 37650000},
        {"day": 7, "draw_bpd": 850000, "inventory_remaining": 32000000}
    ],
    "refinery_impact": [
        {"refinery": "Jamnagar", "capacity_bpd": 1240000, "gap_bpd": 350000, "days_until_idle": 0},
        {"refinery": "Mangalore", "capacity_bpd": 300000, "gap_bpd": 200000, "days_until_idle": 7}
    ],
    "replenishment_plan": {
        "volume_barrels": 38500000,
        "estimated_days": 45,
        "estimated_cost_usd": 2772000000
    }
}
```

### 7.6 Frontend Changes

**New page:**
- `/intelligence/spr` — SPR Optimizer Dashboard with:
  - Current SPR status overview (total inventory, days of cover, fill level %)
  - Per-SPR breakdown cards with inventory bar, drawdown rate, replenishment rate
  - "Run Optimization" button → scenario selection modal
  - Results view: drawdown schedule chart, refinery impact table, depletion timeline
  - Replenishment plan with estimated cost

**New components:**
- `SPRStatusCard` — Single SPR status with inventory gauge
- `DrawdownChart` — Line chart showing inventory over time during drawdown
- `RefineryImpactTable` — Table showing refineries most affected by disruption

**Modified pages:**
- `EnergyAssetDetail.tsx` — When viewing a Strategic Petroleum Reserve, show optimizer link and current optimization results
- `EnergyAnalytics.tsx` — Add "SPR Status" panel with fill levels and days of cover

### 7.7 Future ML Models (Phase 3+)

| Model | Input Features | Prediction Target |
|---|---|---|
| **Optimal Drawdown Scheduler** | Historical drawdown events, refinery demand curves, disruption type, SPR location | Optimal daily draw rate per SPR |
| **Replenishment Price Forecaster** | Global crude price trends, sanctions status, supplier reliability | Optimal time to purchase for replenishment |
| **Gap Duration Predictor** | Disruption type, affected infrastructure, historical recovery times, diplomatic status | Expected duration of supply gap |
| **Economic Impact Model** | Supply gap size, duration, refinery utilization, global crude price | Economic impact ($/day) of disruption |

---

## 8. Implementation Phasing

### Phase 2A: Foundation (Weeks 1-2)

Build the supporting infrastructure for all six capabilities.

| Task | Details | Files/Modules |
|---|---|---|
| 1 | Create `risk_factors` table and seed initial factors | `infra/sql/energy_intelligence_schema.sql`, Alembic migration `0006_energy_intelligence` |
| 2 | Create `risk_scores` table with indexes | Same migration |
| 3 | Seed risk factor definitions (10-15 factors) | `services/energy-service/seed_data/risk_factors.json` |
| 4 | Build risk engine (`risk_engine.py`) | `services/energy-service/services/risk_engine.py` |
| 5 | Build risk router (`routers/risk.py`) | `services/energy-service/routers/risk.py` |
| 6 | Add `/api/v1/intelligence` proxy to modular-api | `backend/api/energy/router.py` (extend with second prefix) |
| 7 | Create `supply_chain_edges` and `risk_propagation` tables | Alembic migration `0006` |
| 8 | Build supply chain auto-builder from existing relationships | `services/energy-service/services/supply_chain.py` |
| 9 | Create `event_article_links` table | Same migration |
| 10 | Add infrastructure event detection to `enrich_energy_context()` | `services/database-service/services/energy_enrichment.py` |
| 11 | Create `simulation_scenarios` and `simulation_runs` tables | Same migration |
| 12 | Create `procurement_recommendations` and `refinery_crude_compatibility` tables | Same migration |
| 13 | Create `spr_optimization_runs` table | Same migration |

### Phase 2B: Risk & Graph (Weeks 3-4)

| Task | Details |
|---|---|
| 1 | Implement corridor risk scoring (distance, chokepoints, historical events) |
| 2 | Implement country risk scoring (article sentiment, event frequency, sanctions) |
| 3 | Implement supplier risk scoring (country risk, market share, organization type) |
| 4 | Implement maritime route risk scoring (historical events, insurance multiplier, chokepoints) |
| 5 | Implement infrastructure risk scoring (events, location risk, criticality) |
| 6 | Implement supply chain graph auto-build from entity_relationships |
| 7 | Implement risk propagation engine (BFS/DFS through supply chain edges) |
| 8 | Build risk API endpoints |
| 9 | Build supply chain API endpoints |
| 10 | Frontend: Risk Dashboard page |
| 11 | Frontend: Supply Chain Graph Explorer |
| 12 | Frontend: Risk overlay on Energy Map |

### Phase 2C: Events & Digital Twin (Weeks 5-6)

| Task | Details |
|---|---|
| 1 | Implement article-to-infrastructure-event detection in database-service |
| 2 | Implement event linking to energy assets via existing entity mappings |
| 3 | Build event intelligence API endpoints |
| 4 | Implement tick-based simulation engine |
| 5 | Build 5 pre-built scenario templates (Hormuz, Suez, sanctions, cyclone, South China Sea) |
| 6 | Implement what-if simulation execution |
| 7 | Build digital twin API endpoints |
| 8 | Frontend: Infrastructure Events Dashboard |
| 9 | Frontend: Digital Twin Dashboard |
| 10 | Frontend: Event timeline component |

### Phase 2D: Procurement & SPR (Weeks 7-8)

| Task | Details |
|---|---|
| 1 | Implement alternative supplier finding (same commodity, different country) |
| 2 | Implement route ranking (distance × risk × cost formula) |
| 3 | Implement refinery compatibility checking (crude_types_accepted × commodity attributes) |
| 4 | Implement trade-off analysis (cost/risk/time Pareto frontier) |
| 5 | Implement SPR drawdown calculator (Inventory / DailyDraw for each disruption day) |
| 6 | Implement replenishment planner (volume needed at max replenishment rate) |
| 7 | Implement supply gap estimator (import affected - SPR drawdown capacity) |
| 8 | Build procurement API endpoints |
| 9 | Build SPR optimizer API endpoints |
| 10 | Frontend: Procurement Recommendation Center |
| 11 | Frontend: SPR Optimizer Dashboard |
| 12 | Frontend: Integrate SPR link into EnergyAssetDetail |

---

## 9. Cross-Cutting Concerns

### 9.1 Modular API Proxy Extension

The existing `backend/api/energy/router.py` only proxies `/api/v1/energy/*`. The new `/api/v1/intelligence/*` prefix must be added to the same proxy pattern.

**Recommended approach:** Convert the single-prefix proxy to a generic proxy function that accepts any prefix:

```python
# backend/api/energy/router.py
def create_proxy_router(prefix: str, upstream_base: str) -> APIRouter:
    router = APIRouter(prefix=prefix)
    async def _proxy(request: Request, path: str):
        url = f"{upstream_base}{prefix}/{path}"
        ...
    for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
        router.add_api_route("/{path:path}", _proxy, methods=[method])
    return router

energy_router = create_proxy_router("/api/v1/energy", ENERGY_BASE)
intel_router = create_proxy_router("/api/v1/intelligence", ENERGY_BASE)
```

Both routers registered in `app.py`:
```python
from backend.api.energy.router import energy_router, intel_router
# in protected_routers:
energy_router, intel_router,
```

### 9.2 Authentication

All `/api/v1/intelligence/*` endpoints are behind the same `get_current_user` dependency as existing protected routes. The proxy passes auth tokens to the Energy Service, which currently ignores them. This is acceptable for Phase 2 — the Energy Service is an internal microservice on a Docker bridge network.

**Future:** Add per-route authorization checks in the Energy Service if the API is ever exposed directly.

### 9.3 Rate Limiting

The existing `slowapi` rate limiter (`@limiter.limit(...)`) should be applied to intelligence endpoints that trigger expensive computations:
- `POST /api/v1/intelligence/risk/score-all` — max 1 per 5 minutes
- `POST /api/v1/intelligence/digital-twin/run` — max 5 per hour per user
- `POST /api/v1/intelligence/spr/optimize` — max 10 per hour per user

### 9.4 Observability

All new endpoints should follow the existing pattern:
- `RequestTrackingMiddleware` — x-request-id, x-correlation-id headers
- Prometheus metrics via `Instrumentator()`
- Structured logging via `structlog`

New metrics to add:
- `risk_calculation_duration_seconds` (histogram)
- `simulation_run_duration_seconds` (histogram)
- `intelligence_api_requests_total` (counter, by endpoint and status)

### 9.5 Caching Strategy

| Data | Cache Strategy | TTL |
|---|---|---|
| Risk scores | Redis (if available) or in-memory dict, invalidated on recalc | 15 minutes |
| Supply chain graph | Generated on build, stored in `supply_chain_edges` table | Until relationship changes |
| Risk propagation | Cached in `risk_propagation` table | Until risk score changes |
| Simulation results | Stored in `simulation_runs` and `simulation_tick_events` | Permanent until deleted |
| Procurement recommendations | Cached in `procurement_recommendations` table per query_id | 24 hours |

### 9.6 Edge Cases and Failure Modes

| Edge Case | Handling |
|---|---|
| **Entity has no risk scores** | Return empty array, not 404 |
| **Supply chain graph empty** (no edges seeded) | Return empty graph; provide `/build` endpoint |
| **No articles match an entity** | Infrastructure event count = 0; risk score uses only static factors |
| **Simulation takes too long** | Cap at 90 ticks; implement tick timeout (1s per tick max) |
| **Recommendation query has no results** | Return empty recommendations array with explanation |
| **SPR has current_inventory > capacity** | Treat as data error, cap at capacity, log warning |
| **Refinery has no crude_types_accepted** | Assume universal compatibility (safe default) |
| **Risk recalculation in progress** | Return last known scores with `stale: true` flag |
| **Digital twin run references deleted entities** | Skip deleted entities in simulation, log warning |

### 9.7 Testing Strategy

| Test Type | Coverage | Tool |
|---|---|---|
| Unit tests | Risk engine scoring formulas, supply chain graph algorithms, simulation engine tick logic | pytest |
| Integration tests | API endpoints (via TestClient), database queries | pytest-asyncio |
| Seed data tests | All intelligence seed data loads and foreign keys are valid | pytest |
| Frontend component tests | New components (RiskBadge, SimulationConfigurator, etc.) | Vitest + Testing Library |
| E2E | Full flow: create event → risk recalculates → propagation → frontend reflects | Playwright (future) |

---

## 10. Appendix: Current Schema Reference

### 10.1 Existing Energy Service ENUM Types

| Enum | Values | Used By |
|---|---|---|
| `energy.lifecycle_state` | `draft`, `verified`, `operational`, `deprecated`, `archived` | All entity tables |
| `energy.operational_status` | `active`, `maintenance`, `offline`, `damaged`, `under_construction`, `mothballed`, `decommissioned` | All entity tables |
| `energy.criticality_level` | `low`, `medium`, `high`, `critical` | All entity tables |
| `energy.organization_type` | `national_oil_company`, `international_oil_company`, `independent`, `trader`, `utility`, `government`, `regulatory_body`, `consortium` | `energy.organizations` |
| `energy.relationship_type` | `supplies`, `connects_to`, `located_in`, `owned_by`, `operated_by`, `feeds_into`, `receives_from`, `monitored_by`, `regulated_by`, `adjacent_to`, `crosses` | `energy.entity_relationships` |
| `energy.event_type` | `shutdown`, `maintenance`, `cyber_attack`, `expansion`, `inspection`, `explosion`, `natural_disaster`, `sanctions`, `conflict`, `piracy`, `labor_strike`, `oil_spill` | `energy.infrastructure_events` |
| `energy.severity_level` | `low`, `medium`, `high`, `critical` | `energy.infrastructure_events` |
| `energy.location_type` | `country`, `eez`, `sea`, `region`, `economic_zone`, `strategic_area`, `strait`, `canal`, `territory` | `energy.locations` |
| `energy.asset_type` | `port`, `oil_field`, `gas_field`, `pipeline`, `refinery`, `power_plant`, `storage_facility`, `strategic_petroleum_reserve`, `import_corridor`, `shipping_route`, `supplier`, `location`, `organization` | `energy.entity_relationships`, `energy.infrastructure_events`, `energy.capacity_history` |

### 10.2 Existing Energy Entity Tables (14)

| Table | Entity Class | Asset Type | Entity-Specific Columns |
|---|---|---|---|
| `energy.locations` | Location | `location` | location_type, parent_location_id, iso_code, iso_code_3, region |
| `energy.organizations` | Organization | `organization` | organization_type, country_id |
| `energy.commodities` | Commodity | *(not an asset type)* | commodity_type, unit, benchmark_price, api_gravity, sulfur_content, category |
| `energy.ports` | Port | `port` | port_type, throughput_mtpa, storage_capacity_barrels, max_draft_m, annual_capacity_mtpa |
| `energy.oil_fields` | OilField | `oil_field` | reserve_estimate_barrels, production_bpd, api_gravity, sulfur_content |
| `energy.gas_fields` | GasField | `gas_field` | reserve_estimate_cf, production_mcfd |
| `energy.pipelines` | Pipeline | `pipeline` | length_km, capacity_bpd, diameter_inches, max_pressure_psi, commodity_type, flow_direction |
| `energy.refineries` | Refinery | `refinery` | capacity_bpd, nelson_complexity_index, crude_types_accepted, output_products |
| `energy.power_plants` | PowerPlant | `power_plant` | capacity_mw, fuel_type, plant_type |
| `energy.storage_facilities` | StorageFacility | `storage_facility` | capacity_barrels, facility_type |
| `energy.strategic_petroleum_reserves` | StrategicPetroleumReserve | `strategic_petroleum_reserve` | capacity_barrels, current_inventory_barrels, max_drawdown_rate_bpd, replenishment_rate_bpd |
| `energy.import_corridors` | ImportCorridor | `import_corridor` | origin_location_id, destination_location_id, distance_km, transit_time_days |
| `energy.shipping_routes` | ShippingRoute | `shipping_route` | origin_port_id, destination_port_id, distance_nm, transit_time_days, insurance_multiplier, risk_score |
| `energy.suppliers` | Supplier | `supplier` | organization_id, location_id, supplier_type, market_share_pct |

### 10.3 Existing Cross-Cutting Tables

| Table | Description |
|---|---|
| `energy.entity_relationships` | Directed relationships between any two asset-typed entities |
| `energy.infrastructure_events` | Infrastructure events/incidents linked to entities |
| `energy.capacity_history` | Time-series capacity/throughput metrics |

### 10.4 Existing Bridge Tables (public schema)

| Table | Description |
|---|---|
| `public.energy_entity_mappings` | NER entity text → energy asset link (article_id, entity_text, energy_asset_type, energy_asset_uuid) |
| `public.article_energy_enrichments` | Per-article aggregated energy context (JSONB) |

### 10.5 New Tables Summary (Phase 2)

| # | Table | Capability | Rows Est. |
|---|---|---|---|
| 1 | `energy.risk_factors` | Risk Intelligence | 15-30 |
| 2 | `energy.risk_scores` | Risk Intelligence | entities × dimensions × versions |
| 3 | `energy.supply_chain_edges` | Supply Chain Graph | entities × avg_out_degree |
| 4 | `energy.risk_propagation` | Supply Chain Graph | entities × affected_entities |
| 5 | `energy.event_article_links` | Event Intelligence | infrastructure_events × articles |
| 6 | `energy.simulation_scenarios` | Digital Twin | 10-20 |
| 7 | `energy.simulation_runs` | Digital Twin | runs × 1 |
| 8 | `energy.simulation_tick_events` | Digital Twin | runs × ticks × events |
| 9 | `energy.simulation_entity_state` | Digital Twin | runs × ticks × entities |
| 10 | `energy.refinery_crude_compatibility` | Procurement | refineries × commodities |
| 11 | `energy.procurement_recommendations` | Procurement | queries × 1 |
| 12 | `energy.spr_optimization_runs` | SPR Optimizer | runs × 1 |

### 10.6 Existing Kafka Topics

| Topic | Partitions | Retention | Publisher | Subscribers |
|---|---|---|---|---|
| `raw_articles` | 3 | 7 days | ingest-service | ml-service |
| `processed_articles` | 3 | 7 days | ml-service | db-service, embedding-service |

Phase 2 does NOT introduce new Kafka topics. All intelligence processing is either:
- Synchronous (inline in `consumer.py` handler chain)
- On-demand (triggered by API calls)
- Periodic (background task in the Energy Service lifespan)

---

> **End of Phase 2 Roadmap**
>
> This document is the blueprint for all Phase 2 implementation. Each capability section contains sufficient detail to begin implementation without additional architectural analysis. The Implementation Phasing section (8) provides the recommended build order across 8 weeks of development.
>
> **Next step after this document is reviewed:** Begin Phase 2A (Foundation) implementing the schema migration, risk engine, and data pipeline extensions.
