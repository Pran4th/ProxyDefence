# ML Platform Architecture Review

**Project:** ProxyDefence
**Author:** Principal ML Architect
**Date:** 2026-07-05
**Status:** Complete architectural analysis — no implementation

---

## Table of Contents

1. Current ML Architecture
2. Target ML Architecture
3. Research Infrastructure
4. Dataset Infrastructure
5. Feature Store
6. Training Infrastructure
7. Evaluation Infrastructure
8. Experiment Tracking
9. Model Registry
10. Integration Architecture
11. Research Models
12. Gap Analysis

---

## 1. Current ML Architecture

### 1.1 Service Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CURRENT ML LANDSCAPE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐   │
│  │   ML Service     │    │   ML Platform     │    │  Embedding    │   │
│  │   (port 8002)    │    │   (port 8007)     │    │  Service      │   │
│  │                  │    │                   │    │  (port 8005)  │   │
│  │  NLP Inference   │    │  Training API     │    │               │   │
│  │  Sentiment       │    │  Model Registry   │    │  bge-small    │   │
│  │  NER             │    │  Feature Store    │    │  384-dim      │   │
│  │  Topic Classify  │    │  Dataset Builder  │    │  pgvector     │   │
│  │  Threat Score    │    │  MLflow Tracking  │    │               │   │
│  │  Entity Extract  │    │  SHAP Explain     │    │  Semantic     │   │
│  │  Relationships   │    │  DVC Versioning   │    │  Search       │   │
│  └────────┬─────────┘    └────────┬─────────┘    └───────┬───────┘   │
│           │                       │                       │           │
│           ▼                       ▼                       ▼           │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                    RESEARCH DIRECTORY                        │     │
│  │  8 notebooks: EDA → Preprocessing → Feature Engineering →  │     │
│  │  Baselines → Comparison → Tuning → SHAP → Export            │     │
│  │  MLflow (file), synthetic data fallback                     │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                    ENERGY SERVICE                            │     │
│  │  14 entity tables, risk engine, ML bridge (rule-based       │     │
│  │  fallback to ML Platform), digital twin, procurement, SPR   │     │
│  └─────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 ML Service (port 8002)

**Responsibility:** Real-time NLP enrichment of news articles in the Kafka pipeline.

**Pipeline steps (per article):**
1. Build full text from title + content
2. Extractive summarization (first 2 sentences)
3. Sentiment analysis (DistilBERT, HuggingFace)
4. Topic classification (keyword frequency: war/diplomacy/economics/cyber)
5. Named entity recognition (BERT NER → spaCy fallback)
6. Threat scoring (rule-based keyword tiers + modifiers)
7. Entity relationship inference (keyword pattern matching)
8. Keyword extraction (frequency-based)
9. Deduplication key generation (SHA-256)

**Models loaded at startup:**
- `distilbert-base-uncased-finetuned-sst-2-english` (HuggingFace pipeline)
- `dbmdz/bert-large-cased-finetuned-conll03-english` (HuggingFace pipeline)
- `en_core_web_sm` (spaCy, NER fallback + general NLP)

**Pattern:** Inference-only, stateless, per-message processing.

**Limitations:**
- Rule-based topic classification (no ML model)
- Rule-based threat scoring (hardcoded weights)
- Rule-based relationship inference (keyword pattern matching)
- No training, no evaluation, no model versioning
- No retraining mechanism
- Single-process consumer (no partitioning parallelism)
- All models loaded into memory regardless of use
- Text truncation at 1200 chars for NER, 1000 for sentiment
- No batching — each article processed individually
- No caching of intermediate results
- Error handling: model failure → silent fallback to neutral/empty

### 1.3 ML Platform (port 8007)

**Responsibility:** ML training platform with feature store, dataset management, model registry, and prediction API.

**Current capabilities:**
- Feature definitions registry (11 types, but only 4 implemented)
- Dataset builder (fetches from Energy Service REST API)
- Train/validation/test splitter (deterministic, stratified)
- DVC dataset versioning
- 5 baseline model wrappers (LogReg, DecisionTree, RandomForest, XGBoost, LightGBM)
- MLflow experiment tracking
- Grid Search, Random Search, Optuna hyperparameter optimization
- SHAP explainability integration
- 5-stage model lifecycle: development → validation → staging → production → archived
- Prediction API with confidence + probabilities + model_version + latency
- Evaluation metrics: classification (accuracy, precision, recall, F1, ROC-AUC, confusion matrix) and regression (MAE, MSE, RMSE, R²)
- Evaluation reporter (JSON + Markdown)

**Current limitations:**
- **Feature store is a thin registry only** — feature definitions are stored but features are computed on-the-fly from raw data. No precomputed feature storage, no online serving, no feature caching.
- **Single dataset type** — only `energy_infrastructure` dataset with `criticality_score` target. Only ports data used as primary entity (with location/org enrichment).
- **Mock data fallback** — synthetic data generation replaces real data when Energy Service is unavailable, creating reproducibility issues.
- **Triggered training only** — no scheduled retraining, no pipeline orchestration.
- **No automated hyperparameter scheduling** — Optuna runs are manual.
- **No model monitoring** — no drift detection, no performance tracking, no prediction logging.
- **No batch inference pipeline** — prediction is single-request only.
- **No distributed training** — all training is single-node, single-process.
- **No experiment comparison** — MLflow runs are logged but no automated comparison dashboard.
- **Feature transform pipeline is duplicated** — `FeatureBuilder.compute_feature()` and `FeatureTransform.transform()` exist separately but overlap in functionality.
- **Feature versions not tracked in training** — the `feature_version` field exists in `model_versions` but isn't populated during training.
- **No feature validation** — no schema checks, range checks, or distribution checks on features.
- **Evaluation is per-run, not continuous** — no evaluation pipeline, no regression testing.
- **No A/B testing infrastructure** — no shadow scoring, canary deployments, or traffic splitting.
- **No model governance** — no approval workflows, compliance metadata, or audit trails.
- **MLflow integration is optional** — training succeeds without MLflow; errors are caught and logged without failing the training run.
- **DVC is called synchronously** — dataset versioning blocks training startup.
- **No online feature store** — features are recomputed per prediction request.
- **Inference API requires pre-encoded features** — no preprocessing pipeline in the prediction path.

### 1.4 Embedding Service (port 8005)

**Responsibility:** Generate and serve text embeddings for semantic search.

**Current state:**
- Model: `BAAI/bge-small-en-v1.5` (384-dim, ONNX via `fastembed`)
- Consumes from `processed_articles` Kafka topic
- Generates embeddings for article title + content
- Stores in PostgreSQL `article_embeddings` table with pgvector HNSW index
- Semantic search via `<=>` cosine distance operator
- Two entry points: REST API (FastAPI) and standalone Kafka consumer
- Model loaded as singleton, lazy initialization

**Limitations:**
- Single embedding model — no multi-model support, no model selection by use case
- No batch embedding API — only single-text embedding
- No embedding caching beyond the database table
- No embedding versioning — model updates would require full re-index
- No cross-encoder re-ranking for search results
- No hybrid fusion at the service level (fusion happens in the RAG engine in Modular API)
- ONNX runtime is single-threaded — no GPU support, no batch inference optimization

