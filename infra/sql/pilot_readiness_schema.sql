-- Pilot-readiness extensions.
-- These tables make every operational recommendation reproducible and honest
-- about whether its inputs were live, cached, replayed, or fallback values.

CREATE SCHEMA IF NOT EXISTS energy;

CREATE TABLE IF NOT EXISTS energy.intelligence_source_status (
    id              BIGSERIAL PRIMARY KEY,
    source_key      TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    mode            TEXT NOT NULL CHECK (mode IN ('live', 'cached', 'replay', 'fallback', 'disabled')),
    observed_at     TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    freshness_seconds DOUBLE PRECISION,
    fallback_reason TEXT,
    source_url      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS energy.response_evidence_bundles (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    telemetry_uuid  UUID NOT NULL UNIQUE REFERENCES energy.response_telemetry(uuid) ON DELETE CASCADE,
    signal_uuid     UUID NOT NULL REFERENCES energy.disruption_signals(uuid),
    scenario_uuid   UUID,
    twin_run_uuid   UUID,
    spr_run_uuid    UUID,
    procurement_run_uuid UUID,
    mode            TEXT NOT NULL CHECK (mode IN ('live', 'cached', 'replay', 'fallback')),
    assumptions     JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_provenance JSONB NOT NULL DEFAULT '[]'::jsonb,
    decision_brief  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_signal ON energy.response_evidence_bundles(signal_uuid, created_at DESC);

CREATE TABLE IF NOT EXISTS energy.decision_approvals (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    evidence_bundle_uuid UUID NOT NULL REFERENCES energy.response_evidence_bundles(uuid) ON DELETE CASCADE,
    status          TEXT NOT NULL CHECK (status IN ('draft', 'reviewed', 'approved', 'executed', 'outcome_recorded')),
    actor           TEXT NOT NULL,
    note            TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_approvals_bundle ON energy.decision_approvals(evidence_bundle_uuid, recorded_at);

CREATE TABLE IF NOT EXISTS energy.historical_replay_runs (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    case_key        TEXT NOT NULL,
    case_name       TEXT NOT NULL,
    source_window   JSONB NOT NULL,
    expected_effects JSONB NOT NULL DEFAULT '{}'::jsonb,
    measured_results JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_bundle_uuid UUID REFERENCES energy.response_evidence_bundles(uuid),
    status          TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'completed', 'failed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_historical_replays_case ON energy.historical_replay_runs(case_key, created_at DESC);
