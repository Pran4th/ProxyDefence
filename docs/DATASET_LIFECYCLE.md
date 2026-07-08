# Dataset Lifecycle

## Overview

The dataset lifecycle defines the end-to-end journey of data from external source ingestion to production ML feature consumption. The lifecycle is managed through the ML Platform's pipeline engine, with each stage producing versioned, validated, and cataloged artifacts.

## Lifecycle Stages

```
  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │  Ingest   │──▶│ Extract  │──▶│ Validate │──▶│Normalize │──▶│ Profile  │
  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
       │              │              │              │              │
       ▼              ▼              ▼              ▼              ▼
  Connector      API Call       Quality        Rule         Statistics
  Framework      Pagination     Checks        Application  & Metrics
                                                                   
  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ Version   │──▶│ Catalog  │──▶│ Register │──▶│  Store   │──▶│ Feature  │
  │           │   │          │   │          │   │          │   │ Engineer │
  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
       │              │              │              │              │
       ▼              ▼              ▼              ▼              ▼
  Semantic        Dataset         Dataset        Parquet/      Transforms
  Versioning      Card            Registry       Feature       & Groups
  + DVC                           + Lineage      Store
```

## Stage 1 — Data Connector

The first stage selects and configures a source connector.

| Step | Description |
|------|-------------|
| **Choose Source Type** | Select from 15+ registered connector types (GNews, ACLED, ICEWS, EIA, FRED, Energy Service, etc.) |
| **Configure Auth** | Apply authentication strategy: Basic, Bearer, API Key, or OAuth2 |
| **Set Rate Limits** | Configure token bucket capacity and refill rate |
| **Choose Pagination** | Select pagination strategy: page_number, cursor, offset, or next_url |
| **Discover Schema** | Introspect source API to discover endpoints, fields, data types |

Configuration is validated against `ml.connector_definitions.config_schema` before the connector is activated.

```python
connector = registry.create("eia")
await connector.configure({
    "api_key": "***",
    "base_url": "https://api.eia.gov/v2/",
    "rate_limit": {"capacity": 50, "refill_rate": 5.0},
    "pagination": {"strategy": "offset", "page_size": 500},
})
await connector.connect()
schemas = await connector.discover_schema()
```

## Stage 2 — Ingestion Pipeline

The ingestion pipeline executes the data fetch through the configured connector and passes raw data through a series of steps.

### Pipeline Steps

```
  download ──▶ extract ──▶ validate ──▶ normalize ──▶ profile ──▶ version ──▶ catalog ──▶ register ──▶ store
```

| Step | Type | Description |
|------|------|-------------|
| `download` | `download` | Executes connector fetch with pagination, rate limiting, retry |
| `extract` | `extract` | Extracts relevant fields from raw response payload |
| `validate` | `validate` | Runs quality checks (missing values, duplicates, types) |
| `normalize` | `normalize` | Applies normalization rules (date formats, units, mappings) |
| `profile` | `profile` | Computes statistical profiles and health scores |
| `version` | `version` | Assigns semantic version, computes hashes, creates manifest |
| `catalog` | `catalog` | Registers in dataset catalog with metadata card |
| `register` | `register` | Records in dataset registry with lineage tracking |
| `store` | `store` | Persists raw/processed data to appropriate storage |

### Execution Context

The `IngestionContext` carries state between pipeline steps as a key-value store:

```python
@dataclass
class IngestionContext:
    pipeline_name: str
    pipeline_version: int
    connector_name: str
    connector_version: int
    job_uuid: str
    params: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)  # step-to-step
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    record_count: int = 0
    error_count: int = 0
```

### Error Handling

- **Per-step isolation**: Each step wraps in try/except; failures are recorded without aborting the entire pipeline
- **Retry with backoff**: Download steps use exponential backoff + jitter (max 3 retries)
- **Partial completion**: Pipeline can complete with partial results; failed records are logged to `ml.ingestion_errors`

