# ML Platform Gap Analysis

**Project:** ProxyDefence
**Date:** 2026-07-05
**Status:** Current platform vs target architecture gap identification

---

## 1. Gap Severity Classification

| Severity | Meaning | Timeline |
|----------|---------|----------|
| **CRITICAL** | Blocks all ML research or production deployment | Must fix before Phase 1 |
| **HIGH** | Significantly limits platform capability | Must fix before Phase 3 |
| **MEDIUM** | Important for production quality but not blocking | Fix in Phase 4 |
| **LOW** | Nice-to-have for advanced research | Fix in Phase 5 |

---

## 2. Missing Directories

### Current Structure
```
services/ml-platform/
├── datasets/
├── evaluation/
├── feature_store/
├── inference/
├── pipeline/
├── registry/
├── training/
└── routers/
```

### Target Additions

| Directory | Current | Target | Priority | Rationale |
|-----------|---------|--------|----------|-----------|
| `configs/` | ❌ Missing | Experiment configs (YAML) | HIGH | Enable config-driven, reproducible experiments |
| `monitoring/` | ❌ Missing | Drift detection, prediction monitoring | CRITICAL | No way to detect model degradation in production |
| `governance/` | ❌ Missing | Approval workflows, compliance, audit | MEDIUM | Required for regulated production deployment |
| `deployment/` | ❌ Missing | Batch inference, shadow scoring, A/B testing | HIGH | Online-only deployment limits use cases |
| `notebooks/` | ❌ Missing | Reference notebooks for research reproduction | MEDIUM | Researchers need templates to start |
| `benchmarks/` | ❌ Missing | Cross-model, cross-run benchmark storage | MEDIUM | No way to compare model versions historically |
| `tests/integration/` | ❌ Missing | End-to-end tests across all ML pipelines | MEDIUM | Only unit tests exist; no pipeline integration tests |
| `tests/research/` | ❌ Missing | Tests that research exports match platform expectations | HIGH | Manual handoff between research and production |
| `reports/` | ❌ Missing (exists in `data/reports/` but not served) | Evaluation reports API | MEDIUM | Reports are generated but not accessible via API |

### Research Directory Gaps

| Directory | Current | Target | Priority |
|-----------|---------|--------|----------|
| `configs/` | ❌ Missing | Experiment YAML configs | HIGH |
| `features/` | ❌ Missing | Feature definition files | MEDIUM |
| `evaluations/` | ❌ Missing | Structured evaluation storage | MEDIUM |
| `benchmarks/` | ❌ Missing | Benchmark results | LOW |

---

## 3. Missing Abstractions

### 3.1 Training Abstractions

| Abstraction | Current | Target | Priority |
|-------------|---------|--------|----------|
| `BaseTrainer` | ❌ Missing | Abstract trainer with train/predict/predict_proba | HIGH |
| `ClassificationTrainer` | ❌ Missing | Trainer for all classification models | HIGH |
| `RegressionTrainer` | ❌ Missing | Trainer for all regression models | HIGH |
| `ForecastingTrainer` | ❌ Missing | Time-series trainer (Prophet/darts) | HIGH |
| `AnomalyTrainer` | ❌ Missing | Unsupervised anomaly detection trainer | MEDIUM |
| `RankingTrainer` | ❌ Missing | Learning-to-rank trainer | LOW |
| `GraphTrainer` | ❌ Missing | Graph ML trainer (Node2Vec, GNN) | LOW |
| `MultiModelTrainer` | ❌ Missing | Ensemble/stacking trainer | MEDIUM |
| `AutoMLTrainer` | ❌ Missing | Automated model selection + tuning | LOW |

**Current state:** `training/models.py` defines 5 standalone model classes (`BaselineLogisticRegression`, `BaselineDecisionTree`, `BaselineRandomForest`, `BaselineXGBoost`, `BaselineLightGBM`) each with their own `train()` and `predict()` methods, but no shared base class. `training/trainer.py` has a monolithic `ModelTrainer` class with a single `train()` method.

### 3.2 Feature Abstractions