### 1.5 Research Directory

**Structure:**
```
research/
├── datasets/fetch_data.py          # Data ingestion from Energy Service
├── notebooks/
│   ├── 01_eda.ipynb                # Exploratory data analysis
│   ├── 02_preprocessing.ipynb      # Sklearn pipelines
│   ├── 03_feature_engineering.ipynb # Ratio, geospatial, polynomial features
│   ├── 04_baseline_models.ipynb    # LogReg, DT, RF
│   ├── 05_model_comparison.ipynb   # + XGBoost, LightGBM
│   ├── 06_hyperparameter_tuning.ipynb # Grid, Random, Optuna
│   ├── 07_explainability.ipynb     # SHAP, permutation importance
│   └── 08_final_model_export.ipynb # XGBoost export + MLflow
├── requirements-research.txt       # Full research stack (mlflow, dvc, shap, optuna, lightgbm, jupyter)
├── artifacts/                      # Empty (populated at runtime)
├── experiments/                    # Empty
├── models/                         # Empty
└── reports/                        # Empty
```

**Current limitations:**
- Single ML problem (energy infrastructure criticality classification)
- No experiment configuration — all parameters hardcoded in notebooks
- No experiment reproducibility — random seeds partially set, notebook cell ordering is fragile
- No dataset versioning — `fetch_data.py` overwrites the dataset each time
- MLflow tracking is file-based (no server) — runs are lost on container restart
- No model comparison across experiments — each notebook run is independent
- Synthetic data fallback creates non-deterministic results (not seeded consistently)
- No validation that exported models load correctly in production
- No integration tests between research output and ML Platform consumption
- Notebooks are linear — changing a cell mid-way invalidates downstream cells

### 1.6 Shared Infrastructure (backend/shared/)

The shared library provides essential ML infrastructure:

| Module | Purpose | ML Relevance |
|--------|---------|-------------|
| `llm/` | LLM client, config, memory, schemas, streaming | Prompt engineering, LLM model management |
| `orchestration/` | Planner, router, reflection, reasoning, confidence, citations | Multi-agent ML pipeline |
| `kafka/` | Topics, producer, consumer, serialization | ML data pipeline |
| `database/` | Pool, transactions, migrations | Feature storage |
| `observability/` | Health, metrics, startup timing | ML model monitoring metrics |
| `resilience/` | Circuit breaker, retry, timeout, bulkhead | ML inference resilience |
| `memory/` | Conversation, execution, agent, compression | ML context management |
| `prompts/` | System prompts for all agent types | LLM-based ML features |

**Key observations:**
- The `kafka/` module has canonical topic definitions — ML Platform should use these for any Kafka-based model serving
- The `observability/` module already defines `ml_inference_latency_seconds` and `llm_*` metrics — the ML Platform should use these
- The `resilience/` module provides circuit breakers and retry logic — critical for ML inference reliability
- The `database/` migrations track all schema changes — ML Platform schema (0004) is one of six migrations

### 1.7 Data Flow Summary

```
Production Data Pipeline (real-time):
  GNews → ingest-service → Kafka(raw_articles)
                          → ML Service (sentiment, NER, topic, threat)
                          → Kafka(processed_articles)
                          → Database Service (PostgreSQL + ES)
                          → Embedding Service (article_embeddings)
                          → Modular API (agents, RAG, search, analytics)

Research Data Pipeline (offline):
  Energy Service API → fetch_data.py → parquet dataset
                                      → notebooks 01-08
                                      → exported models (.joblib)
                                      → ML Platform registry (manual)

ML Training Pipeline (on-demand):
  Energy Service API → DatasetBuilder → DVC tracked parquet
                                       → FeatureBuilder → feature matrix
                                       → ModelTrainer → MLflow run
                                                      → Model Registry
                                                      → Prediction API
```

---

## 2. Target ML Architecture

### 2.1 Design Principles

1. **Research-First** — Every production model starts as a reproducible research experiment
2. **Model-Agnostic** — The platform supports any model type (classification, regression, forecasting, graph, anomaly, transformers)
3. **Reproducible by Default** — Every experiment records dataset version, feature version, parameters, code version, and runtime environment
4. **Progressive Promotion** — Models move through defined lifecycle stages with validation gates
5. **Online/Offline Separation** — Feature computation and model serving cleanly separate batch (offline) from real-time (online)
6. **Observable** — Every prediction is logged, every model is monitored, every drift event is detected
7. **Self-Service** — Researchers can run experiments without infrastructure changes; models can be deployed without engineering handoffs

