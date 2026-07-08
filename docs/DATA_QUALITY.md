# Data Quality Framework

## Overview

The Data Quality Framework provides a systematic approach to measuring, monitoring, and enforcing data quality across the ML Platform. It defines six quality dimensions, each with a scoring methodology, configurable thresholds, and integration points throughout the dataset lifecycle.

Quality checks execute during the **validate** stage of the ingestion pipeline and produce structured reports stored in `ml.quality_reports`. Historical snapshots in `ml.quality_dashboard` enable trend analysis and drift detection.

## Six Quality Dimensions

### 1. Completeness

**Definition**: The degree to which data is present (not missing or null) across all expected fields.

**Scoring Formula**:

```
completeness_score = 1.0 - (total_missing_cells / total_expected_cells)
```

Where:
- `total_missing_cells` = count of NULL/NaN values across all columns
- `total_expected_cells` = total_cells = rows × columns

**Example Thresholds**:

| Level | Threshold | Action |
|-------|-----------|--------|
| Critical | < 0.80 | Pipeline abort |
| Warning | < 0.90 | Alert, continue |
| Pass | >= 0.90 | Proceed |

### 2. Consistency

**Definition**: The degree to which data conforms to expected formats, types, and distributions.

**Scoring Formula**:

```
consistency_score = Σ(weight_i × check_i) / Σ(weight_i)
```

Checks:
- **Schema type match**: `(matching_columns / total_columns)` — weight 0.4
- **Distribution match**: `1.0 - (anomalous_features / total_features)` — weight 0.3
- **Target distribution**: `min_class_percentage` — weight 0.3

**Example Thresholds**:

| Level | Threshold | Action |
|-------|-----------|--------|
| Critical | < 0.75 | Pipeline abort |
| Warning | < 0.90 | Alert, continue |
| Pass | >= 0.90 | Proceed |

### 3. Uniqueness

**Definition**: The degree to which data contains no duplicate records or primary key violations.

**Scoring Formula**:

```
uniqueness_score = 1.0 - duplicate_rate
```

Where `duplicate_rate = duplicate_count / total_rows`.

**Example Thresholds**:

| Level | Threshold | Action |
|-------|-----------|--------|
| Critical | < 0.90 | Pipeline abort |
| Warning | < 0.95 | Alert, continue |
| Pass | >= 0.95 | Proceed |

### 4. Timeliness

**Definition**: The degree to which data is current and arrives within expected time windows.

**Scoring Formula**:

```
timeliness_score = max(0.0, 1.0 - (actual_lag_hours / max_acceptable_lag_hours))
```

Where:
- `actual_lag_hours` = time since the latest record's timestamp
- `max_acceptable_lag_hours` = configured per dataset (e.g., 24h for daily, 1h for streaming)

**Example Thresholds**:

| Level | Threshold | Action |
|-------|-----------|--------|
| Critical | < 0.50 | Pipeline abort |
| Warning | < 0.80 | Alert, continue |
| Pass | >= 0.80 | Proceed |

### 5. Validity

**Definition**: The degree to which data values conform to domain-specific constraints, ranges, and business rules.

**Scoring Formula**:

```
validity_score = Σ(weight_i × valid_check_i) / Σ(weight_i)
```

Checks:
- **Range validity**: `(values_in_range / total_values)` — weight 0.3
- **Outlier rate**: `1.0 - outlier_rate` — weight 0.3
- **Type validity**: `(type_valid_values / total_values)` — weight 0.2
- **Pattern validity**: `(pattern_match_values / total_values)` — weight 0.2

**Example Thresholds**:

| Level | Threshold | Action |
|-------|-----------|--------|
| Critical | < 0.70 | Pipeline abort |
| Warning | < 0.85 | Alert, continue |
| Pass | >= 0.85 | Proceed |

### 6. Integrity

**Definition**: The degree to which data maintains referential integrity, relational constraints, and internal consistency.

**Scoring Formula**:

```
integrity_score = Σ(integrity_checks_passed) / Σ(integrity_checks_total)
```

Checks:
- **Referential integrity**: Foreign key relationships are valid
- **Temporal ordering**: Timestamps are monotonically increasing
- **Train/test separation**: No overlap between train and test indices
- **Balance checks**: Target class distribution within expected bounds

**Example Thresholds**:

| Level | Threshold | Action |
|-------|-----------|--------|
| Critical | < 0.80 | Pipeline abort |
| Warning | < 0.95 | Alert, continue |
| Pass | >= 0.95 | Proceed |