| Abstraction | Current | Target | Priority |
|-------------|---------|--------|----------|
| `OnlineFeatureStore` | ❌ Missing | Redis/pgvector-backed feature serving | HIGH |
| `OfflineFeatureStore` | ❌ Missing | Parquet/DuckDB-backed batch computation | HIGH |
| `FeatureValidator` | ❌ Missing | Schema, range, distribution validation | HIGH |
| `FeatureLineageTracker` | ❌ Missing | Source → transform → model tracking | MEDIUM |

**Current state:** `FeatureRegistry` in `feature_store/registry.py` is a thin CRUD wrapper around `ml.feature_definitions`. Feature computation is manual via `FeatureBuilder.compute_feature()`. No precomputed storage or online serving exists.

### 3.3 Evaluation Abstractions

| Abstraction | Current | Target | Priority |
|-------------|---------|--------|----------|
| `BaseEvaluator` | ❌ Missing | Common interface for all evaluators | MEDIUM |
| `ForecastingEvaluator` | ❌ Missing | Time-series metrics (MASE, sMAPE, MDA) | HIGH |
| `RankingEvaluator` | ❌ Missing | NDCG, MAP, MRR | LOW |
| `AnomalyEvaluator` | ❌ Missing | Precision/recall at threshold, AUC-PR | MEDIUM |
| `BenchmarkRunner` | ❌ Missing | Standardized cross-model comparison | MEDIUM |
| `AblationRunner` | ❌ Missing | Feature group ablation studies | MEDIUM |
| `DriftBaselineComputer` | ❌ Missing | Reference distribution computation | HIGH |

**Current state:** `evaluation/` has `classification.py` and `regression.py` with standalone functions. `EvaluationReporter` formats results. No evaluator ABC exists.

### 3.4 Monitoring Abstractions

| Abstraction | Current | Target | Priority |
|-------------|---------|--------|----------|
| `DriftDetector` | ❌ Missing | PSI, KS test, distribution shift | CRITICAL |
| `ModelMonitor` | ❌ Missing | Prediction logging, metric tracking | CRITICAL |
| `PerformanceTracker` | ❌ Missing | Accuracy-on-event, latency tracking | HIGH |
| `DataQualityMonitor` | ❌ Missing | Missing values, schema violations | HIGH |
| `AlertManager` | ❌ Missing | Threshold-based alerting rules | MEDIUM |

**Current state:** None of these exist.

---

## 4. Missing APIs

### 4.1 ML Platform API Gaps

| Endpoint | Current | Target | Priority |
|----------|---------|--------|----------|
| `POST /api/v1/ml/train` | ❌ | Trigger training with config | HIGH |
| `POST /api/v1/ml/train/schedule` | ❌ | Scheduled retraining configuration | HIGH |
| `GET /api/v1/ml/train/runs/{run_id}` | ❌ | Training run status + logs | HIGH |
| `GET /api/v1/ml/experiments/compare` | ❌ | Compare multiple runs | MEDIUM |
| `GET /api/v1/ml/experiments/{id}/reproduce` | ❌ | Clone and re-run experiment | MEDIUM |
| `POST /api/v1/ml/predict/batch` | ❌ | Batch inference endpoint | HIGH |
| `GET /api/v1/ml/models/{id}/metrics` | ❌ | Live monitoring metrics | CRITICAL |
| `GET /api/v1/ml/models/{id}/drift` | ❌ | Drift detection results | CRITICAL |
| `GET /api/v1/ml/monitoring/dashboard` | ❌ | Monitoring dashboard data | HIGH |
| `POST /api/v1/ml/deploy/shadow` | ❌ | Deploy model as shadow | HIGH |
| `POST /api/v1/ml/deploy/canary` | ❌ | Canary deployment with traffic % | MEDIUM |
| `POST /api/v1/ml/governance/promote` | ❌ | Promote with approval | MEDIUM |
| `GET /api/v1/ml/governance/audit/{id}` | ❌ | Audit trail for model version | MEDIUM |
| `POST /api/v1/ml/governance/rollback` | ❌ | Rollback to previous version | MEDIUM |