## Stage 3 — Validation

Data quality validation runs across six dimensions before data progresses to normalization.

| Check | Dimension | Method |
|-------|-----------|--------|
| Column validity | Validity | Schema matching against registered schema |
| Schema types | Consistency | Data type verification per column |
| Distribution | Consistency | Z-score comparison against reference statistics |
| Duplicates | Uniqueness | `df.duplicated().sum()` rate < 5% |
| Missing values | Completeness | `df.isnull().sum().sum()` rate < 10% |
| Outliers | Validity | IQR-based outlier detection per column |
| Target distribution | Consistency | Minimum class percentage > 1% |
| Temporal leakage | Integrity | No duplicate timestamps in time series |
| Train/test leakage | Integrity | No index overlap between train and test splits |

Each check returns a `ValidationResult` with `passed`, `score` (0.0-1.0), and `details`. Results are persisted to `ml.dataset_validations`.

Threshold configuration:

```yaml
validation:
  missing_rate_threshold: 0.10
  duplicate_rate_threshold: 0.05
  outlier_rate_threshold: 0.01
  z_score_threshold: 3.0
  iqr_multiplier: 1.5
```

## Stage 4 — Normalization

Normalization applies configurable rules to transform raw data into a consistent format.

### Rule Application Order

Rules are applied sequentially in priority order. Each rule in the `NormalizationRegistry` maps to a `BaseNormalizer` subclass.

```
  1. Null Handling        ──▶ fillna / dropna strategy per column
  2. Data Type Coercion   ──▶ astype / to_datetime / to_numeric
  3. String Cleaning      ──▶ strip / lower / regex replacement
  4. Unit Conversion      ──▶ imperial→metric, barrel→ton, bbl→m³
  5. Value Mapping        ──▶ source→target value maps
  6. Date Normalization   ──▶ ISO 8601 standardization
  7. Outlier Clipping     ──▶ winsorize / clip at percentiles
  8. Categorical Encoding ──▶ label / one-hot / frequency encoding
```

### Type-Specific Normalizers

| Normalizer Type | Purpose | Example |
|----------------|---------|---------|
| `date_normalizer` | Standardizes date formats | `01/15/2024` → `2024-01-15` |
| `unit_converter` | Converts measurement units | `bbl` → `m³` |
| `value_mapper` | Maps source values to targets | `"Y"` → `True` |
| `string_cleaner` | Cleans text fields | `"  NYC "` → `"nyc"` |
| `numeric_coercer` | Coerces strings to numbers | `"1,234.56"` → `1234.56` |

The normalization registry (`ml.normalization_rules`) stores all active rules with their configurations. Value mappings are stored in `ml.normalization_mappings`.

```yaml
normalization_rules:
  - name: normalize_dates
    rule_type: date_normalizer
    source_field: published_at
    target_field: published_at_iso
    config:
      input_formats: ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%m/%d/%Y"]
      output_format: "%Y-%m-%dT%H:%M:%SZ"
  - name: map_operational_status
    rule_type: value_mapper
    source_field: status
    target_field: status_clean
    config:
      mapping:
        "1": "active"
        "0": "inactive"
        "A": "active"
        "I": "inactive"
```

## Stage 5 — Profiling

Statistical profiling computes per-column and overall dataset characteristics.

### Statistical Profile

Per-column profile includes:

| Metric | Numeric | Categorical | DateTime |
|--------|---------|-------------|----------|
| dtype | ✓ | ✓ | ✓ |
| missing_count | ✓ | ✓ | ✓ |
| missing_rate | ✓ | ✓ | ✓ |
| unique_count | ✓ | ✓ | ✓ |
| cardinality | ✓ | ✓ | ✓ |
| mean / std | ✓ | | |
| min / max / median | ✓ | | |
| p1 / p5 / p25 / p75 / p95 / p99 | ✓ | | |
| skew / kurtosis | ✓ | | |
| IQR | ✓ | | |
| zeros / negatives | ✓ | | |
| entropy | | ✓ | |
| top_value / top_frequency | | ✓ | |
| avg/min/max length | | ✓ | |
| min_date / max_date | | | ✓ |
| range_days | | | ✓ |

