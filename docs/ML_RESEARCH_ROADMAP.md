# ML Research Roadmap

**Project:** ProxyDefence
**Date:** 2026-07-05
**Status:** Research architecture — no implementation

---

## Phase Overview

```
Phase 0: Foundation (current)    → Existing codebase analysis complete
Phase 1: Infrastructure          → Feature store, dataset pipeline, evaluation framework
Phase 2: Training Platform       → BaseTrainer, scheduled pipelines, experiment tracking
Phase 3: Model Development       → Train all 12 identified models
Phase 4: Production Deployment   → Online inference, monitoring, drift, governance
Phase 5: Advanced Research       → Graph ML, LLM evaluation, domain adaptation
```

---

## Phase 1: Infrastructure (Weeks 1-3)

### Week 1: Feature Store Expansion

**Objective:** Turn the thin feature registry into a real feature store with offline computation.

| Task | Files | Deliverable |
|------|-------|-------------|
| Create `ml.feature_lineage` table | SQL migration | Feature lineage tracking |
| Create `ml.feature_importance` table | SQL migration | Feature importance persistence |
| Implement `OnlineFeatureStore` | `services/ml-platform/feature_store/online.py` | Redis/pgvector-backed online serving |
| Implement `OfflineFeatureStore` | `services/ml-platform/feature_store/offline.py` | Parquet/DuckDB-backed batch compute |
| Add RollingWindow transform | `services/ml-platform/feature_store/transforms.py` | Time-series feature support |
| Add EmbeddingTransform | `services/ml-platform/feature_store/transforms.py` | Embedding feature support |
| Wire FeatureBuilder into training pipeline | `services/ml-platform/training/trainer.py` | Features actually used in training |
| Add feature validation (schema, range, distribution) | `services/ml-platform/feature_store/validation.py` | Drift detection baseline |

**Success criteria:** Features are computed once and served; training pipeline consumes precomputed features without recomputing.

### Week 2: Dataset Pipeline Expansion

**Objective:** Support multiple datasets with validation, versioning, and lineage.

| Task | Files | Deliverable |
|------|-------|-------------|
| Create `ml.dataset_lineage` table | SQL migration | Dataset provenance tracking |
| Create `ml.dataset_profiles` table | SQL migration | Statistical profiles per version |
| Implement `NewsArticleLoader` | `services/ml-platform/datasets/loaders/news_loader.py` | Article dataset support |
| Implement `SignalLoader` | `services/ml-platform/datasets/loaders/signal_loader.py` | Signal dataset support |
| Implement `PriceLoader` | `services/ml-platform/datasets/loaders/price_loader.py` | Price time-series support |
| Add dataset validation pipeline | `services/ml-platform/datasets/validation.py` | Schema + stats + GE checks |
| Add dataset profiling on build | `services/ml-platform/datasets/builder.py` | Auto-profile every version |
| Register 5 dataset configurations | `services/ml-platform/datasets/configs/` | Version-controlled dataset specs |

**Success criteria:** 5 dataset types can be built, validated, versioned, and consumed by training.

### Week 3: Evaluation Framework

**Objective:** Expand from per-run metrics to a full evaluation suite.

| Task | Files | Deliverable |
|------|-------|-------------|
| Add forecasting metrics (MASE, sMAPE, MDA) | `services/ml-platform/evaluation/forecasting.py` | Time-series evaluation |
| Add ranking metrics (NDCG, MAP, MRR) | `services/ml-platform/evaluation/ranking.py` | Ranking evaluation |
| Add anomaly detection metrics | `services/ml-platform/evaluation/anomaly.py` | Anomaly evaluation |
| Implement ablation study runner | `services/ml-platform/evaluation/ablation.py` | Feature group ablation |
| Implement benchmark comparison | `services/ml-platform/evaluation/benchmark.py` | Cross-model comparison |
| Add drift baseline computation | `services/ml-platform/evaluation/drift.py` | Reference distributions |
| Wire evaluation into model registry | `services/ml-platform/registry/model_registry.py` | Evaluation stored with model |
| Add evaluation report API | `services/ml-platform/routers/evaluation.py` | Expose reports via REST |

**Success criteria:** Evaluation report generated automatically after every training run; benchmark comparisons available via API.

---

## Phase 2: Training Platform (Weeks 4-5)

### Week 4: BaseTrainer Framework

**Objective:** Generic training infrastructure supporting all model types.

