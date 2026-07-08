from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FeatureDef(BaseModel):
    uuid: str | None = None
    name: str
    version: int = 1
    feature_type: str
    description: str | None = None
    transform_config: dict[str, Any] = {}
    source_feature: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


class FeatureDefCreate(BaseModel):
    name: str
    feature_type: str
    description: str | None = None
    transform_config: dict[str, Any] = {}
    source_feature: str | None = None


class DatasetMetadata(BaseModel):
    uuid: str | None = None
    name: str
    version: int = 1
    path: str
    total_records: int | None = None
    splits: dict[str, int] = {}
    target_column: str | None = None
    feature_versions: list[dict[str, int]] = []
    created_at: datetime | None = None


class DatasetBuildRequest(BaseModel):
    name: str = "energy_infrastructure"
    target_column: str = "criticality_score"
    feature_names: list[str] = []
    test_size: float = 0.2
    val_size: float = 0.1
    random_seed: int = 42


class DatasetBuildResponse(BaseModel):
    uuid: str
    name: str
    version: int
    path: str
    total_records: int
    splits: dict[str, int]
    target_column: str
    feature_count: int


class ModelVersion(BaseModel):
    uuid: str | None = None
    name: str
    version: int = 1
    model_type: str
    stage: str = "development"
    metrics: dict[str, float] = {}
    parameters: dict[str, Any] = {}
    feature_version: int | None = None
    dataset_version: int | None = None
    mlflow_run_id: str | None = None
    artifact_path: str | None = None
    file_path: str | None = None
    git_commit_hash: str | None = None
    execution_time_seconds: float | None = None
    training_date: datetime | None = None
    created_at: datetime | None = None


class ModelTransition(BaseModel):
    stage: str


class TrainingRequest(BaseModel):
    model_name: str = "energy_criticality_classifier"
    model_type: str = "xgboost"
    dataset_version: int = 1
    feature_version: int = 1
    parameters: dict[str, Any] = {}
    random_seed: int = 42


class TrainingResponse(BaseModel):
    model_version_uuid: str
    model_name: str
    model_version: int
    stage: str
    metrics: dict[str, float]
    mlflow_run_id: str
    execution_time_seconds: float


class PredictionRequest(BaseModel):
    features: dict[str, Any]
    model_name: str = "energy_criticality_classifier"
    model_version: int | None = None


class PredictionResponse(BaseModel):
    prediction: Any
    confidence: float
    probabilities: dict[str, float] | None = None
    model_name: str
    model_version: int
    model_stage: str
    feature_version: int | None = None
    prediction_timestamp: str
    latency_ms: float
    input_metadata: dict[str, Any] = {}


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


# ── Monitoring Models ──────────────────────────────────────────────

class DriftBaselineRequest(BaseModel):
    model_name: str
    model_version: int
    baseline_type: str = "feature"
    n_bins: int = 20


class DriftDetectionRequest(BaseModel):
    model_name: str
    model_version: int | None = None
    window_size: int = 1000
    threshold_psi: float = 0.2
    threshold_ks: float = 0.05


class DriftResultResponse(BaseModel):
    uuid: str | None = None
    model_name: str
    model_version: int
    feature_name: str | None = None
    drift_type: str
    drift_score: float
    threshold: float
    is_drift: bool
    window_size: int
    n_expected: int | None = None
    n_actual: int | None = None
    details: dict[str, Any] = {}
    detected_at: str | None = None


class FeatureServeRequest(BaseModel):
    entity_type: str = "port"
    entity_ids: list[str]
    feature_version: int | None = None


class FeatureServeResponse(BaseModel):
    features: dict[str, dict[str, Any]]
    feature_version: int
    from_cache: bool = False
    cache_hit_rate: float = 0.0


# ── Deployment / Research Pipeline Models ──────────────────────────

class ResearchExportConfig(BaseModel):
    model_name: str
    model_type: str
    experiment_id: str
    run_id: str
    parameters: dict[str, Any] = {}
    metrics: dict[str, float] = {}
    feature_version: int = 1
    dataset_version: int = 1
    tags: dict[str, str] = {}
    description: str | None = None


class ResearchImportRequest(BaseModel):
    export_path: str
    model_name: str | None = None
    stage: str = "development"


class ResearchImportResponse(BaseModel):
    model_version_uuid: str
    model_name: str
    model_version: int
    stage: str
    file_path: str


# ── Governance Models ──────────────────────────────────────────────

class GovernanceAction(BaseModel):
    action: str
    actor: str
    reason: str | None = None
    metadata: dict[str, Any] = {}