### 4.2 Existing APIs

| Endpoint | Current | Purpose |
|----------|---------|---------|
| `POST /api/v1/ml/features` | ✅ | Create feature definition |
| `GET /api/v1/ml/features` | ✅ | List feature definitions |
| `GET /api/v1/ml/features/{uuid}` | ✅ | Get feature definition |
| `POST /api/v1/ml/datasets/build` | ✅ | Build dataset |
| `GET /api/v1/ml/datasets` | ✅ | List datasets |
| `GET /api/v1/ml/datasets/{uuid}` | ✅ | Get dataset |
| `GET /api/v1/ml/datasets/{uuid}/download` | ✅ | Download dataset files |
| `POST /api/v1/ml/models/register` | ✅ | Register model version |
| `GET /api/v1/ml/models` | ✅ | List models |
| `GET /api/v1/ml/models/{uuid}` | ✅ | Get model version |
| `POST /api/v1/ml/models/{uuid}/transition` | ✅ | Transition stage |
| `GET /api/v1/ml/models/production` | ✅ | Get production model |
| `POST /api/v1/ml/predict` | ✅ | Single prediction |

---

## 5. Missing Schemas (Database)

| Table | Current | Purpose | Priority |
|-------|---------|---------|----------|
| `ml.feature_lineage` | ❌ | Feature source tracking | MEDIUM |
| `ml.feature_importance` | ❌ | Per-model feature importance | MEDIUM |
| `ml.dataset_lineage` | ❌ | Dataset parent/transform tracking | LOW |
| `ml.dataset_profiles` | ❌ | Statistical profiles per dataset version | LOW |
| `ml.model_governance` | ❌ | Approval, compliance, bias audit | MEDIUM |
| `ml.model_audit_log` | ❌ | State transition history | MEDIUM |
| `ml.prediction_log` | ❌ | All predictions with metadata | HIGH |
| `ml.drift_baselines` | ❌ | Reference distributions per model | HIGH |
| `ml.drift_results` | ❌ | Drift detection results over time | HIGH |
| `ml.batch_predictions` | ❌ | Batch inference job tracking | LOW |
| `ml.training_schedules` | ❌ | Scheduled retraining configuration | LOW |
| `ml.experiment_configs` | ❌ | Stored experiment configurations | LOW |

### Current Schema Status