### Health Score

The `DatasetStatistics.get_health_score()` method produces a composite 0-100 score:

```python
score = 100.0
if missing_rate > 5%:    score -= missing_rate * 100
if duplicate_rate > 5%:  score -= duplicate_rate * 50
if row_count < 100:     score -= 20
if total_cells == 0:    score -= 50
```

Profiles are persisted to `ml.dataset_profiles` and statistics to `ml.dataset_statistics`.

## Stage 6 — Versioning

Every dataset version is assigned a semantic version, content-addressed hash, and manifest.

### Semantic Versioning

```
v{major}.{minor}.{patch}

v1.0.0  — Initial dataset version
v1.1.0  — Schema-compatible additions (new columns, more rows)
v2.0.0  — Breaking schema changes (column removed, type changed)
```

In practice, the ML Platform uses monotonic integer versions (`v1`, `v2`, `v3`) for simplicity, with the semantic interpretation encoded in the changelog metadata.

### Hash Verification

```python
class DatasetHasher:
    @staticmethod
    def hash_dataframe(df: pd.DataFrame) -> str:
        content = pd.util.hash_pandas_object(df).values
        return hashlib.sha256(content.tobytes()).hexdigest()

    @staticmethod
    def hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
```

### Manifest Creation

Each dataset version creates a manifest in `ml.dataset_manifests` with:

| Field | Description |
|-------|-------------|
| `file_path` | Full path to the dataset file |
| `file_size` | Size in bytes |
| `sha256` | SHA-256 content hash |
| `row_count` | Number of rows |
| `column_count` | Number of columns |
| `format` | File format (parquet, csv, json) |
| `compression` | Compression algorithm |

Manifests enable integrity verification on retrieval:

```bash
# Verify all files for energy_infrastructure v3
GET /api/v1/ml/datasets/energy_infrastructure/v3/manifest/verify
```

DVC integration via `DvcManager` provides Git-based dataset versioning:

```python
dvc = DvcManager()
dvc.track("data/datasets/energy_infrastructure/v3")
dvc.push()
```

## Stage 7 — Catalog Registration

### Dataset Cards

Every dataset has a dataset card (`ml.dataset_cards`) documenting its purpose, limitations, and usage:

```json
{
  "dataset_name": "energy_infrastructure",
  "title": "Energy Infrastructure Catalog",
  "summary": "Global energy infrastructure assets including ports, pipelines, refineries, oil fields",
  "intended_uses": "Infrastructure risk classification, capacity forecasting",
  "limitations": "Coverage limited to publicly reported data",
  "ethical_considerations": "Aggregate infrastructure data, no PII",
  "maintenance": "Updated quarterly via Energy Service API",
  "authors": [{"name": "ProxyDefence ML Platform", "role": "system"}],
  "references": []
}
```

### Lineage Tracking

Dataset lineage is tracked as a directed acyclic graph (DAG) in `ml.dataset_lineage`:

```python
await DatasetLineage.add_edge(
    dataset_name="energy_features_v3",
    dataset_version=1,
    parent_name="energy_infrastructure",
    parent_version=3,
    transform_type="feature_engineering",
    transform_params={"features": ["throughput_mtpa", "storage_capacity"]},
)
```

### Provenance

Source provenance is recorded in `ml.dataset_provenance`:

| Field | Description |
|-------|-------------|
| `source_type` | `api`, `download`, `build`, `upload`, `connector` |
| `source_name` | Name of the source system |
| `source_version` | Version identifier from the source |
| `source_url` | URL of the source API or file |
| `access_method` | How the data was accessed |
| `checksum` | Optional source-side checksum |