### 2.2 Target Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         TARGET ML PLATFORM ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                        RESEARCH LAYER                                 │   │
│  │  notebooks/  experiments/  datasets/  features/  models/  reports/    │   │
│  │  evaluations/  artifacts/  benchmarks/                                │   │
│  │  Experiment configs (YAML) | MLflow server | DVC remote | Weights &   │   │
│  │  Biases (optional) | Jupyter Lab | VS Code integration                │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
│  ┌──────────────────────────────▼────────────────────────────────────────┐   │
│  │                       FEATURE STORE                                    │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │Offline Store │  │ Online Store │  │Feature       │  │Feature    │  │   │
│  │  │(Parquet/Duck)│  │(Redis/pgvec) │  │Registry      │  │Validation │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐                 │   │
│  │  │Feature       │  │Feature       │  │Feature       │                 │   │
│  │  │Lineage       │  │Importance    │  │Transforms    │                 │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘                 │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
│  ┌──────────────────────────────▼────────────────────────────────────────┐   │
│  │                      DATASET STORE                                    │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │Versioned     │  │Lineage       │  │Validation    │  │Document   │  │   │
│  │  │Datasets (DVC)│  │Tracking      │  │& Profiling   │  │& Metadata │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐                 │   │
│  │  │Preprocessing │  │Augmentation  │  │Split Registry│                 │   │
│  │  │Pipelines     │  │Transforms    │  │              │                 │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘                 │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
│  ┌──────────────────────────────▼────────────────────────────────────────┐   │
│  │                     TRAINING PIPELINE                                  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │BaseTrainer  │  │AutoML        │  │Cross-        │  │Distributed│  │   │
│  │  │(abstract)   │  │(Optuna/TPE)  │  │Validation    │  │Training   │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐                 │   │
│  │  │Model         │  │Training      │  │Artifact      │                 │   │
│  │  │Selection     │  │Orchestration │  │Storage       │                 │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘                 │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
│  ┌──────────────────────────────▼────────────────────────────────────────┐   │
│  │                    EVALUATION PIPELINE                                 │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │Metrics       │  │Benchmarks    │  │Ablation      │  │Error      │  │   │
│  │  │Library       │  │& Comparison  │  │Studies       │  │Analysis   │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │Drift         │  │Fairness      │  │Robustness    │  │Adversarial│  │   │
│  │  │Baseline      │  │Auditing      │  │Testing       │  │Testing    │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
│  ┌──────────────────────────────▼────────────────────────────────────────┐   │
│  │                      EXPERIMENT TRACKING                               │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │MLflow Server │  │Experiment    │  │Run           │  │Artifact   │  │   │
│  │  │(centralized) │  │Comparison    │  │Dashboard     │  │Browser    │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
│  ┌──────────────────────────────▼────────────────────────────────────────┐   │
│  │                       MODEL REGISTRY                                  │   │
│  │  development → validation → staging → production → archived          │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │Governance   │  │Approval      │  │Canary        │  │Rollback   │  │   │
│  │  │Workflow     │  │Gates         │  │Deployment    │  │Mechanism  │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
│  ┌──────────────────────────────▼────────────────────────────────────────┐   │
│  │                      MODEL DEPLOYMENT                                  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │Online        │  │Batch         │  │Shadow        │  │A/B        │  │   │
│  │  │Inference     │  │Inference     │  │Scoring       │  │Testing    │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │Model         │  │Prediction    │  │Monitoring    │  │Alerting   │  │   │
│  │  │Serving       │  │Logging       │  │& Drift       │  │           │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  └──────────────────────────────┬────────────────────────────────────────┘   │
│                                 │                                            │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  ML Service   │      │   Energy Service  │      │   Modular API    │
│  (NLP inf)    │      │   (domain data)   │      │   (gateway)      │
└───────────────┘      └──────────────────┘      └──────────────────┘
```

### 2.3 Component Catalog

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **Research Layer** | Notebook experiments, config-driven training, MLflow server | Jupyter + YAML configs + centralized MLflow |
| **Feature Store** | Offline/online feature computation, serving, validation | `ml.feature_definitions` + Redis/Parquet + transform library |
| **Dataset Store** | Versioned, validated, documented datasets | DVC + `ml.datasets` + Great Expectations |
| **Training Pipeline** | Generic model training with pluggable trainers | `BaseTrainer` ABC + task-specific trainers |
| **Evaluation Pipeline** | Multi-metric evaluation, benchmarks, drift baselines | sklearn metrics + custom evaluators + reporting |
| **Experiment Tracking** | Centralized experiment management | MLflow server (PostgreSQL-backed) |
| **Model Registry** | Lifecycle management, governance, deployment | `ml.model_versions` + approval workflow |
| **Deployment** | Online + batch inference, canary, A/B testing | ModelPredictor + BatchPredictor + shadow scoring |

---

## 3. Research Infrastructure

### 3.1 Directory Structure

```
research/
├── configs/                          # YAML experiment configs (version-controlled)
│   ├── experiments/
│   │   ├── energy_criticality_v1.yaml
│   │   ├── disruption_risk_v1.yaml
│   │   └── commodity_forecast_v1.yaml
│   ├── datasets/
│   │   ├── energy_infrastructure_v1.yaml
│   │   └── news_articles_v1.yaml
│   └── models/
│       ├── classification.yaml
│       ├── regression.yaml
│       └── forecasting.yaml
│
├── datasets/                         # Data ingestion and versioning
│   ├── fetch_data.py                 # Current: Energy Service → parquet
│   ├── loaders/                      # New: modular data loaders
│   │   ├── __init__.py
│   │   ├── base.py                   # DataLoader ABC
│   │   ├── energy_loader.py          # Energy Service entities
│   │   ├── news_loader.py            # Kafka/PostgreSQL news articles
│   │   ├── signal_loader.py          # Disruption signals
│   │   ├── price_loader.py           # Commodity prices
│   │   └── synthetic_loader.py       # Controlled synthetic generation
│   ├── validators/                    # Dataset validation
│   │   ├── __init__.py
│   │   ├── schema.py                 # Column type/schema validation
│   │   ├── stats.py                  # Distribution statistics
│   │   └── expectations.py           # Great Expectations suites
│   └── transforms/                   # Dataset-level transforms
│       ├── __init__.py
│       ├── cleaners.py               # Missing value, outlier handling
│       ├── normalizers.py            # Scaling, encoding
│       └── augmenters.py             # Data augmentation
│
├── features/                         # Feature definitions and experiments
│   ├── definitions/                  # Feature specs (version-controlled)
│   │   ├── energy_features.yaml
│   │   ├── news_features.yaml
│   │   └── temporal_features.yaml
│   ├── notebooks/                    # Feature exploration notebooks
│   │   ├── feature_importance.ipynb
│   │   └── feature_correlation.ipynb
│   └── benchmarks/                   # Feature computation benchmarks
│       └── compute_latency.ipynb
│
├── notebooks/                        # Structured experiment notebooks
│   ├── 01_eda/                       # EDA by domain
│   │   ├── energy_eda.ipynb
│   │   ├── supply_chain_eda.ipynb
│   │   └── news_eda.ipynb
│   ├── 02_preprocessing/             # Preprocessing experiments
│   │   ├── scaling_comparison.ipynb
│   │   └── encoding_strategies.ipynb
│   ├── 03_feature_engineering/       # Feature engineering experiments
│   │   ├── geospatial_features.ipynb
│   │   └── temporal_features.ipynb
│   ├── 04_baselines/                 # Baseline models by problem type
│   │   ├── classification_baselines.ipynb
│   │   ├── regression_baselines.ipynb
│   │   └── forecasting_baselines.ipynb
│   ├── 05_model_comparison/          # Model comparison studies
│   │   └── comparison.ipynb
│   ├── 06_hyperparameter_tuning/     # Tuning studies
│   │   └── tuning.ipynb
│   ├── 07_explainability/            # Model interpretation
│   │   └── explainability.ipynb
│   └── 08_production_export/         # Final model packaging
│       └── export.ipynb
│
├── experiments/                      # MLflow experiment artifacts
│   ├── mlruns/                       # Local MLflow artifacts (gitignored)
│   └── registry/                     # Registered model versions
│
├── models/                           # Exported models by task
│   ├── energy_criticality/           # Task-specific subdirectories
│   │   ├── v1/
│   │   │   ├── model.joblib
│   │   │   ├── preprocessing.joblib
│   │   │   ├── metadata.json
│   │   │   └── evaluation.json
│   │   └── v2/
│   ├── disruption_risk/
│   ├── commodity_forecast/
│   └── supply_gap/
│
├── evaluations/                      # Stored evaluation results
│   ├── benchmarks/                   # Benchmark comparison results
│   ├── ablation/                     # Ablation study results
│   └── drift_baselines/              # Drift detection baselines
│
├── reports/                          # Generated evaluation reports
│   ├── html/                         # HTML reports
│   ├── pdf/                          # PDF exports
│   └── md/                           # Markdown summaries
│
├── artifacts/                        # Generated plots, figures
│   ├── eda/                          # EDA plots
│   ├── tuning/                       # Hyperparameter tuning plots
│   ├── explainability/              # SHAP, permutation plots
│   └── monitoring/                   # Drift monitoring plots
│
├── benchmarks/                       # Benchmarking infrastructure
│   ├── model_benchmarks.py           # Standardized benchmark runner
│   ├── datasets/                     # Benchmark datasets
│   └── results/                      # Stored benchmark results
│
├── requirements-research.txt         # Existing: full research stack
├── README.md                         # Existing: usage instructions
└── pyproject.toml                    # Research environment config
```

### 3.2 Config-Driven Experiment Workflow

Every experiment is defined by a YAML config:

```yaml
# configs/experiments/disruption_risk_v1.yaml
experiment:
  name: disruption_risk_prediction
  type: classification
  mlflow_experiment: disruption_risk

