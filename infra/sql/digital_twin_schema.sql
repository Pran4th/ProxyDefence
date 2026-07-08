-- Digital Twin Schema for Energy Supply Chain Simulation
-- Extends energy. schema with network graph, simulation, and flow tracking

-- ─── ENUM types ────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE energy.simulation_status AS ENUM ('pending', 'running', 'completed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.node_category AS ENUM ('producer', 'exporter', 'shipping', 'import', 'pipeline', 'storage', 'refinery', 'spr', 'consumer', 'distribution', 'power_generator');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.edge_category AS ENUM ('crude_flow', 'product_flow', 'transit', 'drawdown', 'consumption', 'storage_inject', 'storage_withdraw', 'backup_route', 'alternative_supply', 'emergency_supply');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.simulation_mode AS ENUM ('scenario', 'realtime', 'comparison');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.scenario_category AS ENUM ('chokepoint', 'sanctions', 'natural_disaster', 'conflict', 'cyber', 'supply_shock', 'demand_shock', 'infrastructure_failure', 'custom');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─── 1. Network Nodes ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.network_nodes (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    node_type               energy.asset_type NOT NULL,
    entity_id               BIGINT,
    name                    TEXT NOT NULL,
    category                energy.node_category NOT NULL,
    location_id             UUID,
    country                 TEXT,
    latitude                DOUBLE PRECISION,
    longitude               DOUBLE PRECISION,
    capacity_bpd            DOUBLE PRECISION,
    storage_capacity_barrels DOUBLE PRECISION,
    current_inventory_barrels DOUBLE PRECISION,
    max_drawdown_bpd        DOUBLE PRECISION,
    operational_status      TEXT DEFAULT 'active',
    criticality             TEXT DEFAULT 'medium',
    metadata                JSONB DEFAULT '{}'::jsonb,
    is_active               BOOLEAN DEFAULT TRUE,
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── 2. Network Edges ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.network_edges (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    source_node_id          BIGINT NOT NULL REFERENCES energy.network_nodes(id) ON DELETE CASCADE,
    target_node_id          BIGINT NOT NULL REFERENCES energy.network_nodes(id) ON DELETE CASCADE,
    edge_type               energy.edge_category NOT NULL,
    category                TEXT DEFAULT 'primary',
    max_capacity_bpd        DOUBLE PRECISION,
    current_flow_bpd        DOUBLE PRECISION DEFAULT 0,
    utilization_pct         DOUBLE PRECISION DEFAULT 0,
    travel_time_hours       DOUBLE PRECISION,
    transport_cost_bbl      DOUBLE PRECISION,
    risk_multiplier         DOUBLE PRECISION DEFAULT 1.0,
    reliability             DOUBLE PRECISION DEFAULT 0.95,
    priority                INTEGER DEFAULT 5,
    commodity_type          TEXT DEFAULT 'crude',
    metadata                JSONB DEFAULT '{}'::jsonb,
    is_active               BOOLEAN DEFAULT TRUE,
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_node_id, target_node_id, edge_type)
);