| Task | Files | Deliverable |
|------|-------|-------------|
| Create `BaseTrainer` ABC | `services/ml-platform/training/base.py` | Abstract training framework |
| Create `ClassificationTrainer` | `services/ml-platform/training/classifier.py` | Classification trainer |
| Create `RegressionTrainer` | `services/ml-platform/training/regressor.py` | Regression trainer |
| Create `ForecastingTrainer` | `services/ml-platform/training/forecaster.py` | Time-series trainer (using `darts` or `sktime`) |
| Create `AnomalyTrainer` | `services/ml-platform/training/anomaly.py` | Anomaly detection trainer |
| Create training orchestrator | `services/ml-platform/training/orchestrator.py` | End-to-end pipeline coordinator |
| Add YAML config parser | `services/ml-platform/training/config.py` | Experiment config from YAML |
| Add distributed training support | `services/ml-platform/training/distributed.py` | Multi-GPU via Ray/Dask |

**Success criteria:** All 5 baseline model types train via common interface; new model types require only a trainer class.

### Week 5: Experiment Tracking + Centralized MLflow

**Objective:** Mandatory, centralized experiment tracking.

| Task | Files | Deliverable |
|------|-------|-------------|
| Deploy centralized MLflow server | Docker Compose + PostgreSQL | MLflow UI accessible at :5000 |
| Convert all trainers to mandatory MLflow | `services/ml-platform/training/*.py` | No training without tracking |
| Add experiment comparison dashboard | `services/ml-platform/routers/experiments.py` | Compare runs API |
| Add experiment clone/reproduce | `services/ml-platform/training/reproduce.py` | Re-run any experiment |
| Add experiment search/filter | `services/ml-platform/routers/experiments.py` | Query by metric, param, dataset |
| Add scheduled retraining | `services/ml-platform/training/scheduler.py` | Cron-triggered retraining |
| Add training notifications (webhook) | `services/ml-platform/training/notifications.py` | Slack/email on completion |

**Success criteria:** Every training run logged; any historical experiment reproducible in one command.

---

## Phase 3: Model Development (Weeks 6-10)

### Week 6: Energy Infrastructure Models

**Objective:** Production-quality models for existing energy infrastructure problems.

| Task | Models | Data Source | Features |
|------|--------|-------------|----------|
| Energy Criticality v2 | XGBoost, LightGBM | All 14 entity tables | Geographic, operational, organizational |
| Energy Criticality v3 | Ensemble (stacking) | + capacity_history | Time-series aggregates |
| Asset Classification | Multiclass (asset_type) | Entity tables + GeoJSON | Location, status, capacity |
| Region Risk Score | Regression | Risk scores + signals | Geopolitical, operational, economic |

**Evaluation targets:** Accuracy >0.90, F1-weighted >0.88, CV std <0.03

### Week 7: Risk & Intelligence Models

**Objective:** Predictive models for disruption risk and threat assessment.

| Task | Models | Data Source | Features |
|------|--------|-------------|----------|
| Disruption Risk v1 | XGBoost (binary) | Disruption signals + entity risk | Signal severity, entity type, region |
| Disruption Risk v2 | LightGBM + SHAP | + historical events | Temporal patterns, event cascades |
| Threat Score Prediction | Regression (ensemble) | All risk sources | Composite multi-dimensional |
| Scenario Severity | Regression (XGBoost) | Digital twin runs | Simulation parameters + entity graph |

**Evaluation targets:** AUC-ROC >0.85, precision >0.80, calibration error <0.05

### Week 8: Commodity & Supply Chain Models

**Objective:** Forecasting models for commodity prices and supply chain dynamics.

| Task | Models | Data Source | Features |
|------|--------|-------------|----------|
| Crude Price Forecast (Brent) | Prophet + LightGBM | `commodity_prices`, 5-year history | Price lags, volatility, event indicators |
| LNG Price Forecast | Ensemble (Prophet + XGBoost) | `commodity_prices` | Seasonality, trend, event shocks |
| Supply Gap Forecast | LSTM (via darts) | `flow_states`, `digital_twin_runs` | Flow utilization, bottleneck history |
| Demand Forecast | Prophet + LightGBM | `demand_profiles` | Seasonal, trend, macroeconomic |

**Evaluation targets:** sMAPE <15%, MASE <1.0, forecast bias <5%

### Week 9: Supplier & Procurement Models

**Objective:** Decision support models for procurement and supplier management.

| Task | Models | Data Source | Features |
|------|--------|-------------|----------|
| Supplier Reliability | XGBoost (classification) | `supplier_intelligence` | Lead time, on-time delivery, sanctions |
| Supplier Risk Score | Regression | + sanctions + events | Multi-dimensional risk composite |
| Route Cost Prediction | Regression (ensemble) | `route_costs` | Distance, risk, tariffs, insurance |
| Route Risk Score | Classification | + shipping routes | Chokepoint proximity, historical incidents |
| Refinery-Crude Match | Recommendation (similarity) | `refinery_crude_compatibility` | NCI, API gravity, sulfur content |

**Evaluation targets:** F1 >0.85 for classification, MAE <10% for regression

### Week 10: Graph & Anomaly Models

**Objective:** Graph-based and unsupervised models for network intelligence.