class ScheduleConfig(BaseModel):
    model_name: str
    cron_expression: str
    config: dict[str, Any] = {}
    is_active: bool = True


# ── Connector Models ──────────────────────────────────────────
class ConnectorConfigRequest(BaseModel):
    name: str
    connector_type: str  # rest_api, csv, excel, json, parquet, geojson, sql, postgresql, elasticsearch, kafka, s3, ftp, http_archive, zip, tar, gzip
    config: dict = {}
    auth_config: dict = {}
    rate_limit_config: dict = {}
    retry_config: dict = {}
    description: str = ""


class ConnectorFetchRequest(BaseModel):
    connector_name: str
    batch_size: int = 1000
    max_records: int | None = None
    start_position: str | None = None
    filters: dict = {}


class ConnectorSchemaResponse(BaseModel):
    columns: list[dict]
    connector_name: str
    schema_version: int
    row_estimate: int | None = None
    discovered_at: str | None = None


class ConnectorValidationResponse(BaseModel):
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    metadata: dict = {}


class ConnectorListResponse(BaseModel):
    items: list[dict]
    total: int


class ConnectorCheckpointResponse(BaseModel):
    connector_name: str
    checkpoint_key: str
    checkpoint_value: str | None
    row_count: int
    last_sync_at: str


# ── Ingestion Models ──────────────────────────────────────────
class IngestionPipelineCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[dict] = []
    connector_name: str | None = None
    schedule_expr: str | None = None
    is_scheduled: bool = False


class IngestionPipelineResponse(BaseModel):
    uuid: str
    name: str
    description: str
    steps: list[dict]
    connector_name: str | None
    schedule_expr: str | None
    is_scheduled: bool
    is_active: bool
    created_at: str


class IngestionJobResponse(BaseModel):
    uuid: str
    pipeline_name: str
    status: str
    started_at: str | None
    completed_at: str | None
    duration_seconds: float | None
    records_downloaded: int
    records_inserted: int
    records_failed: int
    error_count: int


class IngestionExecuteRequest(BaseModel):
    pipeline_name: str
    dry_run: bool = False
    params: dict = {}


# ── Normalization Models ──────────────────────────────────────
class NormalizationRuleCreate(BaseModel):
    name: str
    rule_type: str  # date, timestamp, currency, unit, country, org, entity_id, geospatial, categorical, missing, duplicate, schema_map, ontology_map, column_std
    description: str = ""
    source_pattern: str = ""
    target_format: str = ""
    config: dict = {}


class NormalizationApplyRequest(BaseModel):
    rules: list[str]  # rule names to apply
    dry_run: bool = False
    strict_mode: bool = False


class NormalizationResultResponse(BaseModel):
    rule_name: str
    records_affected: int
    duration_ms: float
    errors: int
    details: dict = {}


# ── Quality Models ────────────────────────────────────────────
class QualityScoreResponse(BaseModel):
    overall_score: float
    dimension_scores: dict[str, float]
    details: dict = {}


class QualityReportResponse(BaseModel):
    dataset_name: str
    dataset_version: int
    overall_score: float
    dimension_scores: dict[str, float]
    row_count: int
    column_count: int
    issues: list[dict]
    report_path: str | None
    created_at: str


class QualityDashboardResponse(BaseModel):
    metric_name: str
    metric_value: float
    dimension: str
    dataset_name: str | None
    snapshot_at: str


# ── Feature Pipeline Models ───────────────────────────────────
class FeaturePipelineDefinitionCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[dict] = []
    input_columns: list[str] = []
    output_columns: list[str] = []
    tags: list[str] = []


class FeaturePipelineRunResponse(BaseModel):
    pipeline_name: str
    pipeline_version: int
    status: str
    output_shape: list[int] | None
    cache_hits: int
    cache_misses: int
    duration_seconds: float
    snapshot_uuid: str | None
    error: str | None


# ── Explorer / Dashboard Models ───────────────────────────────
class SchemaTableResponse(BaseModel):
    table_name: str
    schema_name: str
    column_count: int
    row_estimate: int | None


class ModelDetailResponse(BaseModel):
    uuid: str
    name: str
    version: int
    model_type: str
    stage: str
    metrics: dict
    parameters: dict
    created_at: str
    dataset_name: str | None
    dataset_version: int | None


class ExplorerSearchRequest(BaseModel):
    query: str
    resource_type: str = "all"  # all, dataset, feature, model, experiment, pipeline
    limit: int = 20
    offset: int = 0


class ExplorerSearchResponse(BaseModel):
    items: list[dict]
    total: int
    resource_type: str
