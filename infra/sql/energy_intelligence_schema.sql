-- Energy Intelligence Schema (Phase 2)
-- Risk scoring, disruption detection, data ingestion tables
-- Aligned with services/energy-service/services/risk_engine.py

CREATE SCHEMA IF NOT EXISTS energy;

-- ============================================================
-- RISK FACTORS
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.risk_factors (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    weight          DOUBLE PRECISION DEFAULT 1.0,
    data_source     TEXT,
    config          JSONB DEFAULT '{}'::jsonb,
    is_active       BOOLEAN DEFAULT TRUE,
    version         INTEGER DEFAULT 1,
    created_by      TEXT DEFAULT 'system',
    updated_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- RISK SCORES
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.risk_scores (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    entity_uuid     UUID NOT NULL,
    entity_type     TEXT NOT NULL,
    dimension       TEXT NOT NULL,
    score           DOUBLE PRECISION NOT NULL,
    confidence      DOUBLE PRECISION DEFAULT 0.7,
    breakdown       JSONB DEFAULT '{}'::jsonb,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_scores_entity
    ON energy.risk_scores (entity_uuid, entity_type);
CREATE INDEX IF NOT EXISTS idx_risk_scores_dimension
    ON energy.risk_scores (dimension);
CREATE INDEX IF NOT EXISTS idx_risk_scores_score_desc
    ON energy.risk_scores (score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_expires
    ON energy.risk_scores (expires_at);

-- ============================================================
-- DISRUPTION SIGNALS
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.disruption_signals (
    id                  BIGSERIAL PRIMARY KEY,
    uuid                UUID UNIQUE DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    description         TEXT,
    source              TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'moderate',
    risk_dimension      TEXT NOT NULL DEFAULT 'operational',
    affected_entity_type TEXT,
    affected_entity_uuid UUID,
    affected_commodities TEXT[] DEFAULT '{}',
    affected_regions    TEXT[] DEFAULT '{}',
    confidence          DOUBLE PRECISION DEFAULT 0.7,
    evidence_urls       TEXT[] DEFAULT '{}',
    ttl_hours           INTEGER DEFAULT 72,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disruption_signals_severity
    ON energy.disruption_signals (severity, expires_at);
CREATE INDEX IF NOT EXISTS idx_disruption_signals_created
    ON energy.disruption_signals (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_disruption_signals_dimension
    ON energy.disruption_signals (risk_dimension);
CREATE INDEX IF NOT EXISTS idx_disruption_signals_entity
    ON energy.disruption_signals (affected_entity_uuid);

-- ============================================================
-- RESPONSE TELEMETRY
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.response_telemetry (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    signal_id       UUID,
    signal_type     VARCHAR(50) NOT NULL,
    signal_detected_at         TIMESTAMPTZ NOT NULL,
    analysis_started_at        TIMESTAMPTZ,
    analysis_completed_at      TIMESTAMPTZ,
    recommendation_generated_at TIMESTAMPTZ,
    recommendation_approved_at  TIMESTAMPTZ,
    total_latency_seconds      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_response_telemetry_signal
    ON energy.response_telemetry (signal_id);

-- ============================================================
-- COMMODITY PRICES
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.commodity_prices (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    commodity_name  TEXT NOT NULL,
    commodity_family TEXT NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    unit            TEXT NOT NULL,
    change_pct      DOUBLE PRECISION DEFAULT 0,
    source          TEXT NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commodity_prices_family
    ON energy.commodity_prices (commodity_family, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_commodity_prices_recent
    ON energy.commodity_prices (recorded_at DESC);

-- ============================================================
-- AIS POSITIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.ais_positions (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    location_name   TEXT NOT NULL,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    location_type   TEXT NOT NULL DEFAULT 'chokepoint',
    vessel_count    INTEGER DEFAULT 0,
    avg_speed_knots DOUBLE PRECISION,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ais_positions_type
    ON energy.ais_positions (location_type, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_ais_positions_recent
    ON energy.ais_positions (recorded_at DESC);

-- ============================================================
-- SANCTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.sanctions (
    id                  BIGSERIAL PRIMARY KEY,
    uuid                UUID UNIQUE DEFAULT gen_random_uuid(),
    country_code        VARCHAR(10) NOT NULL,
    country_name        TEXT NOT NULL,
    sanction_scope      TEXT NOT NULL,
    imposed_by          TEXT NOT NULL,
    affected_commodities TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'primary',
    is_active           BOOLEAN DEFAULT TRUE,
    source              TEXT NOT NULL DEFAULT 'sanctions',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (country_code, sanction_scope)
);

CREATE INDEX IF NOT EXISTS idx_sanctions_country
    ON energy.sanctions (country_code);
CREATE INDEX IF NOT EXISTS idx_sanctions_active
    ON energy.sanctions (is_active);

-- ============================================================
-- PORT CONGESTION
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.port_congestion (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    port_name       TEXT NOT NULL,
    country         TEXT NOT NULL,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    congestion_pct  DOUBLE PRECISION DEFAULT 0,
    waiting_vessels INTEGER DEFAULT 0,
    avg_wait_hours  DOUBLE PRECISION DEFAULT 0,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_port_congestion_country
    ON energy.port_congestion (country, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_port_congestion_pct
    ON energy.port_congestion (congestion_pct DESC);

-- ============================================================
-- TANKER AVAILABILITY
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.tanker_availability (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    vessel_type     TEXT NOT NULL,
    vessels_available INTEGER NOT NULL DEFAULT 0,
    total_vessels   INTEGER NOT NULL DEFAULT 0,
    avg_daily_rate_usd DOUBLE PRECISION DEFAULT 0,
    utilization_pct DOUBLE PRECISION DEFAULT 0,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tanker_availability_type
    ON energy.tanker_availability (vessel_type, recorded_at DESC);

-- ============================================================
-- SCENARIO ASSUMPTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS energy.scenario_assumptions (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    assumptions     JSONB DEFAULT '{}'::jsonb,
    risk_dimensions TEXT[] DEFAULT '{geopolitical,operational,economic,environmental}',
    created_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scenario_assumptions_name
    ON energy.scenario_assumptions (name);
CREATE INDEX IF NOT EXISTS idx_scenario_assumptions_created
    ON energy.scenario_assumptions (created_at DESC);
