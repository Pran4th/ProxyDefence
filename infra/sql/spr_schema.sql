-- SPR Decision Intelligence Schema (Sprint 4)
-- Strategic Petroleum Reserve — release optimization, refill planning,
-- demand modeling, policy constraints, executive decision timeline.
-- Idempotent bootstrap on restart.

DO $$ BEGIN
    CREATE TYPE energy.spr_release_reason AS ENUM ('supply_disruption', 'price_stabilization', 'emergency', 'conflict', 'natural_disaster', 'strategic_rotation', 'policy_test');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.spr_facility_status AS ENUM ('operational', 'maintenance', 'offline', 'emergency_only', 'depleted', 'filling');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.spr_strategy AS ENUM ('conservative', 'aggressive', 'balanced', 'economic', 'strategic_preservation', 'critical_infrastructure_first');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.spr_timeline_phase AS ENUM ('immediate', 'short_term', 'medium_term', 'long_term');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 1. SPR Facilities — detailed asset model

CREATE TABLE IF NOT EXISTS energy.spr_facilities (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    slug                    TEXT UNIQUE NOT NULL,
    location_id             UUID REFERENCES energy.locations(uuid),
    country                 TEXT,
    latitude                DOUBLE PRECISION,
    longitude               DOUBLE PRECISION,
    storage_capacity_barrels DOUBLE PRECISION NOT NULL,
    current_inventory_barrels DOUBLE PRECISION DEFAULT 0,
    max_drawdown_rate_bpd   DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_refill_rate_bpd     DOUBLE PRECISION DEFAULT 0,
    fill_pct                DOUBLE PRECISION GENERATED ALWAYS AS (CASE WHEN storage_capacity_barrels > 0 THEN (current_inventory_barrels / storage_capacity_barrels) * 100 ELSE 0 END) STORED,
    facility_type           TEXT DEFAULT 'underground_cavern',
    commodity_types         TEXT[] DEFAULT '{crude}',
    connected_pipeline_uuids UUID[] DEFAULT '{}',
    connected_port_uuids    UUID[] DEFAULT '{}',
    connected_refinery_uuids UUID[] DEFAULT '{}',
    maintenance_schedule    JSONB DEFAULT '{}'::jsonb,
    emergency_status        TEXT DEFAULT 'normal',
    operational_availability DOUBLE PRECISION DEFAULT 1.0,
    last_inspection_date    TIMESTAMPTZ,
    reliability_score       DOUBLE PRECISION DEFAULT 0.95,
    status                  energy.spr_facility_status DEFAULT 'operational',
    operational_status      energy.operational_status DEFAULT 'active',
    criticality             energy.criticality_level DEFAULT 'critical',
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_by              TEXT DEFAULT 'system',
    updated_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_facilities_country ON energy.spr_facilities (country);
CREATE INDEX IF NOT EXISTS idx_spr_facilities_status ON energy.spr_facilities (status);
CREATE INDEX IF NOT EXISTS idx_spr_facilities_fill ON energy.spr_facilities (fill_pct DESC);
CREATE INDEX IF NOT EXISTS idx_spr_facilities_location ON energy.spr_facilities (location_id);

-- 2. SPR Inventory — time-series tracking

CREATE TABLE IF NOT EXISTS energy.spr_inventory (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    facility_uuid           UUID NOT NULL REFERENCES energy.spr_facilities(uuid) ON DELETE CASCADE,
    inventory_barrels       DOUBLE PRECISION NOT NULL,
    fill_pct                DOUBLE PRECISION DEFAULT 0,
    recorded_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source                  TEXT DEFAULT 'system',
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_inventory_facility ON energy.spr_inventory (facility_uuid, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_spr_inventory_recorded ON energy.spr_inventory (recorded_at DESC);

-- 3. SPR Capacity History

CREATE TABLE IF NOT EXISTS energy.spr_capacity (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    facility_uuid           UUID NOT NULL REFERENCES energy.spr_facilities(uuid) ON DELETE CASCADE,
    capacity_barrels        DOUBLE PRECISION NOT NULL,
    max_drawdown_bpd        DOUBLE PRECISION,
    max_refill_bpd          DOUBLE PRECISION,
    effective_from          DATE NOT NULL,
    effective_to            DATE,
    source                  TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_capacity_facility ON energy.spr_capacity (facility_uuid, effective_from DESC);

-- 4. SPR Release / Optimization Runs

CREATE TABLE IF NOT EXISTS energy.spr_release_runs (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    description             TEXT,
    scenario_uuid           UUID REFERENCES energy.simulation_scenarios(uuid) ON DELETE SET NULL,
    simulation_run_uuid     UUID REFERENCES energy.digital_twin_runs(uuid) ON DELETE SET NULL,
    procurement_run_uuid    UUID REFERENCES energy.procurement_runs(uuid) ON DELETE SET NULL,
    disruption_reason       energy.spr_release_reason DEFAULT 'supply_disruption',
    disruption_days         INTEGER NOT NULL DEFAULT 90,
    supply_gap_bpd          DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_spr_capacity      DOUBLE PRECISION DEFAULT 0,
    total_current_inventory DOUBLE PRECISION DEFAULT 0,
    total_max_drawdown_bpd  DOUBLE PRECISION DEFAULT 0,
    total_refill_rate_bpd   DOUBLE PRECISION DEFAULT 0,
    strategy                energy.spr_strategy DEFAULT 'balanced',
    policy_name             TEXT DEFAULT 'default',
    results                 JSONB DEFAULT '{}'::jsonb,
    decision_timeline       JSONB DEFAULT '[]'::jsonb,
    recommendations         JSONB DEFAULT '[]'::jsonb,
    execution_time_ms       DOUBLE PRECISION DEFAULT 0,
    status                  TEXT DEFAULT 'completed',
    created_by              TEXT DEFAULT 'system',
    updated_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_release_runs_scenario ON energy.spr_release_runs (scenario_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_release_runs_sim ON energy.spr_release_runs (simulation_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_release_runs_procurement ON energy.spr_release_runs (procurement_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_release_runs_created ON energy.spr_release_runs (created_at DESC);

-- 5. SPR Release Plans

CREATE TABLE IF NOT EXISTS energy.spr_release_plans (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID NOT NULL REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    facility_uuid           UUID NOT NULL REFERENCES energy.spr_facilities(uuid) ON DELETE CASCADE,
    release_volume_barrels  DOUBLE PRECISION NOT NULL DEFAULT 0,
    release_rate_bpd        DOUBLE PRECISION DEFAULT 0,
    start_day               INTEGER NOT NULL DEFAULT 1,
    duration_days           INTEGER DEFAULT 1,
    priority                INTEGER DEFAULT 5,
    target_refinery_uuids   UUID[] DEFAULT '{}',
    reason                  TEXT,
    cost_per_barrel         DOUBLE PRECISION DEFAULT 0,
    total_cost_usd          DOUBLE PRECISION DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_release_plans_run ON energy.spr_release_plans (release_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_release_plans_facility ON energy.spr_release_plans (facility_uuid);

-- 6. SPR Refill Plans

CREATE TABLE IF NOT EXISTS energy.spr_refill_plans (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID NOT NULL REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    facility_uuid           UUID NOT NULL REFERENCES energy.spr_facilities(uuid) ON DELETE CASCADE,
    refill_volume_barrels   DOUBLE PRECISION NOT NULL DEFAULT 0,
    refill_rate_bpd         DOUBLE PRECISION DEFAULT 0,
    start_day               INTEGER NOT NULL DEFAULT 1,
    duration_days           INTEGER NOT NULL DEFAULT 1,
    procurement_source      TEXT DEFAULT 'spot_market',
    estimated_cost_bbl      DOUBLE PRECISION DEFAULT 0,
    total_cost_usd          DOUBLE PRECISION DEFAULT 0,
    priority                INTEGER DEFAULT 5,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_refill_plans_run ON energy.spr_refill_plans (release_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_refill_plans_facility ON energy.spr_refill_plans (facility_uuid);

-- 7. SPR Recommendations (executive-level)

CREATE TABLE IF NOT EXISTS energy.spr_recommendations (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID NOT NULL REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    title                   TEXT NOT NULL,
    summary                 TEXT NOT NULL,
    recommendation_type     TEXT NOT NULL DEFAULT 'release',
    severity                TEXT DEFAULT 'info',
    release_volume_barrels  DOUBLE PRECISION DEFAULT 0,
    primary_facility        TEXT,
    reason                  TEXT,
    expected_supply_extension_days DOUBLE PRECISION DEFAULT 0,
    economic_savings_usd    DOUBLE PRECISION DEFAULT 0,
    confidence              DOUBLE PRECISION DEFAULT 0.7,
    alternative_strategy    TEXT,
    alternative_cost_delta  DOUBLE PRECISION DEFAULT 0,
    policy_used             TEXT DEFAULT 'default',
    strategy_used           energy.spr_strategy DEFAULT 'balanced',
    timeline_phase          energy.spr_timeline_phase DEFAULT 'immediate',
    data_sources            TEXT[] DEFAULT '{}',
    is_acknowledged         BOOLEAN DEFAULT FALSE,
    acknowledged_at         TIMESTAMPTZ,
    acknowledged_by         TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_recs_run ON energy.spr_recommendations (release_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_recs_severity ON energy.spr_recommendations (severity);
CREATE INDEX IF NOT EXISTS idx_spr_recs_type ON energy.spr_recommendations (recommendation_type);

-- 8. SPR Policy Constraints

CREATE TABLE IF NOT EXISTS energy.spr_policy_constraints (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL UNIQUE,
    description             TEXT,
    min_reserve_threshold_pct DOUBLE PRECISION DEFAULT 20.0,
    max_daily_release_bpd   DOUBLE PRECISION DEFAULT 5000000,
    emergency_only          BOOLEAN DEFAULT FALSE,
    strategic_preservation  BOOLEAN DEFAULT FALSE,
    economic_optimization   BOOLEAN DEFAULT TRUE,
    critical_infrastructure_first BOOLEAN DEFAULT TRUE,
    max_consecutive_release_days INTEGER DEFAULT 90,
    min_days_between_releases INTEGER DEFAULT 30,
    refill_trigger_pct      DOUBLE PRECISION DEFAULT 30.0,
    refill_priority         TEXT DEFAULT 'balanced',
    is_active               BOOLEAN DEFAULT TRUE,
    created_by              TEXT DEFAULT 'system',
    updated_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_policy_active ON energy.spr_policy_constraints (is_active) WHERE is_active = TRUE;

-- 9. SPR Consumption / Demand Forecasts

CREATE TABLE IF NOT EXISTS energy.spr_consumption_forecasts (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    region                  TEXT NOT NULL DEFAULT 'national',
    daily_demand_bpd        DOUBLE PRECISION NOT NULL DEFAULT 0,
    peak_demand_bpd         DOUBLE PRECISION,
    emergency_demand_bpd    DOUBLE PRECISION,
    supply_gap_bpd          DOUBLE PRECISION DEFAULT 0,
    days_of_supply_remaining DOUBLE PRECISION DEFAULT 0,
    inventory_burn_rate_bpd DOUBLE PRECISION DEFAULT 0,
    source                  TEXT DEFAULT 'digital_twin',
    forecast_date           DATE DEFAULT CURRENT_DATE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_consumption_run ON energy.spr_consumption_forecasts (release_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_consumption_region ON energy.spr_consumption_forecasts (region);

-- 10. SPR Distribution Network

CREATE TABLE IF NOT EXISTS energy.spr_distribution (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    facility_uuid           UUID NOT NULL REFERENCES energy.spr_facilities(uuid) ON DELETE CASCADE,
    target_entity_type      TEXT NOT NULL,
    target_entity_uuid      UUID NOT NULL,
    volume_barrels          DOUBLE PRECISION NOT NULL DEFAULT 0,
    route_description       TEXT,
    transit_time_days       DOUBLE PRECISION DEFAULT 1,
    transport_cost_bbl      DOUBLE PRECISION DEFAULT 0,
    priority                INTEGER DEFAULT 5,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_distribution_run ON energy.spr_distribution (release_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_distribution_facility ON energy.spr_distribution (facility_uuid);

-- 11. SPR Cost Analysis

CREATE TABLE IF NOT EXISTS energy.spr_cost_analysis (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID NOT NULL REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    cost_category           TEXT NOT NULL,
    description             TEXT,
    volume_barrels          DOUBLE PRECISION DEFAULT 0,
    unit_cost               DOUBLE PRECISION DEFAULT 0,
    total_cost              DOUBLE PRECISION DEFAULT 0,
    currency                TEXT DEFAULT 'USD',
    is_estimated            BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_cost_run ON energy.spr_cost_analysis (release_run_uuid);

-- 12. SPR Assumptions

CREATE TABLE IF NOT EXISTS energy.spr_assumptions (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID NOT NULL REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    assumption_key          TEXT NOT NULL,
    assumption_value        TEXT NOT NULL,
    assumption_type         TEXT DEFAULT 'parameter',
    source                  TEXT DEFAULT 'system',
    confidence              DOUBLE PRECISION DEFAULT 0.7,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_assumptions_run ON energy.spr_assumptions (release_run_uuid);

-- 13. Executive Decision Timeline

CREATE TABLE IF NOT EXISTS energy.spr_decision_timeline (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    release_run_uuid        UUID NOT NULL REFERENCES energy.spr_release_runs(uuid) ON DELETE CASCADE,
    phase                   energy.spr_timeline_phase NOT NULL DEFAULT 'immediate',
    sequence_order          INTEGER NOT NULL DEFAULT 1,
    timing_label            TEXT NOT NULL,
    action                  TEXT NOT NULL,
    details                 TEXT,
    volume_barrels          DOUBLE PRECISION DEFAULT 0,
    facility                TEXT,
    expected_impact         TEXT,
    confidence              DOUBLE PRECISION DEFAULT 0.7,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_timeline_run ON energy.spr_decision_timeline (release_run_uuid, sequence_order);

-- Seed default policy

INSERT INTO energy.spr_policy_constraints (uuid, name, description) VALUES
    (gen_random_uuid(), 'default', 'Default SPR policy — balanced approach with 20% strategic reserve threshold')
ON CONFLICT (name) DO NOTHING;

INSERT INTO energy.spr_policy_constraints (uuid, name, description, strategic_preservation, min_reserve_threshold_pct) VALUES
    (gen_random_uuid(), 'conservative', 'Conservative policy — preserve at least 50% for strategic emergencies', TRUE, 50.0)
ON CONFLICT (name) DO NOTHING;

INSERT INTO energy.spr_policy_constraints (uuid, name, description, economic_optimization, min_reserve_threshold_pct) VALUES
    (gen_random_uuid(), 'aggressive', 'Aggressive release policy — maximize economic stability', FALSE, 10.0)
ON CONFLICT (name) DO NOTHING;
