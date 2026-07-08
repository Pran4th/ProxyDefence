# Research Infrastructure

## Overview

The Research Infrastructure bridges the gap between experimental data science and production ML. It provides a structured environment for configuring experiments, exploring datasets and features, running training iterations, exporting models, and importing them into the production ML Platform.

Research runs **outside Docker** — notebooks execute locally, models are exported as artifacts, and the production platform consumes only the finalized exports. This strict separation ensures that experimental code, visualizations, and heavy dependencies never enter the production Docker image.

## End-to-End Workflow

```
  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐
  │ Configure  │──▶│  Explore  │──▶│ Experiment│──▶│  Export   │──▶│  Import   │──▶│  Deploy   │
  │            │   │           │   │           │   │           │   │           │   │           │
  └───────────┘   └───────────┘   └───────────┘   └───────────┘   └───────────┘   └───────────┘
       │               │               │               │               │               │
       ▼               ▼               ▼               ▼               ▼               ▼
  YAML Config     Catalog +        Notebooks        joblib +         Platform        Production
  (experiment,    Stats +          01 → 08          config.json     Importer        Inference
   dataset,       Feature          (EDA → Export)   + README.md     API             API
   model)         Profiles                                                          (port 8007)
```

## Research Config

Experiments are defined declaratively in YAML/JSON configuration files stored in `research/configs/`.

### Structure

```yaml
experiment:
  name: disruption_risk_classifier
  type: classification
  description: Predict energy infrastructure disruption risk level
  author: system
  random_seed: 42
  tags:
    - energy
    - disruption
    - risk

dataset:
  name: energy_infrastructure_incidents
  version: 1
  target_column: risk_level
  test_size: 0.2
  val_size: 0.1
  feature_names:
    - asset_age_years
    - maintenance_score
    - geopolitical_risk_index
    - incident_count_90d
    - region_tension_score

model:
  type: xgboost
  parameters:
    n_estimators: 200
    max_depth: 8
    learning_rate: 0.05
    subsample: 0.8
  evaluation:
    metrics: [accuracy, f1, precision, recall, roc_auc]
    cross_validation:
      folds: 5
      stratify: true

export:
  format: joblib
  register: true
  stage: development
```

### Existing Configs

| Config File | Type | Description |
|-------------|------|-------------|
| `disruption_risk_classifier.yaml` | classification | Infrastructure disruption risk prediction |
| `commodity_forecaster.yaml` | regression | Commodity price trend forecasting |
| `anomaly_detection_infrastructure.yaml` | anomaly_detection | Infrastructure telemetry anomaly detection |

The `ResearchConfigLoader` manages config loading, validation, and persistence:

```python
loader = ResearchConfigLoader("research/configs")
config = loader.load("disruption_risk_classifier.yaml")
# Validates required fields: experiment.name, experiment.type
```

Config API endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/ml/research/configs` | List all configs |
| `GET /api/v1/ml/research/configs/{name}` | Get config details |
| `POST /api/v1/ml/research/configs` | Save new config |
| `PUT /api/v1/ml/research/configs/{name}` | Update existing config |

## Dataset Explorer

### Catalog Search

Search across all registered datasets in `ml.dataset_catalog`:

```bash
# Search by keyword
GET /api/v1/ml/datasets/catalog/search?q=energy

# Filter by type
GET /api/v1/ml/datasets/catalog/search?dataset_type=energy_infrastructure