dataset:
  name: energy_infrastructure
  version: 3
  target_column: disruption_risk_score
  split:
    train: 0.7
    validation: 0.15
    test: 0.15
    stratify: true
    random_seed: 42

features:
  version: 2
  include:
    - geopolitical_tension_score
    - regional_conflict_proximity
    - sanctions_exposure
    - port_congestion_pct
    - price_volatility_30d
    - historical_disruption_count
  exclude: []

model:
  type: xgboost
  params:
    n_estimators: 200
    max_depth: 8
    learning_rate: 0.1
    subsample: 0.8
    colsample_bytree: 0.8
  tuning:
    enabled: true
    method: optuna
    n_trials: 50
    timeout_minutes: 30

evaluation:
  metrics:
    - accuracy
    - precision_weighted
    - recall_weighted
    - f1_weighted
    - roc_auc
  cross_validation:
    folds: 5
    stratified: true
  ablation:
    enabled: true
    feature_groups: ["temporal", "geospatial", "entity"]
  explainability:
    enabled: true
    methods: ["shap", "permutation"]

deployment:
  auto_promote: false
  validation_threshold:
    accuracy: 0.85
    f1_weighted: 0.80
```

### 3.3 Experiment Lifecycle

```
Config Creation → Dataset Assembly → Feature Computation → Training → Evaluation → Registration → Promotion
      │                │                    │                  │           │              │              │
      │                ▼                    │                  │           │              │              │
      │          DVC versioned       Feature store        MLflow run    MLflow run    Model registry  Stage: staging
      │          dataset tracked      version tracked     logged        logged        registered
      ▼                                                               ▼
  Git committed                                                    Report generated
```

---

## 4. Dataset Infrastructure

### 4.1 Dataset Lifecycle

```
Download → Validate → Clean → Normalize → Version → Store → Index → Document → Register → Consume
   │          │         │         │           │        │       │        │           │          │
   │          │         │         │           │        │       │        │           │          │
   ▼          ▼         ▼         ▼           ▼        ▼       ▼        ▼           ▼          ▼
