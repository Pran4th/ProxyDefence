CREATE SCHEMA IF NOT EXISTS ml;

-- ENUM types
DO $$ BEGIN
    CREATE TYPE ml.feature_type AS ENUM (
        'numerical', 'categorical', 'boolean', 'timestamp',
        'geospatial', 'entity_statistics', 'relationship_statistics',
        'historical_capacity', 'infrastructure',
        'embedding_reference', 'graph_placeholder'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE ml.model_stage AS ENUM (
        'development', 'validation', 'staging', 'production', 'archived'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE ml.model_type AS ENUM (
        'logistic_regression', 'decision_tree', 'random_forest',
        'xgboost', 'lightgbm', 'catboost'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE ml.split_type AS ENUM ('train', 'validation', 'test');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Feature definitions (versioned)
CREATE TABLE IF NOT EXISTS ml.feature_definitions (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    feature_type ml.feature_type NOT NULL,
    description TEXT,
    transform_config JSONB DEFAULT '{}',
    source_feature TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Dataset metadata
CREATE TABLE IF NOT EXISTS ml.datasets (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    path TEXT NOT NULL,
    schema_json JSONB DEFAULT '{}',
    metadata_json JSONB DEFAULT '{}',
    feature_versions JSONB DEFAULT '[]',
    total_records INTEGER,
    train_records INTEGER,
    val_records INTEGER,
    test_records INTEGER,
    target_column TEXT,
    random_seed INTEGER,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Model versions (registry)
CREATE TABLE IF NOT EXISTS ml.model_versions (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    model_type ml.model_type NOT NULL,
    stage ml.model_stage NOT NULL DEFAULT 'development',
    metrics JSONB DEFAULT '{}',
    parameters JSONB DEFAULT '{}',
    feature_version INTEGER,
    dataset_version INTEGER,
    dataset_uuid UUID,
    experiment_id TEXT,
    mlflow_run_id TEXT,
    artifact_path TEXT,
    file_path TEXT,
    git_commit_hash TEXT,
    execution_time_seconds DOUBLE PRECISION,
    training_date TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Prediction audit log
CREATE TABLE IF NOT EXISTS ml.predictions (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    model_version_id BIGINT REFERENCES ml.model_versions(id),
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    input_data JSONB NOT NULL,
    prediction DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    probabilities JSONB,
    latency_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feature lineage tracking
CREATE TABLE IF NOT EXISTS ml.feature_lineage (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    feature_name TEXT NOT NULL,
    feature_version INTEGER NOT NULL,
    source_table TEXT,
    source_column TEXT,
    transform_type TEXT,
    transform_params JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Precomputed feature vectors for online serving
CREATE TABLE IF NOT EXISTS ml.feature_vectors (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    feature_version INTEGER NOT NULL,
    vector JSONB NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(entity_type, entity_id, feature_version)
);

-- Drift baselines (reference distributions per model/feature)
CREATE TABLE IF NOT EXISTS ml.drift_baselines (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    feature_name TEXT NOT NULL,
    baseline_type TEXT NOT NULL,
    distribution JSONB NOT NULL,
    n_samples INTEGER NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Drift detection results
CREATE TABLE IF NOT EXISTS ml.drift_results (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    feature_name TEXT,
    drift_type TEXT NOT NULL,
    drift_score DOUBLE PRECISION NOT NULL,
    threshold DOUBLE PRECISION NOT NULL,
    is_drift BOOLEAN NOT NULL,
    window_size INTEGER NOT NULL,
    n_expected INTEGER,
    n_actual INTEGER,
    details JSONB DEFAULT '{}',
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Model governance (approval/audit trail)
CREATE TABLE IF NOT EXISTS ml.model_governance (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    model_version_uuid UUID REFERENCES ml.model_versions(uuid),
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Training schedules
CREATE TABLE IF NOT EXISTS ml.training_schedules (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Dataset Infrastructure
-- ================================================================

-- Dataset catalog (master registry)
CREATE TABLE IF NOT EXISTS ml.dataset_catalog (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    dataset_type TEXT NOT NULL,
    description TEXT,
    category TEXT,
    tags TEXT[] DEFAULT '{}',
    owner TEXT DEFAULT 'system',
    source TEXT,
    documentation TEXT,
    license TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dataset lineage (DAG of parent/child)
CREATE TABLE IF NOT EXISTS ml.dataset_lineage (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL,
    parent_name TEXT,
    parent_version INTEGER,
    transform_type TEXT NOT NULL,
    transform_params JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dataset provenance (source tracking)
CREATE TABLE IF NOT EXISTS ml.dataset_provenance (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_version TEXT,
    source_url TEXT,
    access_method TEXT,
    access_params JSONB DEFAULT '{}',
    retrieval_timestamp TIMESTAMPTZ,
    checksum TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dataset statistics (per version)
CREATE TABLE IF NOT EXISTS ml.dataset_statistics (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL,
    row_count INTEGER NOT NULL,
    column_count INTEGER NOT NULL,
    memory_bytes BIGINT,
    size_bytes BIGINT,
    duplicate_count INTEGER DEFAULT 0,
    missing_cells INTEGER DEFAULT 0,
    total_cells INTEGER DEFAULT 0,
    duplicate_rate DOUBLE PRECISION DEFAULT 0.0,
    missing_rate DOUBLE PRECISION DEFAULT 0.0,
    numerical_columns INTEGER DEFAULT 0,
    categorical_columns INTEGER DEFAULT 0,
    boolean_columns INTEGER DEFAULT 0,
    datetime_columns INTEGER DEFAULT 0,
    text_columns INTEGER DEFAULT 0,
    stats_json JSONB DEFAULT '{}',
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dataset_name, dataset_version)
);

-- Dataset profiles (detailed per-column data)
CREATE TABLE IF NOT EXISTS ml.dataset_profiles (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL,
    column_name TEXT NOT NULL,
    dtype TEXT,
    missing_count INTEGER DEFAULT 0,
    missing_rate DOUBLE PRECISION DEFAULT 0.0,
    unique_count INTEGER DEFAULT 0,
    cardinality DOUBLE PRECISION DEFAULT 0.0,
    entropy DOUBLE PRECISION,
    samples JSONB DEFAULT '[]',
    profile_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dataset_name, dataset_version, column_name)
);

-- Dataset manifests (file integrity)
CREATE TABLE IF NOT EXISTS ml.dataset_manifests (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    sha256 TEXT,
    md5 TEXT,
    row_count INTEGER,
    column_count INTEGER,
    format TEXT,
    compression TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dataset_name, dataset_version, file_path)
);

-- Dataset validation results
CREATE TABLE IF NOT EXISTS ml.dataset_validations (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL,
    validation_type TEXT NOT NULL,
    status TEXT NOT NULL,
    score DOUBLE PRECISION,
    passed BOOLEAN NOT NULL,
    details JSONB DEFAULT '{}',
    executed_by TEXT DEFAULT 'system',
    executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dataset cards (documentation)
CREATE TABLE IF NOT EXISTS ml.dataset_cards (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL UNIQUE,
    title TEXT,
    summary TEXT,
    description TEXT,
    intended_uses TEXT,
    limitations TEXT,
    ethical_considerations TEXT,
    maintenance TEXT,
    authors JSONB DEFAULT '[]',
    references_json JSONB DEFAULT '[]',
    version INTEGER DEFAULT 1,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dataset dependencies
CREATE TABLE IF NOT EXISTS ml.dataset_dependencies (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL,
    dependency_name TEXT NOT NULL,
    dependency_version INTEGER,
    dependency_type TEXT NOT NULL,
    is_optional BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Feature Engineering Infrastructure
-- ================================================================

-- Feature groups
CREATE TABLE IF NOT EXISTS ml.feature_groups (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    group_type TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feature group membership
CREATE TABLE IF NOT EXISTS ml.feature_group_members (
    id BIGSERIAL PRIMARY KEY,
    group_uuid UUID REFERENCES ml.feature_groups(uuid) ON DELETE CASCADE,
    feature_uuid UUID REFERENCES ml.feature_definitions(uuid) ON DELETE CASCADE,
    feature_name TEXT NOT NULL,
    feature_version INTEGER NOT NULL,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_uuid, feature_uuid)
);

-- Transform registry
CREATE TABLE IF NOT EXISTS ml.transform_registry (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    transform_type TEXT NOT NULL,
    description TEXT,
    parameters_schema JSONB DEFAULT '{}',
    is_builtin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feature importance (per model per version)
CREATE TABLE IF NOT EXISTS ml.feature_importance (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    model_version_uuid UUID REFERENCES ml.model_versions(uuid),
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    feature_name TEXT NOT NULL,
    importance_score DOUBLE PRECISION NOT NULL,
    importance_type TEXT NOT NULL,
    rank INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feature snapshots (point-in-time feature values)
CREATE TABLE IF NOT EXISTS ml.feature_snapshots (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    feature_version INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    snapshot_data JSONB NOT NULL,
    snapshot_label TEXT,
    snapshot_type TEXT DEFAULT 'scheduled',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Research Framework
-- ================================================================

-- Research experiments
CREATE TABLE IF NOT EXISTS ml.experiments (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    experiment_type TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    author TEXT DEFAULT 'system',
    git_commit TEXT,
    random_seed INTEGER,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Experiment runs
CREATE TABLE IF NOT EXISTS ml.experiment_runs (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    experiment_uuid UUID REFERENCES ml.experiments(uuid),
    run_name TEXT NOT NULL,
    run_number INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    config JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    params JSONB DEFAULT '{}',
    model_version_uuid UUID REFERENCES ml.model_versions(uuid),
    dataset_version INTEGER,
    feature_version INTEGER,
    git_commit TEXT,
    random_seed INTEGER,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_seconds DOUBLE PRECISION,
    error_message TEXT,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(experiment_uuid, run_number)
);

-- Research configs (stored YAML/JSON configurations)
CREATE TABLE IF NOT EXISTS ml.research_configs (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    config_type TEXT NOT NULL,
    config_data JSONB NOT NULL,
    version INTEGER DEFAULT 1,
    description TEXT,
    tags TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Research artifacts
CREATE TABLE IF NOT EXISTS ml.research_artifacts (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    artifact_type TEXT NOT NULL,
    name TEXT NOT NULL,
    file_path TEXT,
    file_size BIGINT,
    mime_type TEXT,
    artifact_metadata JSONB DEFAULT '{}',
    experiment_uuid UUID REFERENCES ml.experiments(uuid),
    run_uuid UUID REFERENCES ml.experiment_runs(uuid),
    checksum TEXT,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Indexes
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_feature_active ON ml.feature_definitions(name, version);
CREATE INDEX IF NOT EXISTS idx_feature_type ON ml.feature_definitions(feature_type);
CREATE INDEX IF NOT EXISTS idx_dataset_name ON ml.datasets(name, version);
CREATE INDEX IF NOT EXISTS idx_model_name ON ml.model_versions(name, version);
CREATE INDEX IF NOT EXISTS idx_model_stage ON ml.model_versions(name, stage)
    WHERE stage = 'production';
CREATE INDEX IF NOT EXISTS idx_model_mlflow ON ml.model_versions(mlflow_run_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON ml.predictions(model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON ml.predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feature_vectors_lookup ON ml.feature_vectors(entity_type, entity_id, feature_version);
CREATE INDEX IF NOT EXISTS idx_drift_results_model ON ml.drift_results(model_name, model_version, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_drift_baselines_model ON ml.drift_baselines(model_name, model_version, feature_name);
CREATE INDEX IF NOT EXISTS idx_governance_model ON ml.model_governance(model_version_uuid, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dataset_catalog_type ON ml.dataset_catalog(dataset_type);
CREATE INDEX IF NOT EXISTS idx_dataset_catalog_tags ON ml.dataset_catalog USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_dataset_lineage_parent ON ml.dataset_lineage(parent_name, parent_version);
CREATE INDEX IF NOT EXISTS idx_dataset_lineage_child ON ml.dataset_lineage(dataset_name, dataset_version);
CREATE INDEX IF NOT EXISTS idx_dataset_provenance_source ON ml.dataset_provenance(source_name);
CREATE INDEX IF NOT EXISTS idx_dataset_statistics_name ON ml.dataset_statistics(dataset_name, dataset_version);
CREATE INDEX IF NOT EXISTS idx_dataset_profiles_name ON ml.dataset_profiles(dataset_name, dataset_version);
CREATE INDEX IF NOT EXISTS idx_dataset_manifests_name ON ml.dataset_manifests(dataset_name, dataset_version);
CREATE INDEX IF NOT EXISTS idx_dataset_validations_name ON ml.dataset_validations(dataset_name, dataset_version);
CREATE INDEX IF NOT EXISTS idx_feature_groups_active ON ml.feature_groups(name);
CREATE INDEX IF NOT EXISTS idx_feature_group_members_group ON ml.feature_group_members(group_uuid);
CREATE INDEX IF NOT EXISTS idx_feature_importance_model ON ml.feature_importance(model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_experiments_name ON ml.experiments(name);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_experiment ON ml.experiment_runs(experiment_uuid);
CREATE INDEX IF NOT EXISTS idx_research_configs_type ON ml.research_configs(config_type);
CREATE INDEX IF NOT EXISTS idx_research_artifacts_experiment ON ml.research_artifacts(experiment_uuid);
CREATE INDEX IF NOT EXISTS idx_research_artifacts_type ON ml.research_artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_dataset_dependencies_name ON ml.dataset_dependencies(dataset_name, dataset_version);
CREATE INDEX IF NOT EXISTS idx_transform_registry_type ON ml.transform_registry(transform_type);
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_entity ON ml.feature_snapshots(entity_type, entity_id);

-- ================================================================
-- Connector Definitions
-- ================================================================

-- Connector definitions (source system registry)
CREATE TABLE IF NOT EXISTS ml.connector_definitions (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    connector_type TEXT NOT NULL,
    description TEXT,
    config_schema JSONB DEFAULT '{}',
    auth_type TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    max_connections INTEGER DEFAULT 5,
    timeout_seconds INTEGER DEFAULT 30,
    retry_count INTEGER DEFAULT 3,
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Connector schema registry (expected data structures per connector)
CREATE TABLE IF NOT EXISTS ml.connector_schemas (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    connector_name TEXT NOT NULL,
    connector_version INTEGER NOT NULL DEFAULT 1,
    schema_name TEXT NOT NULL,
    schema_type TEXT NOT NULL,
    fields_json JSONB DEFAULT '[]',
    required_fields JSONB DEFAULT '[]',
    nullable_fields JSONB DEFAULT '[]',
    primary_key_fields JSONB DEFAULT '[]',
    validation_rules JSONB DEFAULT '{}',
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connector_name, schema_name)
);

-- Connector checkpoint tracking (incremental ingestion state)
CREATE TABLE IF NOT EXISTS ml.connector_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    connector_name TEXT NOT NULL,
    connector_version INTEGER NOT NULL DEFAULT 1,
    checkpoint_key TEXT NOT NULL,
    checkpoint_value TEXT,
    checkpoint_type TEXT DEFAULT 'cursor',
    snapshot JSONB DEFAULT '{}',
    last_sequence TEXT,
    last_modified TIMESTAMPTZ,
    record_count INTEGER DEFAULT 0,
    is_complete BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connector_name, connector_version, checkpoint_key)
);

-- ================================================================
-- Ingestion Pipeline Tables
-- ================================================================

-- Ingestion pipeline definitions
CREATE TABLE IF NOT EXISTS ml.ingestion_pipelines (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    connector_name TEXT NOT NULL,
    pipeline_type TEXT NOT NULL,
    schedule_cron TEXT,
    batch_size INTEGER DEFAULT 1000,
    max_retries INTEGER DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 60,
    transform_pipeline JSONB DEFAULT '[]',
    filter_rules JSONB DEFAULT '{}',
    target_dataset TEXT,
    target_table TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Ingestion job runs
CREATE TABLE IF NOT EXISTS ml.ingestion_jobs (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    pipeline_name TEXT NOT NULL,
    pipeline_version INTEGER NOT NULL DEFAULT 1,
    job_status TEXT NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    total_records INTEGER DEFAULT 0,
    processed_records INTEGER DEFAULT 0,
    failed_records INTEGER DEFAULT 0,
    skipped_records INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    duration_seconds DOUBLE PRECISION,
    trigger_type TEXT DEFAULT 'manual',
    worker_id TEXT,
    config_override JSONB DEFAULT '{}',
    results JSONB DEFAULT '{}',
    error_message TEXT,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ingestion error log
CREATE TABLE IF NOT EXISTS ml.ingestion_errors (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    pipeline_name TEXT NOT NULL,
    pipeline_version INTEGER NOT NULL DEFAULT 1,
    job_uuid UUID,
    error_type TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT NOT NULL,
    error_detail TEXT,
    source_record JSONB DEFAULT '{}',
    raw_payload TEXT,
    retry_count INTEGER DEFAULT 0,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Normalization Tables
-- ================================================================

-- Normalization rules (transform configurations)
CREATE TABLE IF NOT EXISTS ml.normalization_rules (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    rule_type TEXT NOT NULL,
    source_field TEXT NOT NULL,
    target_field TEXT NOT NULL,
    transform_function TEXT,
    transform_params JSONB DEFAULT '{}',
    data_type TEXT,
    default_value TEXT,
    validation_pattern TEXT,
    null_handling TEXT DEFAULT 'skip',
    error_handling TEXT DEFAULT 'fail',
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Normalization value mappings (source-to-target value maps)
CREATE TABLE IF NOT EXISTS ml.normalization_mappings (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    rule_name TEXT NOT NULL,
    rule_version INTEGER NOT NULL DEFAULT 1,
    source_value TEXT NOT NULL,
    target_value TEXT NOT NULL,
    mapping_type TEXT DEFAULT 'exact',
    confidence DOUBLE PRECISION DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(rule_name, rule_version, source_value)
);

-- ================================================================
-- Quality Framework Tables
-- ================================================================

-- Quality reports (data quality check results)
CREATE TABLE IF NOT EXISTS ml.quality_reports (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    report_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    dataset_version INTEGER NOT NULL DEFAULT 1,
    report_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    overall_score DOUBLE PRECISION,
    completeness_score DOUBLE PRECISION,
    accuracy_score DOUBLE PRECISION,
    consistency_score DOUBLE PRECISION,
    timeliness_score DOUBLE PRECISION,
    uniqueness_score DOUBLE PRECISION,
    validity_score DOUBLE PRECISION,
    total_checks INTEGER DEFAULT 0,
    passed_checks INTEGER DEFAULT 0,
    failed_checks INTEGER DEFAULT 0,
    warning_checks INTEGER DEFAULT 0,
    threshold_warning DOUBLE PRECISION DEFAULT 0.95,
    threshold_failure DOUBLE PRECISION DEFAULT 0.90,
    checks_json JSONB DEFAULT '[]',
    dimensions JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    executed_by TEXT DEFAULT 'system',
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quality dashboard snapshots (aggregated trends)
CREATE TABLE IF NOT EXISTS ml.quality_dashboard (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    dashboard_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    overall_score DOUBLE PRECISION,
    completeness_score DOUBLE PRECISION,
    accuracy_score DOUBLE PRECISION,
    consistency_score DOUBLE PRECISION,
    timeliness_score DOUBLE PRECISION,
    uniqueness_score DOUBLE PRECISION,
    validity_score DOUBLE PRECISION,
    row_count INTEGER,
    column_count INTEGER,
    trend_direction TEXT,
    score_delta DOUBLE PRECISION,
    alerts_count INTEGER DEFAULT 0,
    critical_alerts INTEGER DEFAULT 0,
    snapshot_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dashboard_name, dataset_name, snapshot_date)
);

-- ================================================================
-- Feature Pipeline Tables
-- ================================================================

-- Feature pipeline definitions
CREATE TABLE IF NOT EXISTS ml.feature_pipelines (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    pipeline_type TEXT NOT NULL,
    source_datasets JSONB DEFAULT '[]',
    target_feature_group TEXT,
    transform_steps JSONB DEFAULT '[]',
    aggregation_config JSONB DEFAULT '{}',
    window_config JSONB DEFAULT '{}',
    schedule_cron TEXT,
    parallelism INTEGER DEFAULT 1,
    max_retries INTEGER DEFAULT 3,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Feature pipeline execution runs
CREATE TABLE IF NOT EXISTS ml.feature_pipeline_runs (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    pipeline_name TEXT NOT NULL,
    pipeline_version INTEGER NOT NULL DEFAULT 1,
    run_status TEXT NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds DOUBLE PRECISION,
    input_records INTEGER DEFAULT 0,
    output_records INTEGER DEFAULT 0,
    dropped_records INTEGER DEFAULT 0,
    features_generated INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    trigger_type TEXT DEFAULT 'manual',
    worker_id TEXT,
    config_override JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    error_message TEXT,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- New Indexes
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_connector_definitions_name ON ml.connector_definitions(name, version);
CREATE INDEX IF NOT EXISTS idx_connector_definitions_type ON ml.connector_definitions(connector_type);
CREATE INDEX IF NOT EXISTS idx_connector_schemas_connector ON ml.connector_schemas(connector_name, schema_name);
CREATE INDEX IF NOT EXISTS idx_connector_checkpoints_lookup ON ml.connector_checkpoints(connector_name, connector_version);
CREATE INDEX IF NOT EXISTS idx_connector_checkpoints_key ON ml.connector_checkpoints(checkpoint_key);
CREATE INDEX IF NOT EXISTS idx_ingestion_pipelines_name ON ml.ingestion_pipelines(name, version);
CREATE INDEX IF NOT EXISTS idx_ingestion_pipelines_connector ON ml.ingestion_pipelines(connector_name);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_pipeline ON ml.ingestion_jobs(pipeline_name, pipeline_version);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ml.ingestion_jobs(job_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_trigger ON ml.ingestion_jobs(trigger_type);
CREATE INDEX IF NOT EXISTS idx_ingestion_errors_pipeline ON ml.ingestion_errors(pipeline_name, pipeline_version);
CREATE INDEX IF NOT EXISTS idx_ingestion_errors_type ON ml.ingestion_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_ingestion_errors_unresolved ON ml.ingestion_errors(is_resolved, created_at DESC)
    WHERE is_resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_normalization_rules_name ON ml.normalization_rules(name, version);
CREATE INDEX IF NOT EXISTS idx_normalization_rules_type ON ml.normalization_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_normalization_rules_target ON ml.normalization_rules(source_field, target_field);
CREATE INDEX IF NOT EXISTS idx_normalization_mappings_rule ON ml.normalization_mappings(rule_name, rule_version);
CREATE INDEX IF NOT EXISTS idx_normalization_mappings_value ON ml.normalization_mappings(source_value, target_value);
CREATE INDEX IF NOT EXISTS idx_quality_reports_dataset ON ml.quality_reports(dataset_name, dataset_version);
CREATE INDEX IF NOT EXISTS idx_quality_reports_type ON ml.quality_reports(report_type, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_quality_reports_score ON ml.quality_reports(overall_score DESC)
    WHERE overall_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quality_dashboard_dataset ON ml.quality_dashboard(dashboard_name, dataset_name);
CREATE INDEX IF NOT EXISTS idx_quality_dashboard_date ON ml.quality_dashboard(snapshot_date DESC, dataset_name);
CREATE INDEX IF NOT EXISTS idx_feature_pipelines_name ON ml.feature_pipelines(name, version);
CREATE INDEX IF NOT EXISTS idx_feature_pipelines_group ON ml.feature_pipelines(target_feature_group);
CREATE INDEX IF NOT EXISTS idx_feature_pipeline_runs_pipeline ON ml.feature_pipeline_runs(pipeline_name, pipeline_version);
CREATE INDEX IF NOT EXISTS idx_feature_pipeline_runs_status ON ml.feature_pipeline_runs(run_status, started_at DESC);