| Task | Models | Data Source | Features |
|------|--------|-------------|----------|
| Entity Link Prediction | Node2Vec + XGBoost | `entity_relationships` | Graph embeddings, node features |
| Entity Classification | GraphSAGE (via PyG) | Knowledge graph | Node features + neighbor aggregation |
| Flow Anomaly Detection | IsolationForest + AE | `flow_states` | Utilization, bottleneck frequency |
| Port Congestion Anomaly | LOF + Autoencoder | `port_congestion` | Waiting vessels, avg wait time |
| Network Community Detection | Louvain + Leiden | `entity_relationships` | Supply chain communities |

**Evaluation targets:** Link prediction Hits@10 >0.70, anomaly F1 >0.80

---

## Phase 4: Production Deployment (Weeks 11-13)

### Week 11: Model Deployment Infrastructure

**Objective:** Support online, batch, shadow, and A/B deployment modes.

| Task | Deliverable |
|------|-------------|
| Online inference optimization | Model warm-up, batching, caching |
| Batch inference pipeline | Kafka consumer + scheduled batch job |
| Shadow scoring | Dual-run every prediction against shadow model |
| A/B testing framework | Traffic splitting, metric collection |
| Prediction logging | `ml.prediction_log` table, all predictions recorded |
| Model warm-up on deploy | Pre-load + warm-up before serving |

**Success criteria:** Models deployable with zero downtime; shadow scoring runs silently alongside production.

### Week 12: Model Monitoring

**Objective:** Continuous monitoring for drift, performance degradation, and data quality.

| Task | Deliverable |
|------|-------------|
| Feature drift detection | PSI, KS test, distribution comparison |
| Prediction drift detection | Prediction distribution shift |
| Performance monitoring | Accuracy on events with known outcomes |
| Data quality monitoring | Missing values, null ratios, schema violations |
| Monitoring dashboard | Grafana dashboard for all ML metrics |
| Alert rules | Slack/email alerts on drift threshold breach |

**Success criteria:** All production models monitored; drift alerts fire within 1 hour of significant shift.

### Week 13: Model Governance

**Objective:** Approval workflows, compliance metadata, audit trails.

| Task | Deliverable |
|------|-------------|
| Approval gate for staging | Manual review required for validation→staging |
| Approval gate for production | Shadow test results required for staging→production |
| Compliance metadata | Risk classification, bias audit, fairness metrics |
| Audit log | Every state transition, every deployment, every rollback |
| Model card generation | Auto-generated model cards per Google format |
| Rollback mechanism | One-click rollback to previous production model |

**Success criteria:** All model promotions require approval; full audit trail for every model; rollback in <1 minute.

---

## Phase 5: Advanced Research (Weeks 14-16)

### Week 14: Domain-Adapted NLP

**Objective:** Replace off-the-shelf HuggingFace models with domain-finetuned versions.

| Task | Description |
|------|-------------|
| Domain sentiment finetuning | Finetune DistilBERT on proxydefense/energy news corpus |
| Domain NER finetuning | Finetune BERT on labeled energy entity corpus |
| Domain topic classification | Train from scratch on labeled topic corpus |
| Model registry integration | Register finetuned models for ML Service consumption |
| ML Service model consumer | ML Service downloads models from registry on startup |

### Week 15: LLM Evaluation & Optimization

**Objective:** Systematically evaluate and optimize LLM usage across agents.

| Task | Description |
|------|-------------|
| Agent response quality framework | Expert-annotated evaluation set |
| Model comparison (Groq models) | Compare llama-3.3-70b vs mixtral vs qwen |
| Prompt optimization | Systematic prompt tuning with eval feedback |
| Cost-performance analysis | Tokens spent vs quality gained per model |
| Caching strategy | Semantic cache for frequent queries |

### Week 16: Cross-Domain Research

**Objective:** Integrate insights across all models for holistic intelligence.

| Task | Description |
|------|-------------|
| Multi-model ensembles | Stack predictions from risk + price + supply models |
| Causal inference | Estimate causal impact of geopolitical events on supply chains |
| Reinforcement learning | Optimal SPR release policy via RL |
| Federated features | Cross-domain feature importance analysis |

---

## Effort Summary

| Phase | Weeks | Key Outputs | Dependencies |
|-------|-------|-------------|--------------|
| 1: Infrastructure | 1-3 | Feature store, dataset pipeline, evaluation framework | PostgreSQL, ML Platform codebase |
| 2: Training Platform | 4-5 | BaseTrainer, MLflow server, scheduled training | Phase 1 complete |
| 3: Model Development | 6-10 | 12+ production models, all domains | Phase 2 complete |
| 4: Production Deployment | 11-13 | Monitoring, drift, governance, deployment modes | Phase 3 complete |
| 5: Advanced Research | 14-16 | Domain NLP, LLM eval, cross-domain research | Phase 4 complete |