-- ─── 3. Simulation Scenarios ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.simulation_scenarios (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    description             TEXT,
    category                energy.scenario_category NOT NULL DEFAULT 'custom',
    config                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    assumptions             JSONB DEFAULT '{}'::jsonb,
    is_template             BOOLEAN DEFAULT FALSE,
    severity                TEXT DEFAULT 'medium',
    affected_nodes          UUID[] DEFAULT '{}',
    created_by              TEXT DEFAULT 'system',
    updated_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── 4. Simulation Runs ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.digital_twin_runs (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    scenario_id             BIGINT REFERENCES energy.simulation_scenarios(id) ON DELETE SET NULL,
    name                    TEXT NOT NULL,
    description             TEXT,
    mode                    energy.simulation_mode DEFAULT 'scenario',
    status                  energy.simulation_status DEFAULT 'pending',
    tick_interval           TEXT DEFAULT 'day',
    max_ticks               INTEGER DEFAULT 90,
    current_tick            INTEGER DEFAULT 0,
    config                  JSONB DEFAULT '{}'::jsonb,
    risk_snapshot           JSONB DEFAULT '{}'::jsonb,
    entity_snapshot         JSONB DEFAULT '{}'::jsonb,
    aggregate_impacts       JSONB DEFAULT '{}'::jsonb,
    supply_gap_bpd          DOUBLE PRECISION DEFAULT 0,
    max_supply_gap_bpd      DOUBLE PRECISION DEFAULT 0,
    days_until_critical     INTEGER,
    economic_impact_usd     DOUBLE PRECISION DEFAULT 0,
    gdp_impact_pct          DOUBLE PRECISION DEFAULT 0,
    created_by              TEXT DEFAULT 'system',
    started_at              TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    execution_time_ms       DOUBLE PRECISION DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── 5. Flow States ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.flow_states (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    run_id                  BIGINT NOT NULL REFERENCES energy.digital_twin_runs(id) ON DELETE CASCADE,
    tick                    INTEGER NOT NULL,
    node_id                 BIGINT NOT NULL REFERENCES energy.network_nodes(id) ON DELETE CASCADE,
    edge_id                 BIGINT REFERENCES energy.network_edges(id) ON DELETE SET NULL,
    flow_bpd                DOUBLE PRECISION DEFAULT 0,
    capacity_bpd            DOUBLE PRECISION DEFAULT 0,
    utilization_pct         DOUBLE PRECISION DEFAULT 0,
    inventory_barrels       DOUBLE PRECISION DEFAULT 0,
    supply_gap_bpd          DOUBLE PRECISION DEFAULT 0,
    is_bottleneck           BOOLEAN DEFAULT FALSE,
    is_idle                 BOOLEAN DEFAULT FALSE,
    status                  TEXT DEFAULT 'normal',
    metadata                JSONB DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── 6. Tick Events ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.simulation_tick_events (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    run_id                  BIGINT NOT NULL REFERENCES energy.digital_twin_runs(id) ON DELETE CASCADE,
    tick                    INTEGER NOT NULL,
    event_type              TEXT NOT NULL,
    node_id                 BIGINT REFERENCES energy.network_nodes(id) ON DELETE SET NULL,
    description             TEXT,
    severity                TEXT DEFAULT 'medium',
    impact                  JSONB DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── 7. Network Snapshots ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.network_snapshots (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    description             TEXT,
    snapshot_type           TEXT DEFAULT 'realtime',
    source_run_id           BIGINT REFERENCES energy.digital_twin_runs(id) ON DELETE SET NULL,
    node_state              JSONB NOT NULL DEFAULT '[]'::jsonb,
    edge_state              JSONB NOT NULL DEFAULT '[]'::jsonb,
    metrics                 JSONB DEFAULT '{}'::jsonb,
    created_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── 8. Demand Profiles ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.demand_profiles (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    region                  TEXT NOT NULL,
    commodity_type          TEXT DEFAULT 'crude',
    daily_demand_bpd        DOUBLE PRECISION NOT NULL,
    peak_demand_bpd         DOUBLE PRECISION,
    demand_growth_pct       DOUBLE PRECISION DEFAULT 0,
    profile_type            TEXT DEFAULT 'baseline',
    seasonality             JSONB DEFAULT '{}'::jsonb,
    source                  TEXT DEFAULT 'estimated',
    valid_from              DATE,
    valid_to                DATE,
    is_active               BOOLEAN DEFAULT TRUE,
    created_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── 9. Flow Constraints ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.flow_constraints (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    edge_id                 BIGINT REFERENCES energy.network_edges(id) ON DELETE CASCADE,
    constraint_type         TEXT NOT NULL,
    max_bpd                 DOUBLE PRECISION,
    min_bpd                 DOUBLE PRECISION DEFAULT 0,
    priority                INTEGER DEFAULT 5,
    effective_from          TIMESTAMPTZ,
    effective_to            TIMESTAMPTZ,
    downstream_effect       JSONB DEFAULT '{}'::jsonb,
    metadata                JSONB DEFAULT '{}'::jsonb,
    is_active               BOOLEAN DEFAULT TRUE,
    created_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Indexes ──────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_network_nodes_type     ON energy.network_nodes (node_type);
CREATE INDEX IF NOT EXISTS idx_network_nodes_category ON energy.network_nodes (category);
CREATE INDEX IF NOT EXISTS idx_network_nodes_country  ON energy.network_nodes (country);
CREATE INDEX IF NOT EXISTS idx_network_nodes_active   ON energy.network_nodes (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_network_nodes_entity   ON energy.network_nodes (node_type, entity_id) WHERE entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_network_edges_source ON energy.network_edges (source_node_id);
CREATE INDEX IF NOT EXISTS idx_network_edges_target ON energy.network_edges (target_node_id);
CREATE INDEX IF NOT EXISTS idx_network_edges_type   ON energy.network_edges (edge_type);
CREATE INDEX IF NOT EXISTS idx_network_edges_active ON energy.network_edges (is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_sim_scenarios_category ON energy.simulation_scenarios (category);
CREATE INDEX IF NOT EXISTS idx_sim_scenarios_template ON energy.simulation_scenarios (is_template) WHERE is_template = TRUE;

CREATE INDEX IF NOT EXISTS idx_dt_runs_scenario ON energy.digital_twin_runs (scenario_id);
CREATE INDEX IF NOT EXISTS idx_dt_runs_status   ON energy.digital_twin_runs (status);
CREATE INDEX IF NOT EXISTS idx_dt_runs_created  ON energy.digital_twin_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_flow_states_run_tick ON energy.flow_states (run_id, tick);
CREATE INDEX IF NOT EXISTS idx_flow_states_node     ON energy.flow_states (node_id);

CREATE INDEX IF NOT EXISTS idx_tick_events_run  ON energy.simulation_tick_events (run_id, tick);
CREATE INDEX IF NOT EXISTS idx_tick_events_node ON energy.simulation_tick_events (node_id) WHERE node_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_demand_profiles_region ON energy.demand_profiles (region);
CREATE INDEX IF NOT EXISTS idx_demand_profiles_active ON energy.demand_profiles (is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_flow_constraints_edge   ON energy.flow_constraints (edge_id);
CREATE INDEX IF NOT EXISTS idx_flow_constraints_active ON energy.flow_constraints (is_active) WHERE is_active = TRUE;