```sql
-- ml.feature_definitions (EXISTS)
CREATE TABLE ml.feature_definitions (
    uuid UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    feature_type feature_type NOT NULL,       -- 11-value ENUM
    description TEXT,
    transform_config JSONB DEFAULT '{}',
    source_feature VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- ml.datasets (EXISTS)
CREATE TABLE ml.datasets (
    uuid UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    path TEXT NOT NULL,
    total_records INTEGER,
    train_records INTEGER,
    val_records INTEGER,
    test_records INTEGER,
    target_column VARCHAR(255),
    feature_versions JSONB,           -- [{name: str, version: int}]
    random_seed INTEGER,
    metadata_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- ml.model_versions (EXISTS)
CREATE TABLE ml.model_versions (
    uuid UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    model_type model_type NOT NULL,      -- 6-value ENUM
    stage model_stage NOT NULL DEFAULT 'development',  -- 5-stage lifecycle
    metrics JSONB DEFAULT '{}',
    parameters JSONB DEFAULT '{}',
    feature_version INTEGER,
    dataset_version INTEGER,
    mlflow_run_id VARCHAR(255),
    artifact_path TEXT,
    file_path TEXT,
    git_commit_hash VARCHAR(40),
    execution_time_seconds FLOAT,
    training_date TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- ml.predictions (EXISTS)
CREATE TABLE ml.predictions (
    id BIGSERIAL PRIMARY KEY,
    model_version_uuid UUID REFERENCES ml.model_versions(uuid),
    model_name VARCHAR(255) NOT NULL,
    model_version INTEGER NOT NULL,
    model_stage model_stage NOT NULL,
    feature_version INTEGER,
    prediction JSONB NOT NULL,
    confidence FLOAT,
    probabilities JSONB,
    latency_ms FLOAT,
    input_hash VARCHAR(64),
    input_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Missing Services

| Service | Current | Purpose | Priority |
|---------|---------|---------|----------|
| **MLflow Server** | ❌ Missing (file-based only) | Centralized experiment tracking + UI | HIGH |
| **Model Monitor** | ❌ Missing | Drift detection, alerting, dashboard | CRITICAL |
| **Batch Inference Worker** | ❌ Missing | Kafka consumer for batch prediction jobs | HIGH |
| **Scheduled Trainer** | ❌ Missing | Cron-triggered retraining pipeline | HIGH |
| **Feature Server** | ❌ Missing | Low-latency online feature serving | HIGH |

---

## 7. Missing Workflows

| Workflow | Current | Target | Priority |
|----------|---------|--------|----------|
| **Experiment → Model** | Manual: Notebook → joblib export → ML Platform | Automated: Config → Train → Register → Report | CRITICAL |
| **Feature → Model** | Manual: define feature, compute in training | Automated: register → compute → store → consume | HIGH |
| **Model → Production** | Manual: transition stage, test prediction | Automated: validation gates → shadow → canary → full | HIGH |
| **Production → Monitor** | ❌ Missing | Predict → log → drift check → alert | CRITICAL |
| **Research → Platform** | Manual copy of .joblib files | Config export → automated registration | HIGH |
| **Training → Retrain** | ❌ Missing | Schedule → data check → retrain → evaluate → promote | HIGH |
| **Model → Rollback** | ❌ Missing | Detect degradation → trigger rollback → verify | MEDIUM |
| **Deploy → Shadow** | ❌ Missing | Deploy → dual-score → compare → analyze | MEDIUM |

---

## 8. Missing Metadata

| Metadata | Current | Target | Priority |
|----------|---------|--------|----------|
| Model card | ❌ | Per-model documentation (Google format) | MEDIUM |
| Feature lineage | ❌ | Source → transform → model for every feature | MEDIUM |
| Dataset profile | ❌ | Statistical summary per dataset version | LOW |
| Experiment notes | ❌ | Researcher annotations per run | LOW |
| Governance audit | ❌ | Who approved what, when, why | MEDIUM |
| Compliance tags | ❌ | GDPR, SOC2, internal classification | LOW |
| Bias audit | ❌ | Fairness metrics per demographic | LOW |
| Prediction statistics | ❌ | Volume, latency, error rate per model | HIGH |
| Drift baseline | ❌ | Reference distribution per feature/prediction | HIGH |
| Cost tracking | ❌ | Training cost, inference cost per model | LOW |

---

## 9. Duplicate Logic

| Component | Location 1 | Location 2 | Impact |
|-----------|-----------|------------|--------|
| `ConversationMemory` | `llm/memory.py` (141 lines) | `memory/conversation.py` (112 lines) | Two independent implementations of the same API — can diverge over time |
| Feature building | `datasets/loader.py` (EnergyServiceLoader) | `feature_store/builders.py` (EnergyServiceDataLoader) | Nearly identical data loading and feature matrix construction — 87% code overlap |
| Entity type lists | `datasets/loader.py` (ENERGY_TABLES) | `feature_store/builders.py` (ENERGY_TABLES) | Same 14 tables defined in two places — adding a table requires updating both |
| Synthetic data generation | `datasets/loader.py` (MockDataLoader) | `feature_store/builders.py` (generate_synthetic) | Same fields, same distributions, different implementation — test divergence risk |
| Dataset download logic | `datasets/builder.py` (dataset building) | `research/datasets/fetch_data.py` | Same REST API calls, same feature joins — 70% code overlap |
| Drop columns list | `datasets/loader.py` (drop_cols) | `feature_store/builders.py` (drop_cols) | Same 23 columns defined in two places |

---

## 10. Missing Automation

| Automation | Current | Target | Priority |
|------------|---------|--------|----------|
| Dataset auto-build on data change | ❌ | Trigger rebuild when source data changes | MEDIUM |
| Model auto-retrain on schedule | ❌ | Weekly/monthly retraining | HIGH |
| Auto-promote on metric threshold | ❌ | Auto-promote to staging if metrics exceed threshold | MEDIUM |
| Shadow deployment on register | ❌ | Auto-deploy shadow when model reaches staging | MEDIUM |
| Drift alert on threshold breach | ❌ | Slack/email when drift exceeds threshold | HIGH |
| Rollback on performance drop | ❌ | Auto-rollback if production metric drops | MEDIUM |
| Feature auto-compute on source update | ❌ | Recompute features when source data changes | LOW |
| Experiment clone on config change | ❌ | Re-run with modified config | LOW |

---

## 11. Summary: Fix Priority Matrix

### Must Fix Before Any Model Development (CRITICAL)

```
Priority 0 — Foundation Blockers:
┌────────────────────────────────────────────────────────────────────┐
│ 1. Online feature store (Redis/pgvector)                          │
│ 2. Prediction logging (ml.prediction_log)                         │
│ 3. Drift detection framework (PSI, KS test)                       │
│ 4. Research → Platform pipeline (config-driven export)            │
└────────────────────────────────────────────────────────────────────┘
```

### Must Fix Before Production Deployment (HIGH)

```
Priority 1 — Production Blockers:
┌────────────────────────────────────────────────────────────────────┐
│ 5. Centralized MLflow server                                      │
│ 6. BaseTrainer framework                                          │
│ 7. Batch inference pipeline                                       │
│ 8. Model monitoring + alerting                                    │
│ 9. Dataset validation pipeline                                    │
│ 10. Scheduled retraining                                          │
└────────────────────────────────────────────────────────────────────┘
```

### Should Fix Before Advanced Research (MEDIUM)

```
Priority 2 — Quality Blockers:
┌────────────────────────────────────────────────────────────────────┐
│ 11. Approval workflow for promotions                              │
│ 12. Audit trail for model changes                                 │
│ 13. Benchmark comparison framework                                │
│ 14. Ablation study runner                                         │
│ 15. Shadow scoring deployment                                     │
│ 16. Remove duplicate code (feature builders, memory)              │
└────────────────────────────────────────────────────────────────────┘
```

### Nice-to-Have (LOW)

```
Priority 3 — Research Enhancements:
┌────────────────────────────────────────────────────────────────────┐
│ 17. Graph ML trainers                                             │
│ 18. A/B testing framework                                         │
│ 19. Model card generation                                         │
│ 20. Bias/fairness auditing                                        │
│ 21. Distributed training support                                  │
│ 22. AutoML pipeline                                               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 12. Risk Assessment