# Filter by tag
GET /api/v1/ml/datasets/catalog/search?tag=critical
```

### Metadata

Retrieve dataset metadata including versions, splits, and target column:

```bash
GET /api/v1/ml/datasets/energy_infrastructure/versions
```

Response includes per-version information: `uuid`, `name`, `version`, `total_records`, `train_records`, `val_records`, `test_records`, `target_column`, `random_seed`, `created_at`.

### Statistics

Statistical summary per dataset version:

```bash
GET /api/v1/ml/datasets/energy_infrastructure/v3/stats
```

Returns: row count, column count, memory size, duplicate rates, missing rates, column type counts, and per-column descriptive statistics (mean, std, percentiles for numerics; top values, entropy for categoricals).

### Profiles

Per-column detailed profiles:

```bash
GET /api/v1/ml/datasets/energy_infrastructure/v3/profile
```

Returns for each column: dtype, missing count/rate, unique count, cardinality, numeric statistics (min, max, mean, std, skew, kurtosis, percentiles, IQR), categorical statistics (top values, entropy, length distribution), datetime range, and samples.

### Validation History

```bash
GET /api/v1/ml/datasets/energy_infrastructure/v3/validation
```

Returns all validation checks executed on the dataset version with status, score, and details.

## Feature Explorer

### Available Features

List all registered feature definitions:

```bash
GET /api/v1/ml/features?feature_type=numerical
```

Supported types: `numerical`, `categorical`, `boolean`, `timestamp`, `geospatial`, `entity_statistics`, `relationship_statistics`, `historical_capacity`, `infrastructure`, `embedding_reference`, `graph_placeholder`.

### Feature Transforms

18 built-in transforms are available, registered in `TRANSFORM_REGISTRY`:

| Transform | Purpose |
|-----------|---------|
| `identity` | Pass-through column |
| `standard_scale` | Z-score normalization |
| `minmax` | Min-max scaling to [0,1] |
| `robust_scale` | IQR-based robust scaling |
| `one_hot` | One-hot encoding |
| `label_encode` | Label encoding |
| `frequency_encode` | Frequency ratio encoding |
| `binary_encode` | Threshold-based binary |
| `temporal` | Date/time component extraction |
| `rolling_window` | Rolling window aggregation |
| `ewma` | Exponentially weighted MA |
| `lag` | Lagged value feature |
| `ratio` | Feature ratio computation |
| `interaction` | Feature interaction |
| `polynomial` | Polynomial expansion |
| `target_encode` | Target mean encoding |
| `aggregate` | Group-by aggregation |
| `geospatial` | Haversine distance to chokepoints |

```bash
GET /api/v1/ml/features/transforms
GET /api/v1/ml/features/transforms/{name}
```

### Feature Groups

Organize features into logical groups:

```bash
GET /api/v1/ml/features/groups
GET /api/v1/ml/features/groups/port_capacity
```

Groups include metadata, group type, and member features with priority ordering.

### Feature Importance

Retrieve computed feature importance for trained models:

```bash
GET /api/v1/ml/features/importance?model_name=energy_criticality_classifier&model_version=3
```

Supports two importance types: `tree_based` (native model importance) and `permutation` (permutation importance with `n_repeats=5`).

## Experiment Manager

### Creation

```bash
POST /api/v1/ml/research/experiments
{
  "name": "xgboost_energy_risk_v3",
  "experiment_type": "classification",
  "description": "XGBoost with tuned hyperparameters for energy risk",
  "tags": ["energy", "xgboost", "tuning"]
}
```

Each experiment is created with an auto-detected Git commit hash for reproducibility.

### Runs

```bash
POST /api/v1/ml/research/experiments/{uuid}/runs
{
  "run_name": "lr_baseline_v3",
  "config": { "learning_rate": 0.05, "max_depth": 8 }
}
```

Runs are auto-numbered within each experiment. Run lifecycle: `pending` → `running` → `completed` / `failed`.

### Comparison

```bash
POST /api/v1/ml/research/experiments/runs/compare
{
  "run_uuids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

Returns a side-by-side comparison of metrics, parameters, duration, and status across selected runs.

### Tagging

Experiments and runs support arbitrary tags for filtering and organization:

```python
# Tags at experiment creation
tags = ["energy", "xgboost", "tuning", "q1_2026"]

# Tags are filterable
GET /api/v1/ml/research/experiments?tag=energy
```

### Git Integration

Every experiment and run records its Git commit hash:

```python
def _get_git_commit(self) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None
```

This enables full reproducibility — any experiment can be recreated by checking out the recorded commit.

## Artifact Manager

### Storage

Artifacts are stored in `data/artifacts/` with versioned paths:

```
data/artifacts/
├── energy_criticality_classifier/
│   ├── v1/
│   │   └── model.joblib
│   └── v3/
│       └── model.joblib
├── imported/
│   └── disruption_risk_classifier/
│       └── v_model.joblib
└── research_exports/
    └── disruption_risk_classifier_run_abc_20260706_120000/
        ├── model.joblib
        ├── config.json
        └── README.md
```

### Retrieval

```bash
GET /api/v1/ml/artifacts?experiment_uuid=...&run_uuid=...
```

### Checksums

Every artifact stored in `ml.research_artifacts` includes:

| Field | Description |
|-------|-------------|
| `file_path` | Full path to artifact file |
| `file_size` | Size in bytes |
| `mime_type` | MIME type (application/octet-stream for joblib) |
| `checksum` | SHA-256 content hash |

### MIME Types

| Artifact Type | MIME Type | Extension |
|---------------|-----------|-----------|
| Model (joblib) | `application/octet-stream` | `.joblib` |
| Configuration | `application/json` | `.json` |
| Configuration | `application/x-yaml` | `.yaml` |
| Dataset | `application/x-parquet` | `.parquet` |
| Report | `application/json` | `.json` |
| Notebook | `application/x-ipynb` | `.ipynb` |

## Research-to-Platform Pipeline

### Config-Driven Export

The `ResearchExporter` packages trained models with their configuration for production consumption:

```python
exporter = ResearchExporter()
export_path = exporter.export(
    model=trained_model,
    config=ResearchConfig("research/configs/disruption_risk_classifier.yaml"),
)
```

Export produces:
- `model.joblib` — serialized model
- `config.json` — full experiment configuration
- `README.md` — auto-generated model card

### Platform-Side Import

The `PlatformImporter` ingests exported models into the production model registry:

```bash
POST /api/v1/ml/research/import
{
  "export_path": "data/artifacts/research_exports/disruption_risk_classifier_run_abc_20260706_120000",
  "model_name": "disruption_risk_classifier",
  "stage": "development"
}
```

Import process:
1. Validate export directory structure (config.json + model.joblib)
2. Copy model to `data/artifacts/imported/{model_name}/`
3. Register in `ml.model_versions` via `ModelRegistry.register()`
4. Optionally transition to specified stage

### Validation During Import

```python
class PlatformImporter:
    async def import_export(self, export_path: str, model_name: str | None = None,
                            stage: str = "development") -> dict[str, Any] | None:
        # 1. Verify export directory exists
        # 2. Load and validate config.json
        # 3. Verify model.joblib exists
        # 4. Copy model to artifacts directory
        # 5. Register in model registry
        # 6. Apply stage transition if specified
```

## Pipeline DAGs

The research infrastructure leverages the same `PipelineDAG` engine used by the ingestion pipeline for reproducible research workflows:

```python
from pipeline.dag import PipelineDAG, PipelineStep

research_pipeline = PipelineDAG(name="feature_importance_analysis")
research_pipeline.add_step(PipelineStep(
    name="load_data",
    func=load_training_data,
    outputs=["X_train", "y_train", "feature_names"],
))
research_pipeline.add_step(PipelineStep(
    name="train_model",
    func=train_random_forest,
    inputs=["X_train", "y_train"],
    outputs=["model"],
    dependencies=["load_data"],
))
research_pipeline.add_step(PipelineStep(
    name="compute_importance",
    func=compute_permutation_importance,
    inputs=["model", "X_train", "y_train", "feature_names"],
    outputs=["importance_scores"],
    dependencies=["train_model"],
))
```

### Caching

The `PipelineCache` provides two-tier caching (memory + disk via Parquet) to avoid recomputing expensive steps:

```python
cache = PipelineCache()
if cache.exists("train_model", params={"n_estimators": 200}):
    model = cache.get("train_model")
else:
    model = train_model(X_train, y_train)
    cache.set("train_model", model)
```

## Quality Framework Integration

Research experiments consume quality metrics from `ml.quality_reports` and `ml.quality_dashboard`:

```bash
# Check dataset quality before starting experiment
GET /api/v1/ml/quality/report?dataset=energy_infrastructure&version=3

# Incorporate quality scores into experiment metadata
POST /api/v1/ml/research/experiments
{
  "name": "energy_risk_v3",
  "metadata": {
    "dataset_quality_score": 0.94,
    "dataset_version": 3
  }
}
```

Quality gates prevent experiments from using low-quality datasets:

```python
async def check_quality_gate(dataset_name: str, version: int, min_score: float = 0.85):
    report = await DatasetStatistics.get_health_score(dataset_name, version)
    if report["score"] < min_score:
        raise QualityGateError(
            f"Dataset {dataset_name} v{version} score {report['score']} < {min_score}"
        )
```

## Connector Framework for Future Data Sources

Research can consume data from any registered connector via the `IngestionPipeline`:

```bash
# Trigger connector fetch for research
POST /api/v1/ml/connectors/fetch
{
  "connector_type": "eia",
  "config": { "api_key": "***", "endpoint": "petroleum/crude" }
}
```

Future connectors planned for research consumption:

| Source | Use Case | Connector Type |
|--------|----------|----------------|
| GDELT | Geopolitical event features | `gdelt` |
| ACLED | Conflict zone risk scoring | `acled` |
| ICEWS | Political stability indicators | `icews` |
| EIA | Energy price & supply data | `eia` |
| FRED | Macro-economic indicators | `fred` |
| AIS | Maritime chokepoint congestion | `ais` |

## API Reference

### Dataset Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ml/datasets` | List all datasets |
| `GET /api/v1/ml/datasets/{name}` | Get dataset metadata |
| `GET /api/v1/ml/datasets/{name}/versions` | List all versions |
| `GET /api/v1/ml/datasets/{name}/v{version}` | Get version metadata |
| `POST /api/v1/ml/datasets/build` | Build a new dataset |
| `POST /api/v1/ml/datasets/{name}/v{version}/validate` | Run validation |
| `GET /api/v1/ml/datasets/{name}/v{version}/validation` | Get validation history |
| `GET /api/v1/ml/datasets/{name}/v{version}/stats` | Get statistics |
| `GET /api/v1/ml/datasets/{name}/v{version}/profile` | Get column profiles |
| `GET /api/v1/ml/datasets/{name}/v{version}/manifest` | Get file manifest |
| `GET /api/v1/ml/datasets/{name}/v{version}/manifest/verify` | Verify manifest |
| `GET /api/v1/ml/datasets/{name}/v{version}/lineage` | Get lineage graph |
| `GET /api/v1/ml/datasets/{name}/v{version}/provenance` | Get provenance |
| `GET /api/v1/ml/datasets/catalog/search` | Search catalog |
| `POST /api/v1/ml/datasets/catalog` | Register in catalog |
| `POST /api/v1/ml/datasets/{name}/card` | Create/update dataset card |

### Feature Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ml/features` | List feature definitions |
| `POST /api/v1/ml/features` | Create feature definition |
| `GET /api/v1/ml/features/{uuid}` | Get feature definition |
| `GET /api/v1/ml/features/transforms` | List available transforms |
| `GET /api/v1/ml/features/groups` | List feature groups |
| `POST /api/v1/ml/features/groups` | Create feature group |
| `GET /api/v1/ml/features/groups/{name}` | Get group with members |
| `GET /api/v1/ml/features/importance` | Get feature importance |
| `POST /api/v1/ml/features/serve` | Compute features for entities |

### Model Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ml/models` | List model versions |
| `GET /api/v1/ml/models/{name}` | Get model version details |
| `POST /api/v1/ml/models/train` | Train a new model |
| `POST /api/v1/ml/models/{uuid}/transition` | Transition model stage |
| `POST /api/v1/ml/models/predict` | Run inference |
| `POST /api/v1/ml/models/schedules` | Create training schedule |
| `GET /api/v1/ml/models/schedules` | List schedules |

### Research Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ml/research/experiments` | List experiments |
| `POST /api/v1/ml/research/experiments` | Create experiment |
| `GET /api/v1/ml/research/experiments/{uuid}` | Get experiment |
| `POST /api/v1/ml/research/experiments/{uuid}/runs` | Start a run |
| `PUT /api/v1/ml/research/experiments/runs/{uuid}` | Finish a run |
| `POST /api/v1/ml/research/experiments/runs/compare` | Compare runs |
| `GET /api/v1/ml/research/configs` | List research configs |
| `POST /api/v1/ml/research/configs` | Save research config |
| `POST /api/v1/ml/research/export` | Export model to file |
| `POST /api/v1/ml/research/import` | Import model to registry |

### Monitoring Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ml/monitor/predictions` | Recent predictions |
| `POST /api/v1/ml/monitor/baseline` | Compute drift baseline |
| `POST /api/v1/ml/monitor/drift` | Detect drift |
| `GET /api/v1/ml/monitor/drift/summary` | Drift summary |

### Quality Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ml/quality/report` | Latest quality report |
| `GET /api/v1/ml/quality/dashboard` | Dashboard trends |
| `POST /api/v1/ml/quality/check` | Run ad-hoc quality check |
| `GET /api/v1/ml/quality/compare` | Compare versions |

### Pipeline Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/ml/pipelines/run` | Execute a pipeline |
| `GET /api/v1/ml/pipelines` | List registered pipelines |
| `GET /api/v1/ml/pipelines/history` | Pipeline execution history |
| `POST /api/v1/ml/pipelines/export` | Export pipeline definition |

### Governance Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/ml/governance/{model_uuid}/audit` | Record governance action |
| `GET /api/v1/ml/governance/{model_uuid}/history` | Governance audit trail |

## Future Integration Points

### Risk Engine

The Risk Engine (planned) will consume:
- Model predictions from `ml.predictions`
- Feature importance scores from `ml.feature_importance`
- Drift detection results from `ml.drift_results`
- Dataset quality scores from `ml.quality_reports`

Research will provide risk models exported via the standard `research_exporter` → `platform_importer` pipeline.

### Copilot

The AI Copilot (planned) will consume:
- Dataset cards from `ml.dataset_cards`
- Experiment metadata from `ml.experiments`
- Feature definitions from `ml.feature_definitions`
- Research configs from `ml.research_configs`

All metadata is accessible via the existing API endpoints.

### Digital Twin

The Digital Twin (planned) will consume:
- Materialized feature vectors from `ml.feature_vectors`
- Feature snapshots from `ml.feature_snapshots`
- Entity relationships from the Energy Service

Research will provide simulation and forecasting models exported via the same pipeline.

## Notebook Reference

| # | Notebook | Key Concepts | Production Mapping |
|---|----------|-------------|-------------------|
| 01 | `01_eda.ipynb` | Distributions, correlations, target analysis | `DatasetProfiler`, `DatasetStatistics` |
| 02 | `02_preprocessing.ipynb` | Missing values, outliers, data types | `DatasetValidationPipeline`, normalization rules |
| 03 | `03_feature_engineering.ipynb` | Encoding, scaling, aggregation, selection | `FeatureTransform` registry |
| 04 | `04_baseline_models.ipynb` | LogisticRegression, DecisionTree | `ModelRegistry` wrappers |
| 05 | `05_model_comparison.ipynb` | RF, XGBoost, LightGBM, cross-validation | `MODEL_REGISTRY`, `trainer.py` |
| 06 | `06_hyperparameter_tuning.ipynb` | Grid/Random search, Optuna | `GridSearchOptimizer`, `OptunaOptimizer` |
| 07 | `07_explainability.ipynb` | SHAP, feature importance, PDP | `FeatureImportance` |
| 08 | `08_final_model_export.ipynb` | Final training, export, model card | `ResearchExporter`, `PlatformImporter` |
