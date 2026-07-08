-- Adaptive Procurement Orchestrator Schema (Sprint 3)
-- Extends energy. schema with procurement optimization, supplier intelligence,
-- refinery compatibility, route costing, and executive recommendations.
-- All CREATE statements are idempotent for safe bootstrap on restart.

-- ─── ENUM types ────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE energy.procurement_priority AS ENUM ('critical', 'high', 'medium', 'low');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.procurement_status AS ENUM ('draft', 'active', 'approved', 'executed', 'cancelled', 'expired');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Add 'completed' to existing enum if not present (PG 9.3+)
DO $$ BEGIN
    ALTER TYPE energy.procurement_status ADD VALUE IF NOT EXISTS 'completed';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE energy.compatibility_score AS ENUM ('optimal', 'compatible', 'partial', 'incompatible');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─── 1. Supplier Intelligence ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.supplier_intelligence (
    id                          BIGSERIAL PRIMARY KEY,
    uuid                        UUID UNIQUE DEFAULT gen_random_uuid(),
    supplier_uuid               UUID NOT NULL REFERENCES energy.suppliers(uuid) ON DELETE CASCADE,
    country_political_stability DOUBLE PRECISION DEFAULT 0.5,
    reliability_score           DOUBLE PRECISION DEFAULT 0.7,
    contract_type               TEXT DEFAULT 'spot',
    contract_expiry             DATE,
    sanctions_exposure          BOOLEAN DEFAULT FALSE,
    compliance_risk             TEXT DEFAULT 'low',
    credit_rating               TEXT,
    avg_lead_time_days          INTEGER DEFAULT 30,
    on_time_delivery_pct        DOUBLE PRECISION DEFAULT 85.0,
    api_gravity_min             DOUBLE PRECISION,
    api_gravity_max             DOUBLE PRECISION,
    sulfur_content_max          DOUBLE PRECISION,
    typical_volume_bpd          DOUBLE PRECISION,
    spot_premium_bbl            DOUBLE PRECISION DEFAULT 0,
    strategic_value             DOUBLE PRECISION DEFAULT 0.5,
    notes                       TEXT,
    metadata                    JSONB DEFAULT '{}'::jsonb,
    is_deleted                  BOOLEAN DEFAULT FALSE,
    created_by                  TEXT DEFAULT 'system',
    updated_by                  TEXT DEFAULT 'system',
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_supplier_intel_supplier
    ON energy.supplier_intelligence (supplier_uuid);
CREATE INDEX IF NOT EXISTS idx_supplier_intel_reliability
    ON energy.supplier_intelligence (reliability_score DESC);
CREATE INDEX IF NOT EXISTS idx_supplier_intel_sanctions
    ON energy.supplier_intelligence (sanctions_exposure) WHERE sanctions_exposure = TRUE;

-- ─── 2. Refinery-Crude Compatibility ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.refinery_crude_compatibility (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    refinery_uuid           UUID NOT NULL REFERENCES energy.refineries(uuid) ON DELETE CASCADE,
    commodity_uuid          UUID NOT NULL REFERENCES energy.commodities(uuid) ON DELETE CASCADE,
    compatibility           energy.compatibility_score NOT NULL DEFAULT 'compatible',
    compatibility_reason    TEXT,
    max_blend_pct           DOUBLE PRECISION DEFAULT 100.0,
    yield_impact_pct        DOUBLE PRECISION DEFAULT 0,
    throughput_penalty_pct  DOUBLE PRECISION DEFAULT 0,
    metadata                JSONB DEFAULT '{}'::jsonb,
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_by              TEXT DEFAULT 'system',
    updated_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (refinery_uuid, commodity_uuid)
);

CREATE INDEX IF NOT EXISTS idx_ref_comp_refinery
    ON energy.refinery_crude_compatibility (refinery_uuid);
CREATE INDEX IF NOT EXISTS idx_ref_comp_commodity
    ON energy.refinery_crude_compatibility (commodity_uuid);
CREATE INDEX IF NOT EXISTS idx_ref_comp_score
    ON energy.refinery_crude_compatibility (compatibility);

-- ─── 3. Route Costs ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.route_costs (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    origin_node_id          BIGINT NOT NULL REFERENCES energy.network_nodes(id) ON DELETE CASCADE,
    destination_node_id     BIGINT NOT NULL REFERENCES energy.network_nodes(id) ON DELETE CASCADE,
    commodity_uuid          UUID REFERENCES energy.commodities(uuid),
    transport_cost_bbl      DOUBLE PRECISION DEFAULT 0,
    insurance_cost_bbl      DOUBLE PRECISION DEFAULT 0,
    tariff_cost_bbl         DOUBLE PRECISION DEFAULT 0,
    risk_adjustment_bbl     DOUBLE PRECISION DEFAULT 0,
    total_cost_bbl          DOUBLE PRECISION DEFAULT 0,
    transit_time_days       DOUBLE PRECISION,
    distance_nm             DOUBLE PRECISION,
    route_risk_score        DOUBLE PRECISION DEFAULT 0,
    reliability             DOUBLE PRECISION DEFAULT 0.9,
    metadata                JSONB DEFAULT '{}'::jsonb,
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_by              TEXT DEFAULT 'system',
    updated_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (origin_node_id, destination_node_id, commodity_uuid)
);

CREATE INDEX IF NOT EXISTS idx_route_costs_origin
    ON energy.route_costs (origin_node_id);
CREATE INDEX IF NOT EXISTS idx_route_costs_dest
    ON energy.route_costs (destination_node_id);
CREATE INDEX IF NOT EXISTS idx_route_costs_total
    ON energy.route_costs (total_cost_bbl);
CREATE UNIQUE INDEX IF NOT EXISTS idx_route_costs_unique_null
    ON energy.route_costs (origin_node_id, destination_node_id) WHERE commodity_uuid IS NULL;

-- ─── 4. Alternative Suppliers ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.alternative_suppliers (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    procurement_run_uuid    UUID NOT NULL,
    commodity_uuid          UUID NOT NULL REFERENCES energy.commodities(uuid) ON DELETE CASCADE,
    original_supplier_uuid  UUID NOT NULL REFERENCES energy.suppliers(uuid) ON DELETE CASCADE,
    alternative_supplier_uuid UUID NOT NULL REFERENCES energy.suppliers(uuid) ON DELETE CASCADE,
    match_score             DOUBLE PRECISION NOT NULL DEFAULT 0,
    price_premium_bbl       DOUBLE PRECISION DEFAULT 0,
    additional_lead_days    INTEGER DEFAULT 0,
    volume_available_bpd    DOUBLE PRECISION DEFAULT 0,
    reliability             DOUBLE PRECISION DEFAULT 0.5,
    country_shift           TEXT,
    risk_delta              DOUBLE PRECISION DEFAULT 0,
    reason                  TEXT,
    metadata                JSONB DEFAULT '{}'::jsonb,
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alt_suppliers_run
    ON energy.alternative_suppliers (procurement_run_uuid);
CREATE INDEX IF NOT EXISTS idx_alt_suppliers_commodity
    ON energy.alternative_suppliers (commodity_uuid);
CREATE INDEX IF NOT EXISTS idx_alt_suppliers_score
    ON energy.alternative_suppliers (match_score DESC);

-- ─── 5. Procurement Runs ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.procurement_runs (
    id                          BIGSERIAL PRIMARY KEY,
    uuid                        UUID UNIQUE DEFAULT gen_random_uuid(),
    simulation_run_uuid         UUID REFERENCES energy.digital_twin_runs(uuid) ON DELETE SET NULL,
    name                        TEXT NOT NULL,
    description                 TEXT,
    status                      energy.procurement_status DEFAULT 'draft',
    priority                    energy.procurement_priority DEFAULT 'medium',
    optimization_goal           TEXT DEFAULT 'balanced',
    total_supply_gap_bpd        DOUBLE PRECISION DEFAULT 0,
    total_recommended_bpd       DOUBLE PRECISION DEFAULT 0,
    total_cost_estimate_usd     DOUBLE PRECISION DEFAULT 0,
    total_risk_score            DOUBLE PRECISION DEFAULT 0,
    pareto_options              JSONB DEFAULT '[]'::jsonb,
    assumptions                 JSONB DEFAULT '{}'::jsonb,
    executive_summary           TEXT,
    created_by                  TEXT DEFAULT 'system',
    updated_by                  TEXT DEFAULT 'system',
    started_at                  TIMESTAMPTZ,
    completed_at                TIMESTAMPTZ,
    execution_time_ms           DOUBLE PRECISION DEFAULT 0,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proc_runs_status
    ON energy.procurement_runs (status);
CREATE INDEX IF NOT EXISTS idx_proc_runs_priority
    ON energy.procurement_runs (priority);
CREATE INDEX IF NOT EXISTS idx_proc_runs_simulation
    ON energy.procurement_runs (simulation_run_uuid);
CREATE INDEX IF NOT EXISTS idx_proc_runs_created
    ON energy.procurement_runs (created_at DESC);

-- ─── 6. Procurement Recommendations ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.procurement_recommendations (
    id                          BIGSERIAL PRIMARY KEY,
    uuid                        UUID UNIQUE DEFAULT gen_random_uuid(),
    procurement_run_uuid        UUID NOT NULL REFERENCES energy.procurement_runs(uuid) ON DELETE CASCADE,
    recommendation_type         TEXT NOT NULL,
    priority                    energy.procurement_priority NOT NULL DEFAULT 'medium',
    title                       TEXT NOT NULL,
    description                 TEXT,
    commodity_uuid              UUID REFERENCES energy.commodities(uuid),
    volume_bpd                  DOUBLE PRECISION DEFAULT 0,
    unit_cost_usd               DOUBLE PRECISION DEFAULT 0,
    total_cost_usd              DOUBLE PRECISION DEFAULT 0,
    supplier_uuid               UUID REFERENCES energy.suppliers(uuid),
    alternative_supplier_uuid   UUID REFERENCES energy.suppliers(uuid),
    route_description           TEXT,
    risk_score                  DOUBLE PRECISION DEFAULT 0,
    confidence                  DOUBLE PRECISION DEFAULT 0.7,
    urgency                     TEXT DEFAULT 'normal',
    expected_impact             TEXT,
    data_sources                TEXT[] DEFAULT '{}',
    metadata                    JSONB DEFAULT '{}'::jsonb,
    is_actioned                 BOOLEAN DEFAULT FALSE,
    actioned_at                 TIMESTAMPTZ,
    actioned_by                 TEXT,
    is_deleted                  BOOLEAN DEFAULT FALSE,
    created_by                  TEXT DEFAULT 'system',
    updated_by                  TEXT DEFAULT 'system',
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proc_recs_run
    ON energy.procurement_recommendations (procurement_run_uuid);
CREATE INDEX IF NOT EXISTS idx_proc_recs_priority
    ON energy.procurement_recommendations (priority);
CREATE INDEX IF NOT EXISTS idx_proc_recs_type
    ON energy.procurement_recommendations (recommendation_type);
CREATE INDEX IF NOT EXISTS idx_proc_recs_commodity
    ON energy.procurement_recommendations (commodity_uuid);

-- ─── 7. Executive Recommendation Cards ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.executive_recommendations (
    id                          BIGSERIAL PRIMARY KEY,
    uuid                        UUID UNIQUE DEFAULT gen_random_uuid(),
    procurement_run_uuid        UUID NOT NULL REFERENCES energy.procurement_runs(uuid) ON DELETE CASCADE,
    title                       TEXT NOT NULL,
    summary                     TEXT NOT NULL,
    severity                    TEXT DEFAULT 'info',
    category                    TEXT NOT NULL,
    financial_impact            JSONB DEFAULT '{}'::jsonb,
    operational_impact          JSONB DEFAULT '{}'::jsonb,
    strategic_importance        DOUBLE PRECISION DEFAULT 0.5,
    confidence                  DOUBLE PRECISION DEFAULT 0.7,
    time_horizon                TEXT DEFAULT 'immediate',
    recommended_actions         JSONB DEFAULT '[]'::jsonb,
    supporting_data             JSONB DEFAULT '{}'::jsonb,
    data_sources                TEXT[] DEFAULT '{}',
    is_acknowledged             BOOLEAN DEFAULT FALSE,
    acknowledged_at             TIMESTAMPTZ,
    acknowledged_by             TEXT,
    is_deleted                  BOOLEAN DEFAULT FALSE,
    created_by                  TEXT DEFAULT 'system',
    updated_by                  TEXT DEFAULT 'system',
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exec_recs_run
    ON energy.executive_recommendations (procurement_run_uuid);
CREATE INDEX IF NOT EXISTS idx_exec_recs_severity
    ON energy.executive_recommendations (severity);
CREATE INDEX IF NOT EXISTS idx_exec_recs_category
    ON energy.executive_recommendations (category);
CREATE INDEX IF NOT EXISTS idx_exec_recs_created
    ON energy.executive_recommendations (created_at DESC);

-- ─── 8. Procurement Assumptions ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.procurement_assumptions (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    procurement_run_uuid    UUID NOT NULL REFERENCES energy.procurement_runs(uuid) ON DELETE CASCADE,
    assumption_key          TEXT NOT NULL,
    assumption_value        TEXT NOT NULL,
    assumption_type         TEXT DEFAULT 'parameter',
    source                  TEXT DEFAULT 'system',
    confidence              DOUBLE PRECISION DEFAULT 0.7,
    metadata                JSONB DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proc_assumptions_run
    ON energy.procurement_assumptions (procurement_run_uuid);

-- ─── 9. RFQ Outputs ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.rfq_outputs (
    id                      BIGSERIAL PRIMARY KEY,
    uuid                    UUID UNIQUE DEFAULT gen_random_uuid(),
    procurement_run_uuid    UUID NOT NULL REFERENCES energy.procurement_runs(uuid) ON DELETE CASCADE,
    supplier_uuid           UUID NOT NULL REFERENCES energy.suppliers(uuid) ON DELETE CASCADE,
    commodity_uuid          UUID NOT NULL REFERENCES energy.commodities(uuid) ON DELETE CASCADE,
    volume_bpd              DOUBLE PRECISION DEFAULT 0,
    proposed_price_bbl      DOUBLE PRECISION DEFAULT 0,
    delivery_terms          TEXT DEFAULT 'FOB',
    lead_time_days          INTEGER DEFAULT 30,
    payment_terms           TEXT DEFAULT 'LC_30',
    validity_days           INTEGER DEFAULT 30,
    status                  TEXT DEFAULT 'draft',
    response_due            TIMESTAMPTZ,
    metadata                JSONB DEFAULT '{}'::jsonb,
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_by              TEXT DEFAULT 'system',
    updated_by              TEXT DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rfq_run
    ON energy.rfq_outputs (procurement_run_uuid);
CREATE INDEX IF NOT EXISTS idx_rfq_supplier
    ON energy.rfq_outputs (supplier_uuid);

-- ─── Indexes for often-joined query patterns ─────────────────────────────

CREATE INDEX IF NOT EXISTS idx_proc_recs_lookup
    ON energy.procurement_recommendations (procurement_run_uuid, priority, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exec_recs_lookup
    ON energy.executive_recommendations (procurement_run_uuid, severity, created_at DESC);

-- ─── 10. SPR Optimization Runs ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS energy.spr_optimization_runs (
    id                          BIGSERIAL PRIMARY KEY,
    uuid                        UUID UNIQUE DEFAULT gen_random_uuid(),
    procurement_run_uuid        UUID REFERENCES energy.procurement_runs(uuid) ON DELETE SET NULL,
    name                        TEXT NOT NULL,
    description                 TEXT,
    disruption_scenario         TEXT NOT NULL DEFAULT 'generic',
    disruption_days             INTEGER NOT NULL DEFAULT 90,
    supply_gap_bpd              DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_import_shortfall      DOUBLE PRECISION DEFAULT 0,
    total_spr_capacity_barrels  DOUBLE PRECISION DEFAULT 0,
    total_current_inventory     DOUBLE PRECISION DEFAULT 0,
    total_max_drawdown_bpd      DOUBLE PRECISION DEFAULT 0,
    total_replenishment_bpd     DOUBLE PRECISION DEFAULT 0,
    max_drawdown_days           INTEGER DEFAULT 0,
    days_until_depletion        INTEGER DEFAULT 0,
    total_drawdown_volume       DOUBLE PRECISION DEFAULT 0,
    remaining_inventory         DOUBLE PRECISION DEFAULT 0,
    uncovered_gap_bpd           DOUBLE PRECISION DEFAULT 0,
    replenishment_volume_needed DOUBLE PRECISION DEFAULT 0,
    replenishment_days_needed   INTEGER DEFAULT 0,
    emergency_purchase_volume   DOUBLE PRECISION DEFAULT 0,
    emergency_purchase_cost_est DOUBLE PRECISION DEFAULT 0,
    coverage_pct                DOUBLE PRECISION DEFAULT 0,
    results                     JSONB DEFAULT '{}'::jsonb,
    recommendations             JSONB DEFAULT '[]'::jsonb,
    status                      TEXT DEFAULT 'completed',
    execution_time_ms           DOUBLE PRECISION DEFAULT 0,
    created_by                  TEXT DEFAULT 'system',
    updated_by                  TEXT DEFAULT 'system',
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spr_opt_runs_procurement
    ON energy.spr_optimization_runs (procurement_run_uuid);
CREATE INDEX IF NOT EXISTS idx_spr_opt_runs_scenario
    ON energy.spr_optimization_runs (disruption_scenario);
CREATE INDEX IF NOT EXISTS idx_spr_opt_runs_created
    ON energy.spr_optimization_runs (created_at DESC);