## Scoring Methodology

### Weighted Average for Overall Score

The overall data quality score is a weighted average of the six dimension scores:

```
overall_score = Σ(w_i × dimension_score_i) / Σ(w_i)
```

### Default Weights

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| Completeness | 0.25 | Missing data is the most common and impactful quality issue |
| Consistency | 0.20 | Schema and distribution drifts degrade model performance |
| Uniqueness | 0.15 | Duplicates cause biased training and evaluation |
| Timeliness | 0.15 | Stale data leads to outdated models |
| Validity | 0.15 | Invalid values corrupt feature representations |
| Integrity | 0.10 | Referential issues are less frequent but severe when present |

Weights are configurable per dataset via `ml.quality_reports.dimensions` JSON:

```json
{
  "weights": {
    "completeness": 0.25,
    "consistency": 0.20,
    "uniqueness": 0.15,
    "timeliness": 0.15,
    "validity": 0.15,
    "integrity": 0.10
  }
}
```

## Report Structure

Each quality check produces a report stored in `ml.quality_reports`:

```json
{
  "report_name": "energy_infrastructure_v3_quality",
  "dataset_name": "energy_infrastructure",
  "dataset_version": 3,
  "report_type": "post_ingestion",
  "status": "completed",
  "overall_score": 0.94,
  "completeness_score": 0.97,
  "consistency_score": 0.92,
  "uniqueness_score": 0.99,
  "timeliness_score": 0.88,
  "validity_score": 0.91,
  "integrity_score": 0.95,
  "total_checks": 24,
  "passed_checks": 21,
  "failed_checks": 2,
  "warning_checks": 1,
  "threshold_warning": 0.95,
  "threshold_failure": 0.90,
  "checks": [
    {
      "check_name": "missing_values",
      "dimension": "completeness",
      "status": "passed",
      "score": 0.97,
      "details": { "missing_rate": 0.03, "columns_high_missing": [] }
    },
    {
      "check_name": "schema_types",
      "dimension": "consistency",
      "status": "failed",
      "score": 0.85,
      "details": {
        "mismatches": {
          "throughput_mtpa": { "expected": "float64", "actual": "object" }
        }
      }
    },
    {
      "check_name": "outliers",
      "dimension": "validity",
      "status": "warning",
      "score": 0.91,
      "details": {
        "outlier_columns": {
          "storage_capacity_barrels": { "outlier_count": 12, "outlier_rate": 0.024 }
        }
      }
    }
  ],
  "dimensions": {
    "weights": {
      "completeness": 0.25,
      "consistency": 0.20,
      "uniqueness": 0.15,
      "timeliness": 0.15,
      "validity": 0.15,
      "integrity": 0.10
    }
  },
  "executed_by": "pipeline",
  "executed_at": "2026-07-06T10:05:00Z"
}
```

### Per-Column Quality

Each column's quality is assessed individually and available via `ml.dataset_profiles`:

```json
{
  "column_name": "throughput_mtpa",
  "dtype": "float64",
  "missing_count": 5,
  "missing_rate": 0.01,
  "unique_count": 482,
  "cardinality": 0.96,
  "mean": 52.3,
  "std": 34.1,
  "min": 0.0,
  "max": 210.0,
  "p25": 25.0,
  "p75": 75.0,
  "outlier_count": 8,
  "outlier_rate": 0.016,
  "is_identifier": false,
  "quality_score": 0.95,
  "quality_issues": []
}
```

## Issue Severity Levels

| Severity | Description | Report Score Impact | Pipeline Action |
|----------|-------------|---------------------|-----------------|
| **Critical** | Data cannot be used for training/inference | >= 2 failed checks with critical | Pipeline abort, notification |
| **Warning** | Degradation detected, investigation recommended | >= 2 warning checks | Alert, pipeline continues |
| **Info** | Minor issues, no immediate action needed | < 2 info-level checks | Logged only |

Severity is determined by:
- Score falling below `threshold_failure` (0.90) = critical
- Score between `threshold_failure` and `threshold_warning` (0.90–0.95) = warning
- Score above `threshold_warning` (0.95) = info

## Dashboard Metrics

### Trend Tracking

The `ml.quality_dashboard` table stores daily snapshots for trend analysis:

```json
{
  "dashboard_name": "energy_infrastructure_tracker",
  "dataset_name": "energy_infrastructure",
  "snapshot_date": "2026-07-06",
  "overall_score": 0.94,
  "completeness_score": 0.97,
  "consistency_score": 0.92,
  "uniqueness_score": 0.99,
  "timeliness_score": 0.88,
  "validity_score": 0.91,
  "integrity_score": 0.95,
  "row_count": 500,
  "column_count": 28,
  "trend_direction": "improving",
  "score_delta": 0.02,
  "alerts_count": 1,
  "critical_alerts": 0
}
```

### Snapshot Management

Snapshots are created on:
- Every pipeline execution (post-ingestion)
- Daily via scheduled job (aggregate view)
- On demand via API

```bash
# Create an ad-hoc snapshot
POST /api/v1/ml/quality/snapshot
{
  "dataset_name": "energy_infrastructure",
  "dashboard_name": "energy_infrastructure_tracker"
}
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/ml/quality/report?dataset=...&version=...` | Retrieve latest quality report |
| `GET /api/v1/ml/quality/dashboard?dataset=...&days=30` | Get dashboard trends |
| `POST /api/v1/ml/quality/check` | Run quality check on provided data |
| `GET /api/v1/ml/quality/compare?dataset=...&v1=...&v2=...` | Compare quality across versions |

## Quality Gates

Quality gates enforce minimum quality scores for dataset promotion through the lifecycle:

| Gate | Location | Minimum Overall Score | Minimum Per-Dimension |
|------|----------|----------------------|-----------------------|
| **Ingestion Gate** | After validate step in pipeline | 0.80 | 0.70 (any dimension) |
| **Catalog Gate** | Before catalog registration | 0.85 | 0.75 (any dimension) |
| **Training Gate** | Before dataset used for training | 0.90 | 0.80 (any dimension) |
| **Production Gate** | Before model promoted to production | 0.90 | 0.85 (any dimension) |

If a quality gate is not met, the pipeline step fails with a descriptive error:

```
QualityGateError: Dataset energy_infrastructure v3 failed production gate:
  overall_score=0.82 < 0.90
  completeness_score=0.97
  consistency_score=0.92
  uniqueness_score=0.99
  timeliness_score=0.88 < 0.85
  validity_score=0.91
  integrity_score=0.95
  Action: Improve timeliness before promoting dataset to production.
```

## Comparison Between Versions

The framework supports diffing quality reports across dataset versions:

```bash
GET /api/v1/ml/quality/compare?dataset=energy_infrastructure&v1=2&v2=3
```

Response:

```json
{
  "dataset_name": "energy_infrastructure",
  "version_a": 2,
  "version_b": 3,
  "overall_delta": 0.03,
  "dimension_deltas": {
    "completeness": { "a": 0.95, "b": 0.97, "delta": 0.02 },
    "consistency":  { "a": 0.88, "b": 0.92, "delta": 0.04 },
    "uniqueness":   { "a": 0.99, "b": 0.99, "delta": 0.00 },
    "timeliness":   { "a": 0.75, "b": 0.88, "delta": 0.13 },
    "validity":     { "a": 0.90, "b": 0.91, "delta": 0.01 },
    "integrity":    { "a": 0.95, "b": 0.95, "delta": 0.00 }
  },
  "new_issues": [],
  "resolved_issues": ["high_missing_rate:0.08"],
  "regression": false
}
```

## Integration Points

| Pipeline Stage | Integration |
|----------------|-------------|
| **validate** (ingestion pipeline) | `DatasetValidationPipeline` runs quality checks, produces `ValidationResult` objects |
| **normalize** (ingestion pipeline) | Quality issues identified during normalization are logged to `ml.ingestion_errors` |
| **profile** (ingestion pipeline) | `DatasetProfiler.profile()` computes per-column quality metrics |
| **version** (ingestion pipeline) | Quality scores are stored alongside version metadata |
| **catalog** (ingestion pipeline) | Quality gate must pass before catalog registration |
| **training** (model trainer) | Quality gate validates dataset before model training |
| **deployment** (model promotion) | Production gate validates dataset quality before production deployment |

## Alert Rules

The `AlertManager` provides rule-based alerting on quality metrics:

```python
alert_manager = get_alert_manager()
alert_manager.add_rule(AlertRule(
    name="low_completeness",
    metric="completeness_score",
    operator="lt",
    threshold=0.90,
    channels=["log", "slack"],
))
alert_manager.add_rule(AlertRule(
    name="critical_quality_degradation",
    metric="overall_score",
    operator="lt",
    threshold=0.80,
    channels=["log", "slack", "pagerduty"],
))
```