### If Gaps Are Not Addressed

| Gap Unaddressed | Risk | Impact |
|-----------------|------|--------|
| No feature store | Every training run recomputes features from raw data | Training time 10x longer, feature inconsistencies |
| No prediction logging | Cannot audit predictions, no drift baseline | Regulatory non-compliance, blind to model degradation |
| No drift detection | Model silently degrades in production | Wrong predictions → bad decisions → reputation damage |
| No experiment tracking (optional) | Lost experiments, unreproducible results | Wasted research effort, no scientific rigor |
| No batch inference | Cannot run large-scale predictions | Limited to online API, no bulk analytics |
| Duplicate feature code | Feature drift between training and inference | Silent accuracy loss in production |
| Research→Platform gap | Manual model handoff introduces errors | Production model != best research model |

### Mitigation Strategy

1. **Immediate (Phase 0):** Consolidate duplicate code, add prediction logging, implement drift detection — these are non-negotiable before any model reaches production.
2. **Short-term (Phase 1-2):** Build feature store, BaseTrainer, centralized MLflow — these enable systematic research.
3. **Medium-term (Phase 3-4):** Production deployment infrastructure, monitoring, governance — these make models safe for production.
4. **Long-term (Phase 5):** Advanced research capabilities — these differentiate the platform.