API/DVC    Schema     Missing    Scaling     DVC      S3/      DVC      README     ml.datasets  Training
Fetcher    Checks     Values     Encoding    Add      Local    Push     Generated  Table       Pipeline
```

### 4.2 Components

**Downloaders:**
- `EnergyServiceLoader` — Fetches 14 entity types from Energy Service API
- `NewsArticleLoader` — Fetches processed articles from PostgreSQL
- `SignalLoader` — Fetches disruption signals from `energy.disruption_signals`
- `PriceLoader` — Fetches commodity prices from `energy.commodity_prices`
- `SyntheticLoader` — Controlled synthetic data generation with seeded RNG

**Validators:**
- Schema validation (column presence, data types, null ratios)
- Distribution checks (min/max/mean/std per column, compared to historical baselines)
- Uniqueness checks (primary key, dedup key)
- Referential integrity (foreign key relationships)
- Great Expectations suite (configurable expectations per dataset)

**Transformers:**
- Missing value imputation (mean, median, mode, constant, model-based)
- Outlier detection (IQR, Z-score, IsolationForest, DBSCAN)
- Normalization (StandardScaler, MinMaxScaler, RobustScaler, QuantileTransformer)
- Encoding (OneHot, Label, Target, Frequency, Binary, Ordinal)
- Temporal features (hour/day/month/quarter, lag, rolling window, differencing)
- Geospatial features (distance to chokepoints, region clustering, country risk score)

**Versioning:**
- DVC for data file versioning (`.dvc` files committed to git, data pushed to remote storage)
- Each dataset version has a unique `(name, version)` composite key in `ml.datasets`
- Version metadata includes: hash, schema, row count, column stats, creation timestamp, git commit
- DVC remote configurable: local, S3, GCS, HDFS

**Storage:**
- Local: `data/datasets/{name}/v{version}/` (parquet files)
- Remote: DVC remote (configurable S3/GCS/local path)
- Metadata: `ml.datasets` table in PostgreSQL
- Lineage: `ml.dataset_lineage` table (parent dataset, transform applied, parameters)

### 4.3 Dataset Registry

```sql
-- Target schema extension to ml.datasets
CREATE TABLE ml.dataset_lineage (
    id BIGSERIAL PRIMARY KEY,
    dataset_uuid UUID NOT NULL REFERENCES ml.datasets(uuid),
    parent_dataset_uuid UUID REFERENCES ml.datasets(uuid),
    transform_name VARCHAR(100),
    transform_params JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ml.dataset_profiles (
    id BIGSERIAL PRIMARY KEY,
    dataset_uuid UUID NOT NULL REFERENCES ml.datasets(uuid),
    profile_json JSONB NOT NULL,        -- Great Expectations profile
    row_count INTEGER,
    column_count INTEGER,
    null_ratios JSONB,
    distributions JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. Feature Store

### 5.1 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        FEATURE STORE                              │
│                                                                   │
│  ┌─────────────────────┐          ┌──────────────────────────┐   │
│  │   Feature Registry   │          │    Feature Computation    │   │
│  │   (PostgreSQL)       │          │    (Python transforms)    │   │
│  │                      │          │                           │   │
│  │  - name              │          │  IdentityTransform       │   │
│  │  - version           │          │  AggregateTransform      │   │
│  │  - feature_type      │─────┬───▶│  LagTransform            │   │
│  │  - transform_config  │     │    │  RatioTransform          │   │
│  │  - source_feature    │     │    │  GeospatialTransform     │   │
│  │  - is_active         │     │    │  RollingWindowTransform  │   │
│  │  - owner             │     │    │  EmbeddingTransform      │   │
│  │  - created_at        │     │    │  CustomTransform         │   │
│  └──────────────────────┘     │    └──────────────────────────┘   │
│                                │                                   │
│  ┌─────────────────────┐      │    ┌──────────────────────────┐   │
│  │  Offline Store       │      │    │  Online Store            │   │
│  │  (Parquet/DuckDB)    │      │    │  (Redis/pgvector)        │   │
│  │                     │      │    │                          │   │
│  │  - Batch compute     │      └───▶│  - Real-time serving    │   │
│  │  - Training data     │           │  - Cached features      │   │
│  │  - Backfill          │           │  - TTL-based eviction   │   │
│  └──────────────────────┘           └──────────────────────────┘   │
│                                                                   │
│  ┌─────────────────────┐          ┌──────────────────────────┐   │
│  │  Feature Validation  │          │  Feature Lineage          │   │
│  │                     │          │                          │   │
│  │  - Schema checks    │          │  - Source table/column   │   │
│  │  - Range checks     │          │  - Transform applied     │   │
│  │  - Distribution     │          │  - Dependent features    │   │
│  │  - Drift detection  │          │  - Used by models        │   │
│  └──────────────────────┘          └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Feature Types

| Type | Description | Storage | Computation |
|------|-------------|---------|-------------|
| `numerical` | Continuous values | float8, Parquet | Identity, Aggregate, Lag, Ratio, Rolling |
| `categorical` | Discrete values | text, Parquet | Identity, Frequency encoding |
| `boolean` | True/false | bool, Parquet | Identity, Threshold |
| `timestamp` | DateTime values | timestamptz, Parquet | Hour, Day, Month, Quarter extraction |
| `geospatial` | Lat/lng derived | float8, Parquet | Haversine distance, region cluster |
| `entity_statistics` | Entity-level aggregates | float8, Parquet | GroupBy, Count, Mean, Sum |
| `relationship_statistics` | Graph aggregates | float8, Parquet | Degree, Centrality, PageRank |
| `historical_capacity` | Time-series aggregates | float8, Parquet | Rolling window, EWMA, Trend |
| `infrastructure` | Infrastructure metadata | text/float8, Parquet | Asset type, Status, Criticality |
| `embedding_reference` | Text embedding vectors | vector(384), pgvector | Text embed, Cosine sim |
| `graph_placeholder` | Graph-structured features | JSONB, Parquet | Node2Vec, GraphSAGE |

### 5.3 Online Feature Serving

**Target:**
```python
# Feature Store API
class FeatureStore:
    async def get_online_features(
        self,
        entity_type: str,
        entity_uuids: list[str],
        feature_names: list[str]
    ) -> pd.DataFrame: ...

    async def get_offline_features(
        self,
        dataset_name: str,
        dataset_version: int,
        feature_names: list[str]
    ) -> pd.DataFrame: ...

    async def compute_and_store(
        self,
        feature_name: str,
        entity_type: str,
        entity_uuids: list[str]
    ) -> None: ...
```

### 5.4 Feature Lineage Tracking

```sql
CREATE TABLE ml.feature_lineage (
    id BIGSERIAL PRIMARY KEY,
    feature_uuid UUID NOT NULL REFERENCES ml.feature_definitions(uuid),
    source_table TEXT NOT NULL,       -- e.g., 'energy.ports'
    source_column TEXT NOT NULL,      -- e.g., 'throughput_mtpa'
    transform_name TEXT NOT NULL,
    transform_params JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ml.feature_importance (
    id BIGSERIAL PRIMARY KEY,
    model_version_uuid UUID NOT NULL REFERENCES ml.model_versions(uuid),
    feature_name TEXT NOT NULL,
    importance_score FLOAT NOT NULL,
    importance_method TEXT NOT NULL,  -- 'gain', 'permutation', 'shap'
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Training Infrastructure

### 6.1 BaseTrainer Framework

```python
class BaseTrainer(ABC):
    """Abstract base for all model trainers."""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def build_model(self) -> Any:
        ...

    @abstractmethod
    async def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame | None = None,
        y_val: pd.Series | None = None
    ) -> TrainingResult:
        ...

    @abstractmethod
    async def predict(
        self,
        model: Any,
        X: pd.DataFrame
    ) -> np.ndarray:
        ...

    @abstractmethod
    async def predict_proba(
        self,
        model: Any,
        X: pd.DataFrame
    ) -> np.ndarray | None:
        ...
```

### 6.2 Task-Specific Trainers

| Trainer | Base Task | Supported Models |
|---------|-----------|-----------------|
| `ClassificationTrainer` | Classification | LogReg, DT, RF, XGBoost, LightGBM, SGD, SVM |
| `RegressionTrainer` | Regression | LinearRegression, Ridge, Lasso, RF, XGBoost, LightGBM |
| `ForecastingTrainer` | Time-series forecasting | ARIMA, Prophet, LSTM (via darts), LightGBM with lags |
| `RankingTrainer` | Learning to rank | LambdaRank, XGBoost ranker |
| `GraphTrainer` | Graph ML | Node2Vec, GraphSAGE, GCN (via PyG) |
| `AnomalyTrainer` | Anomaly detection | IsolationForest, LOF, OneClassSVM, AE |
| `TransformerTrainer` | Text/sequence | BERT, RoBERTa, DistilBERT (via transformers) |

### 6.3 Training Pipeline

```python
async def training_pipeline(config: TrainingConfig) -> TrainingResult:
    # 1. Load dataset
    dataset = await DatasetStore.get(config.dataset_name, config.dataset_version)

    # 2. Load features
    feature_matrix = await FeatureStore.get_offline_features(
        dataset.name, dataset.version, config.feature_names
    )

    # 3. Split
    X_train, X_val, X_test, y_train, y_val, y_test = DatasetSplitter(
        test_size=config.test_size,
        val_size=config.val_size,
        random_seed=config.random_seed
    ).split(feature_matrix, config.target_column)

    # 4. Build preprocessing pipeline
    preprocessor = build_preprocessing_pipeline(config.preprocessing)

    # 5. Create trainer
    trainer = get_trainer(config.model_type)(config)

    # 6. Train with MLflow tracking
    with mlflow.start_run() as run:
        mlflow.log_params(config.to_dict())
        model = await trainer.build_model()
        result = await trainer.train(model, X_train, y_train, X_val, y_val)

        # 7. Evaluate
        eval_result = await evaluate(trainer, model, X_test, y_test)

        # 8. Log artifacts
        mlflow.log_metrics(eval_result.metrics)
        mlflow.log_artifact(...)

        # 9. Register model
        registry.log_model_version(
            name=config.model_name,
            model=model,
            metrics=eval_result.metrics,
            dataset_version=config.dataset_version,
            feature_version=config.feature_version,
            mlflow_run_id=run.info.run_id
        )

    return result
```

---

## 7. Evaluation Infrastructure

### 7.1 Metrics Library

```
Classification:
├── accuracy, precision, recall, f1 (macro/weighted/per-class)
├── roc_auc, pr_auc
├── log_loss, brier_score
├── confusion_matrix, classification_report
├── matthews_corrcoef, cohen_kappa

Regression:
├── mae, mse, rmse, r2, mape, smape
├── explained_variance, max_error, median_absolute_error

Forecasting:
├── mae, mse, rmse, mape, smape
├── mda (mean directional accuracy)
├── mase (mean absolute scaled error)
├── forecast_bias

Ranking:
├── ndcg@k, map@k, mrr
├── precision@k, recall@k

Graph:
├── accuracy, f1 (node classification)
├── ari, nmi (community detection)
├── hits@k, mrr (link prediction)

Anomaly:
├── precision, recall, f1 (at threshold)
├── auc_pr, auc_roc (with variable threshold)
├── average_precision
```

### 7.2 Evaluation Pipeline

```
Training Output
      │
      ▼
┌─────────────────┐
│  Metrics         │  ← sklearn/forecasting/ranking metrics
│  Computation     │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Cross-          │  ← K-fold, Stratified, Group, TimeSeriesSplit
│  Validation      │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Hyperparameter  │  ← Grid, Random, Optuna, Hyperopt
│  Tuning          │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Ablation        │  ← Feature groups, model components
│  Studies         │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Error Analysis  │  ← Confusion matrix, residuals, stratified error
│                  │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Explainability  │  ← SHAP, Permutation, LIME, Partial dependence
│                  │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Drift Baseline  │  ← Reference distribution, PSI, KS test
│                  │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Benchmark       │  ← Cross-model, cross-run comparison
│  Comparison      │
└────────┬─────────┘
         │
         ▼
    Report + Registry
```

---

## 8. Experiment Tracking

### 8.1 MLflow Server Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     CENTRALIZED MLFLOW SERVER                   │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Tracking  │  │ Registry │  │ Artifacts│  │ Experiments  │  │
│  │ Server    │  │ Server   │  │ Store    │  │ UI           │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
│       │              │             │               │          │
│       ▼              ▼             ▼               ▼          │
│  PostgreSQL      PostgreSQL    S3/Local         Browser       │
│  (mlflow_*)      (model_reg)   (artifacts)                    │
└────────────────────────────────────────────────────────────────┘
```

### 8.2 Experiment Record Schema

Each experiment run records:

```
EXPERIMENT RUN
├── dataset_version: int              → ml.datasets.version
├── feature_version: int              → ml.feature_definitions.version
├── parameters: dict                  → model hyperparameters
├── metrics: dict[str, float]         → evaluation metrics
├── artifacts: list[str]              → model file, plots, reports
├── plots: list[str]                  → PNG/SVG plots (confusion matrix, SHAP, curves)
├── model: BinaryArtifact             → serialized model (joblib/ONNX/pt)
├── notes: str                        → researcher notes
├── runtime_seconds: float            → training duration
├── git_commit: str                   → HEAD commit hash
├── git_branch: str                   → active branch
├── environment: dict                 → Python packages + versions
├── mlflow_run_id: str                → MLflow identifier
└── status: str                       → running/completed/failed
```

---

## 9. Model Registry

### 9.1 Lifecycle Stages

```
                                          ┌──────────┐
               Training ──────────────────▶│Development│
                   │                       └─────┬─────┘
                   │                             │
                   │                             ▼
                   │                       ┌──────────┐
                   │                       │Validation │ ◀── Approval gate #1
                   │                       └─────┬─────┘
                   │                             │
                   │                             ▼
                   │                       ┌──────────┐
                   │                       │  Staging  │ ◀── Shadow deployment
                   │                       └─────┬─────┘
                   │                             │
                   │                             ▼
                   │                       ┌──────────┐
                   │                       │Production│ ◀── Approval gate #2
                   │                       └────┬─────┘
                   │                            │
                   │                            ▼
                   │                       ┌──────────┐
                   └──────────────────────▶│ Archived  │
                                           └──────────┘
```

### 9.2 Stage Transition Rules

| From | To | Gate | Automation |
|------|-----|------|------------|
| Development | Validation | Auto: metrics threshold | `promote_to_validation()` checks metric thresholds |
| Validation | Staging | Approval: manual review | `promote_to_staging()` requires `approved_by` |
| Staging | Production | Approval: shadow test results | Shadow scoring must pass drift/success thresholds |
| Any | Archived | Manual or auto: stale | Auto-archive production after N days without use |

**Promotion API:**
```python
class ModelRegistry:
    async def promote(
        self,
        model_uuid: str,
        target_stage: str,
        approved_by: str | None = None,
        validation_results: dict | None = None
    ) -> bool: ...

    async def can_promote(
        self,
        model_uuid: str,
        target_stage: str
    ) -> PromotionGate:
        """Check if model meets all gates for promotion to target stage."""
        ...
```

### 9.3 Governance Metadata

```sql
CREATE TABLE ml.model_governance (
    id BIGSERIAL PRIMARY KEY,
    model_version_uuid UUID NOT NULL REFERENCES ml.model_versions(uuid),
    approved_by VARCHAR(255),
    approved_at TIMESTAMPTZ,
    approval_notes TEXT,
    review_url VARCHAR(500),
    compliance_tags TEXT[],          -- 'gdpr', 'soc2', 'internal'
    risk_classification VARCHAR(50),  -- 'low', 'medium', 'high', 'critical'
    bias_audit_url VARCHAR(500),
    fairness_metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ml.model_audit_log (
    id BIGSERIAL PRIMARY KEY,
    model_version_uuid UUID NOT NULL REFERENCES ml.model_versions(uuid),
    action VARCHAR(100) NOT NULL,     -- 'created', 'promoted', 'rolled_back', 'archived'
    from_stage VARCHAR(50),
    to_stage VARCHAR(50),
    performed_by VARCHAR(255),
    reason TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 10. Integration Architecture

### 10.1 Integration with ML Service

```
ML Service (port 8002)                          ML Platform (port 8007)
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                      │                       │
│  NLP Inference (prod) │                      │  Model Training (off) │
│  Sentiment (DistilBERT│                      │  Model Registry       │
│  NER (BERT)           │    No direct link     │  Feature Store        │
│  Topic (rule-based)   │◀─────────────────────│  Dataset Store         │
│  Threat (rule-based)  │     (future)          │                       │
│                       │                      │  ML Platform trains   │
│  ML Service should    │                      │  improved models for  │
│  eventually consume   │                      │  sentiment/NER/topic  │
│  models from ML       │                      │  and registers them   │
│  Platform registry    │                      │  for ML Service to    │
│                       │                      │  download & use       │
└───────────────────────┘                      └───────────────────────┘
```

**Integration mechanism (future):**
- ML Platform trains and registers NLP models (finetuned BERT for domain-specific sentiment/NER/topic)
- ML Service polls registry for new model versions on startup
- Model artifacts downloaded from ML Platform's artifact store
- No duplicate training — ML Service is pure inference consumer

### 10.2 Integration with Energy Service

```
Energy Service (port 8006)                     ML Platform (port 8007)
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                      │                       │
│  14 entity tables     │──── REST API ───────▶│  DatasetBuilder       │
│  (data source)        │                      │  FeatureBuilder       │
│                       │◀───── /predict ──────│  Prediction API       │
│  MLBridge             │                      │                       │
│  (calls ML Platform   │                      │  Trains models for:   │
│   with features from  │                      │  - disruption risk    │
│   signals/congestion) │                      │  - supply gap         │
│                       │                      │  - demand forecasting │
│  Digital Twin         │                      │  - commodity prices   │
│  (simulation engine)  │                      │  - supplier risk      │
│                       │                      │                       │
│  Procurement Engine   │                      │  Registers models in  │
│  (optimization)       │                      │  registry → served    │
│                       │                      │  via prediction API   │
└───────────────────────┘                      └───────────────────────┘
```

**Integration points:**
1. **Data source** — Energy Service exposes all entity data via REST
2. **Feature source** — Energy tables accessed directly via shared PostgreSQL
3. **Prediction consumer** — `MLBridge` calls ML Platform for disruption risk predictions
4. **Digital Twin** — Simulation runs can request ML predictions for scenario impact
5. **Procurement** — Compatibility scores can be enhanced with ML models

### 10.3 Integration with Digital Twin

```
Digital Twin                                   ML Platform
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                      │                       │
│  Scenario Templates   │───── scenario params─▶│  Impact Prediction   │
│  Simulation Runs      │◀──── predicted impact─│  (regression model)  │
│                       │                       │                       │
│  Flow States          │───── features ───────▶│  Bottleneck          │
│  (utilization_pct,    │                       │  Prediction           │
│   supply_gap_bpd)     │◀──── anomaly score ───│  (anomaly detection)  │
│                       │                       │                       │
│  Network Graph        │───── graph data ─────▶│  Graph ML             │
│  (entity relationships)│                      │  (link prediction)    │
│                       │                       │                       │
└───────────────────────┘                      └───────────────────────┘
```

### 10.4 Integration with Procurement

```
Procurement Engine                             ML Platform
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                      │                       │
│  Supplier Intel       │───── features ───────▶│  Supplier Risk       │
│  (reliability,        │                       │  Prediction           │
│   sanctions_exposure) │◀──── risk_score ──────│  (classification)    │
│                       │                       │                       │
│  Route Costs          │───── features ───────▶│  Route Cost           │
│  (distance, risk,     │                       │  Prediction           │
│   tariffs)            │◀──── predicted_cost ──│  (regression)         │
│                       │                       │                       │
│  SPR Optimization     │───── demand params ──▶│  Demand Forecasting   │
│  (release strategy)   │◀──── forecast ────────│  (time-series)        │
│                       │                       │                       │
└───────────────────────┘                      └───────────────────────┘
```

### 10.5 Integration with AI Agents

```
AI Agents                                      ML Platform
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                      │                       │
│  IntelligenceAgent    │                       │                       │
│  (uses 25 tools)      │── tool call ────────▶│  /api/v1/ml/predict  │
│                       │◀── prediction ───────│                       │
│  PredictionAgent      │                       │  Model Registry      │
│  (stub - future)      │                       │  Feature Store       │
│                       │── RAG context ──────▶│  Embedding Service    │
│  ResearchAgent        │                       │  (via modular API)   │
│  (search/semantic)    │                       │                       │
│                       │                       │                       │
└───────────────────────┘                      └───────────────────────┘
```

**Key integration rule:** Agents never call ML Platform directly. All ML predictions go through the Modular API gateway. The tool registry provides ML prediction as a tool that agents can invoke.

### 10.6 Integration with Hybrid RAG

```
RAG Engine                                     ML Platform
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                       │                       │
│  Retriever             │── dense ────────────▶│  Embedding Service    │
│  (hybrid search)       │◀── vectors ──────────│  (managed by ML       │
│                        │                       │   Platform in future)│
│  Dense: embedding svc  │                       │                       │
│  Sparse: ES BM25       │── re-rank ──────────▶│  Cross-encoder       │
│  KG: entity graph      │◀── scores ──────────│  (future model)      │
│                        │                       │                       │
│  RRF Fusion            │                       │  ML Platform tracks  │
│                        │                       │  RAG quality metrics │
└───────────────────────┘                       │  (NDCG, MRR)          │
                                                 └───────────────────────┘
```

### 10.7 Integration with Kafka Pipeline

```
Kafka Topics                                     ML Platform
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                       │                       │
│  raw_articles         │── consumed by ───────▶│  ML Service (NLP)    │
│  processed_articles   │── consumed by ───────▶│  Embedding Service    │
│                       │                       │                       │
│  commodity_prices     │── consumed by ───────▶│  Feature Ingester     │
│  disruption_signals   │                       │  (stores in feature   │
│  ais_signals          │                       │   store for training) │
│  sanctions_updates    │                       │                       │
│                       │── future ───────────▶│  Prediction Consumer  │
│  prediction_requests  │                       │  (batch inference)    │
│  prediction_results   │◀── published by ──────│                       │
│                       │                       │                       │
└───────────────────────┘                      └───────────────────────┘
```

### 10.8 Integration with Database

```
PostgreSQL (shared)                              ML Platform
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                       │                       │
│  public schema        │                       │  Reads via asyncpg    │
│  ├── processed_...    │── training data ─────▶│  DatasetBuilder       │
│  ├── article_embedd...│                       │  FeatureBuilder       │
│  └── users            │                       │                       │
│                       │                       │  Writes via asyncpg   │
│  energy schema        │── feature data ──────▶│  FeatureRegistry      │
│  ├── 14 entity tables │                       │  ModelRegistry        │
│  ├── risk_scores      │── prediction results ─│  Prediction logging   │
│  ├── disruption_sig.. │                       │                       │
│  └── flow_states      │                       │                       │
│                       │                       │  Schema: ml.*         │
│  ml schema            │          ─────────────│  feature_definitions  │
│  ├── feature_defs     │          ─────────────│  datasets             │
│  ├── datasets         │          ─────────────│  model_versions       │
│  └── model_versions   │          ─────────────│  predictions          │
│                       │                       │                       │
└───────────────────────┘                      └───────────────────────┘
```

### 10.9 No Duplicate Logic Principle

| Capability | Owner | Shared via | Not Duplicated In |
|-----------|-------|------------|-------------------|
| Entity normalization | `backend/shared/entity_normalization.py` | Shared import | Any service |
| Kafka config/topics | `backend/shared/kafka/topics.py` | Shared import | Any service |
| Database pool | `backend/shared/database/pool.py` | Shared import | Any service |
| Resilience patterns | `backend/shared/resilience/` | Shared import | Any service |
| Observability metrics | `backend/shared/observability/` | Shared import | Any service |
| Feature transforms | `ML Platform feature_store/` | Import or package | ML Service |
| Model prediction | `ML Platform inference/` | REST API call | Energy Service |
| Embedding generation | `Embedding Service` | REST API call | ML Platform |
| Data fetching | `ML Platform datasets/` | REST API call | Research notebooks |
| Experiment tracking | `ML Platform` | MLflow server | Research notebooks |

---

## 11. Research Models

### 11.1 Identified Research Pipelines

| Pipeline | Problem Type | Target | Data Sources | Priority |
|----------|-------------|--------|-------------|----------|
| **Energy Criticality** | Multiclass classification (4 classes) | `criticality_score` | Entity tables, locations, organizations | Existing |
| **Disruption Risk** | Binary classification / regression | `disruption_risk_score` | Signals, entity risk profiles, events | High |
| **Commodity Price** | Time-series forecasting | `price` (Brent, WTI, etc.) | `commodity_prices`, historical events | High |
| **Supply Gap** | Regression / forecasting | `supply_gap_bpd` | `flow_states`, `digital_twin_runs` | High |
| **Supplier Risk** | Classification / scoring | `supplier_reliability` | `supplier_intelligence`, sanctions | Medium |
| **Demand Forecast** | Time-series forecasting | `daily_demand_bpd` | `demand_profiles`, `capacity_history` | Medium |
| **Scenario Severity** | Regression | `economic_impact_usd` | `digital_twin_runs`, scenario params | Medium |
| **Route Optimization** | Regression / ranking | `route_risk_score` | `route_costs`, shipping routes | Medium |
| **Graph Prediction** | Link prediction / node classification | `relationship_type` | `entity_relationships`, `network_edges` | Low |
| **Anomaly Detection** | Unsupervised | `anomaly_score` | `flow_states`, utilization patterns | Low |
| **Port Congestion** | Time-series forecasting | `congestion_pct` | `port_congestion`, `ais_positions` | Low |
| **LLM Evaluation** | Benchmarking | `response_quality` | Agent responses, expert annotations | Ongoing |

### 11.2 Infrastructure Support Matrix

| Feature | Energy Criticality | Disruption Risk | Commodity Price | Supply Gap | Supplier Risk | Demand Forecast |
|---------|-------------------|----------------|----------------|------------|---------------|-----------------|
| Dataset builder | ✅ Existing | ✅ Easy | ✅ Easy | ✅ Easy | ✅ Easy | ✅ Easy |
| Feature transforms | ✅ | ✅ | Need time-series | Need time-series | ✅ | Need time-series |
| Model trainers | Classification | Classification | Forecasting | Regression | Classification | Forecasting |
| Evaluation metrics | ✅ | ✅ | Need forecasting | ✅ | ✅ | Need forecasting |
| CV strategy | Stratified KFold | Stratified KFold | TimeSeriesSplit | KFold | Stratified KFold | TimeSeriesSplit |
| Explainability | SHAP | SHAP | SHAP (partial) | SHAP | SHAP | Partial dependence |
| Drift detection | Feature | Feature + target | Prediction error | Prediction error | Feature | Prediction error |
| Online inference | ✅ | ✅ | Periodic | ✅ | ✅ | Periodic |

---

## 12. Gap Analysis

### 12.1 Current vs Target

| Dimension | Current State | Target State | Delta |
|-----------|--------------|--------------|-------|
| **Feature Store** | Thin registry, on-the-fly compute | Offline + online store, versioned, validated | CRITICAL |
| **Dataset Management** | Single dataset, single loader | Multi-dataset, pluggable loaders, validation, lineage | LARGE |
| **Training Pipeline** | One trainer config, manual trigger | Generic framework, scheduled, distributed | LARGE |
| **Evaluation** | Per-run metrics, classification + regression | Full suite: ablation, benchmarks, drift baselines | MEDIUM |
| **Experiment Tracking** | Optional MLflow, file-based | Centralized MLflow server, mandatory | MEDIUM |
| **Model Registry** | 5 stages, no gates | Stages + approval gates + audit log | MEDIUM |
| **Model Deployment** | Single prediction endpoint | Online + batch + shadow + A/B | LARGE |
| **Model Monitoring** | None | Drift detection, prediction logging, alerting | CRITICAL |
| **Research Integration** | Manual export from notebooks | Config-driven, automated registration | LARGE |
| **NLP Models** | Off-the-shelf HuggingFace | Domain-finetuned, registry-served | MEDIUM |
| **Infrastructure** | Single-node training | Distributed training support | LOW |
| **Governance** | None | Approval workflows, compliance metadata, audit | MEDIUM |

### 12.2 Missing Schemas

| Schema | Status | Priority |
|--------|--------|----------|
| `ml.feature_lineage` | Missing | MEDIUM |
| `ml.feature_importance` | Missing | MEDIUM |
| `ml.dataset_lineage` | Missing | LOW |
| `ml.dataset_profiles` | Missing | LOW |
| `ml.model_governance` | Missing | MEDIUM |
| `ml.model_audit_log` | Missing | MEDIUM |
| `ml.drift_baselines` | Missing | HIGH |
| `ml.prediction_log` | Missing | HIGH |
| `ml.batch_predictions` | Missing | LOW |

### 12.3 Missing Abstractions

| Abstraction | Missing | Priority |
|-------------|---------|----------|
| `DataLoader` base class | ✅ Exists (ABC in `datasets/loader.py`) | — |
| `FeatureTransform` base class | ✅ Exists (ABC in `feature_store/transforms.py`) | — |
| `BaseTrainer` | ❌ Missing | HIGH |
| `BaseEvaluator` | ❌ Missing | MEDIUM |
| `BaseDatasetValidator` | ❌ Missing | MEDIUM |
| `OnlineFeatureStore` | ❌ Missing | HIGH |
| `BatchPredictor` | ❌ Missing | MEDIUM |
| `ModelMonitor` | ❌ Missing | HIGH |
| `DriftDetector` | ❌ Missing | HIGH |
| `ExperiementConfigParser` (YAML-based) | ❌ Missing | MEDIUM |

### 12.4 Unused or Dead Code

| Code | Location | Status |
|------|----------|--------|
| `feature_store/builders.py` — `compute_all()` | ML Platform | Used by tests only, not by training pipeline |
| `feature_store/transforms.py` — 5 transform classes | ML Platform | Used by tests only, not integrated with training |
| `DvcManager` — full class with init/push/pull/gc | ML Platform | `track()` called from `DatasetBuilder` but init/push/pull/gc never used externally |
| `EvaluationReporter.save_report()` | ML Platform | Saves to `./data/reports/` but no endpoint exposes reports |
| `research/artifacts/` | Research | Directory exists, populated at runtime only |
| `research/experiments/` | Research | Directory exists, empty |
| `research/models/` | Research | Directory exists, empty |
| `research/reports/` | Research | Directory exists, empty |
| `backend/shared/schema_bootstrap.py` | Shared | Deprecated, delegates to `database/migrations.py` |

### 12.5 Weak Architecture

| Issue | Location | Severity | Impact |
|-------|----------|----------|--------|
| `ConversationMemory` duplicated in `llm/memory.py` and `memory/conversation.py` | Shared | MEDIUM | Two implementations with same API, can diverge |
| Training succeeds silently even when MLflow fails | ML Platform `trainer.py` | MEDIUM | Experiment runs not tracked, lost results |
| Feature transforms defined but never applied in training | ML Platform | HIGH | Feature engineering code is untested dead code |
| Mock data loader overrides real data silently | ML Platform `DatasetBuilder` | MEDIUM | Training on synthetic data without warning |
| `MLBRidge.score_from_recent_data()` always returns fallback | Energy Service | HIGH | ML Platform integration never actually used in production |
| Research notebooks use hardcoded paths and seeds | Research | MEDIUM | Non-reproducible across environments |
| No validation that `research/models/` exports match ML Platform expectations | Cross-service | HIGH | Manual handoff, no contract tests |
| `ensure_topics()` called with no error handling in some consumers | Multiple | LOW | Topic creation failures silently ignored |
| Prediction API uses `model_name` as string (no validation against registry) | ML Platform | MEDIUM | Invalid model names fail at runtime with confusing errors |

### 12.6 Strengths

| Strength | Location | Why It Matters |
|----------|----------|----------------|
| **Clean separation of inference vs training** | ML Service vs ML Platform | Production inference is isolated from training instability |
| **Deterministic dataset splitting** | ML Platform `DatasetSplitter` | Reproducible train/val/test splits across runs |
| **Feature type validation** | ML Platform `FeatureRegistry` | 11 well-defined types with validation on creation |
| **Multi-strategy hyperparameter optimization** | ML Platform `optimization.py` | Grid, Random, and Optuna all available |
| **Structured model lifecycle** | ML Platform `model_registry.py` | 5-stage lifecycle with stage transition methods |
| **Comprehensive observability metrics** | Shared `observability/metrics.py` | ML-specific metrics already defined (`ml_inference_latency_seconds`, `llm_*`) |
| **Resilience patterns available** | Shared `resilience/` | Circuit breaker, retry, timeout, bulkhead all available for ML inference |
| **Canonical Kafka topic definitions** | Shared `kafka/topics.py` | Prediction topics can be added in the same canonical format |
| **HuggingFace + spaCy fallback chain** | ML Service `entities.py` | Graceful degradation if one model fails |
| **PostgreSQL shared schema** | All services | ML Platform can directly query all energy and public data |
| **Strong migration discipline** | Shared `migrations/` | 6 Alembic migrations tracked in git, reversible |
| **Config-driven service settings** | Shared `settings.py` | Single source of truth for all service configurations |