### Dependencies

Dataset dependencies are recorded in `ml.dataset_dependencies` for dependency resolution during pipeline execution.

## Stage 8 — Storage

Storage is organized into three tiers:

### Raw Store

```
data/datasets/{name}/v{version}/
├── raw/
│   ├── page_001.json
│   └── page_002.json
```

Raw API responses as received, preserved for audit and reprocessing.

### Processed Store

```
data/datasets/{name}/v{version}/
├── train.parquet
├── validation.parquet
├── test.parquet
├── metadata.json
└── .dvc
```

Processed, split, and versioned datasets in Parquet format with ZSTD compression.

### Feature Store

```
data/materialized/{entity_type}/v{feature_version}/
├── features.parquet
└── .dvc
```

Materialized feature vectors for online serving, stored as parquet files.

**Compression**: All Parquet files use ZSTD compression (compression ratio ~4:1 for structured tabular data).

## Stage 9 — Feature Engineering

### Feature Transforms

18 built-in transforms registered in `TRANSFORM_REGISTRY`:

| Transform | Type | Description |
|-----------|------|-------------|
| `identity` | Pass-through | Raw column as feature |
| `standard_scale` | Numerical | Z-score normalization |
| `minmax` | Numerical | Min-max scaling to [0,1] |
| `robust_scale` | Numerical | IQR-based robust scaling |
| `one_hot` | Categorical | One-hot encoding |
| `label_encode` | Categorical | Label encoding |
| `frequency_encode` | Categorical | Frequency ratio encoding |
| `binary_encode` | Categorical | Threshold-based binary encoding |
| `temporal` | DateTime | Date/time component extraction |
| `rolling_window` | Time Series | Rolling window aggregation |
| `ewma` | Time Series | Exponentially weighted moving average |
| `lag` | Time Series | Lagged value feature |
| `ratio` | Numerical | Feature ratio computation |
| `interaction` | Numerical | Feature interaction (multiply/add) |
| `polynomial` | Numerical | Polynomial expansion |
| `target_encode` | Categorical | Target mean encoding |
| `aggregate` | Aggregation | Group-by aggregation |
| `geospatial` | Geospatial | Haversine distance to chokepoints |

### Feature Groups

Features can be organized into logical groups (`ml.feature_groups`) for easier management:

| Group | Type | Features |
|-------|------|----------|
| `port_capacity` | numerical | throughput_mtpa, storage_capacity_barrels |
| `location_attributes` | categorical | region, iso_code, location_type |
| `temporal_patterns` | temporal | created_at_year, created_at_month |
| `risk_indicators` | derived | region_risk_score, chokepoint_proximity |

### Feature Snapshots

Point-in-time feature values are captured in `ml.feature_snapshots` for reproducibility:

```python
await FeatureSnapshots.create_snapshot(
    feature_version=3,
    entity_type="port",
    entity_id="uuid-abc-123",
    snapshot_data={"throughput_mtpa": 85.3, "region": "middle_east"},
    snapshot_label="q1_2026_baseline",
    snapshot_type="scheduled",
)
```

Snapshots support diff comparison between any two points in time:

```python
diff = await FeatureSnapshots.diff(snapshot_a_uuid, snapshot_b_uuid)
# Returns: {"changed_features": 3, "changes": { "throughput_mtpa": {"from": 80.1, "to": 85.3} }}
```

### Full Feature Pipeline

The `FeaturePipeline` orchestrates feature computation end-to-end:

1. Load data from Energy Service via `EnergyServiceDataLoader`
2. Fetch active feature definitions from `FeatureRegistry`
3. Compute all features via `FeatureBuilder.compute_all()`
4. Cache results in `FeatureCache` (LRU, TTL 300s)
5. Persist to `ml.feature_vectors` for online serving
6. Materialize to parquet for batch training
