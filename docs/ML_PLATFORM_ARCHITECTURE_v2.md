# ML Platform Architecture v2 — Research-Grade Energy Intelligence

> **Audience:** ML Engineers, Data Scientists, MLOps  
> **Status:** Design Phase (No Code Changes Yet)  
> **Date:** 2026-07-06

---

## Table of Contents

1. [Research Datasets](#1-research-datasets)
2. [Feature Store Architecture](#2-feature-store-architecture)
3. [Dataset Lineage](#3-dataset-lineage)
4. [Temporal Training Strategy](#4-temporal-training-strategy)
5. [Automatic Dataset Outputs](#5-automatic-dataset-outputs)
6. [Canonical Schema Assessment](#6-canonical-schema-assessment)
7. [Energy Domain Coverage](#7-energy-domain-coverage)
8. [Revised Implementation Roadmap](#8-revised-implementation-roadmap)
9. [Appendix: Feature Catalog](#9-appendix-feature-catalog)

---

## 1. Research Datasets

The ML Platform must produce **versioned, reproducible, research-grade datasets** that can be consumed directly by models without manual preprocessing. Each dataset is defined by its prediction objective, target variable, grain, entities, temporal resolution, sources, features, and consumers.

---

### Dataset 1: `geopolitical_risk_index_v1`

| Attribute | Value |
|---|---|
| **Objective** | Produce composite geopolitical risk scores per country-region-day |
| **Prediction Type** | Regression + Ranking |
| **Target Variable** | `risk_score` (continuous 0-100), `risk_quartile` (1-4), `risk_regime` (calm/elevated/crisis) |
| **Grain** | `country_code` + `date` |
| **Primary Entities** | Country, region (UN M49), sub-region |
| **Temporal Resolution** | Daily |
| **Forecast Horizons** | 7d, 30d, 90d |
| **Required Sources** | GDELT Events (all 61 fields), GDELT Mentions, GKG (themes, persons, orgs, tone) |
| **Consumers** | All downstream datasets (as feature), executive dashboard, AI agents |

**Feature Groups:**

| Group | Features |
|---|---|
| Event Volume | `event_count`, `mention_count`, `article_count`, `source_count` |
| Conflict Intensity | `avg_goldstein_scale`, `goldstein_volatility_7d`, `conflict_event_ratio`, `quad_class_distribution` |
| Tone | `avg_tone`, `tone_volatility_7d`, `negative_tone_ratio`, `positive_tone_ratio` |
| Actor Activity | `unique_actor1_count`, `unique_actor2_count`, `actor_type_distribution` |
| Theme Density | `theme_count`, `person_count`, `org_count`, `unique_theme_count` |
| Temporal | `event_count_7d_rolling`, `event_count_30d_rolling`, `goldstein_7d_ema`, `tone_7d_ema` |
| Composite | `risk_score` (weighted combination of above), `risk_regime` (HMM-derived) |

**Label Construction:**
- `risk_score` = weighted composite of: `(1 - goldstein_norm) * 0.3 + (1 - tone_norm) * 0.25 + event_density * 0.25 + conflict_ratio * 0.2`
- `risk_regime` = 3-state HMM trained on goldstein_7d_ema + tone_7d_ema sequence
- Labels are **contemporaneous** (same time as features) for risk assessment; **forward-looking** for risk prediction

---

### Dataset 2: `port_disruption_risk_v1`

| Attribute | Value |
|---|---|
| **Objective** | Predict port congestion, disruption probability, and waiting time |
| **Prediction Type** | Regression + Classification + Quantile |
| **Target Variables** | `disruption_probability` (binary), `expected_waiting_days` (regression), `congestion_quartile` (1-4), `throughput_deviation` (z-score) |
| **Grain** | `port_code` (UNLOCODE) + `date` |
| **Primary Entities** | Port, country, region, chokepoint cluster |
| **Temporal Resolution** | Daily |
| **Forecast Horizons** | 7d, 14d, 30d |
| **Required Sources** | Port Congestion, AIS (vessel count, speed, destination), World Port Index, GDELT Events/GKG, Commodity Prices |
| **Consumers** | Procurement optimization, logistics AI agents, maritime risk, digital twin |

**Feature Groups:**

| Group | Features |
|---|---|
| Port Profile | `harbor_type`, `max_draft`, `max_length`, `cargo_types`, `region`, `country` (static from WPI) |
| Congestion History | `waiting_days_7d_avg`, `waiting_days_30d_avg`, `vessel_count_7d_avg`, `congestion_level_trend` |
| AIS-derived | `vessels_approaching_7d`, `vessels_departed_7d`, `avg_speed_approach`, `avg_loitering_time` |
| Geopolitical | `country_risk_score` (from geopolitical_risk_index), `nearby_event_count_50km`, `nearby_event_count_200km` |
| Economic | `commodity_price_impact`, `trade_volume_deviation` |
| Temporal | `day_of_week`, `month`, `holiday_flag`, `season`, `port_specific_seasonality` |
| Geospatial | `distance_to_chokepoint`, `chokepoint_congestion_correlation` |

**Label Construction (forward-looking):**
- `disruption_probability` = 1 if waiting_days exceeds 2x historical median in next 7d
- `expected_waiting_days` = actual waiting_days at forecast horizon
- Labels shifted backward by forecast horizon (T+7 for 7d forecast)

---

### Dataset 3: `commodity_forecast_v1`

| Attribute | Value |
|---|---|
| **Objective** | Predict commodity prices, volatility, and price direction |
| **Prediction Type** | Regression + Binary Classification |
| **Target Variables** | `future_price` (continuous), `price_direction` (up/down), `future_volatility` (continuous), `z_score_deviation` |
| **Grain** | `commodity_code` + `exchange` + `date` |
| **Primary Entities** | Commodity (crude oil WTI, Brent, LNG, coal, gas), market/exchange |
| **Temporal Resolution** | Daily |
| **Forecast Horizons** | 7d, 30d, 90d |
| **Required Sources** | Commodity Prices, Commodity Futures, GDELT Events/GKG, EIA, FRED, OPEC, sanctions |
| **Consumers** | Procurement optimization, SPR optimization, risk models, digital twin |

**Feature Groups:**

| Group | Features |
|---|---|
| Price History | `price_lag_1d` through `price_lag_30d`, `price_7d_avg`, `price_30d_avg`, `price_90d_avg` |
| Technical | `rsi_14`, `macd`, `bollinger_pct`, `volume_7d_avg`, `open_interest_change` |
| Futures Curve | `front_month_price`, `back_month_price`, `contango_backwardation_flag`, `spread_1m_12m` |
| Supply | `opec_production`, `opec_change`, `eia_inventories`, `eia_production`, `spr_level` |
| Geopolitical | `producer_country_risk_score`, `conflict_events_producer_regions`, `sanction_events_on_producer` |
| Macro | `usd_index`, `inflation_rate`, `interest_rate`, `gdp_growth` (from FRED) |
| Market Sentiment | `avg_tone_commodity_mentions`, `mention_count_commodity`, `theme_frequency_oil_market` |
| Temporal | `day_of_week`, `month`, `quarter`, `opec_meeting_flag`, `eia_report_day_flag` |

**Label Construction:**
- `future_price` = closing price at T+horizon
- `price_direction` = 1 if future_price > current_price, else 0
- `future_volatility` = std(returns) over [T, T+horizon]
- No lookahead: labels computed from future data but only used at training time

---

### Dataset 4: `maritime_risk_v1`

| Attribute | Value |
|---|---|
| **Objective** | Predict vessel-level maritime risk (delay, rerouting, chokepoint congestion) |
| **Prediction Type** | Classification + Regression |
| **Target Variables** | `delay_probability` (binary), `reroute_probability` (binary), `estimated_arrival_delay_days` (regression), `incident_probability` (binary) |
| **Grain** | `mmsi` (vessel) + `date` |
| **Primary Entities** | Vessel, flag state, vessel type, destination port, origin port |
| **Temporal Resolution** | Daily |
| **Forecast Horizons** | 7d, 14d (for specific route segments) |
| **Required Sources** | AIS, Port Congestion, World Port Index, GDELT Events/GKG, sanctions |
| **Consumers** | Logistics optimization, supply chain AI agents, insurance models |

**Feature Groups:**

| Group | Features |
|---|---|
| Vessel Profile | `vessel_type`, `ship_type_category`, `length`, `width`, `draft`, `cargo_type`, `flag_country` |
| Vessel Track | `speed_avg_7d`, `speed_std_7d`, `course_variance`, `distance_traveled_7d`, `loitering_hours` |
| Route Risk | `destination_port_congestion`, `origin_port_congestion`, `chokepoints_on_route`, `chokepoint_congestion` |
| Geopolitical | `flag_country_risk_score`, `destination_country_risk_score`, `sanctions_on_flag_country`, `sanctions_on_destination` |
| GDELT Route | `events_along_route_100km_7d`, `goldstein_min_along_route_7d`, `tone_min_along_route_7d` |
| Temporal | `day_of_week`, `month`, `seasonal_weather_risk` (future: real-time weather) |

**Label Construction:**
- `delay_probability` = 1 if actual_arrival > scheduled_arrival + 24h
- `reroute_probability` = 1 if vessel track deviates > 50km from expected route
- Labels derived from AIS track analysis at destination arrival

---

### Dataset 5: `infrastructure_anomaly_v1`

| Attribute | Value |
|---|---|
| **Objective** | Detect anomalous infrastructure operation patterns |
| **Prediction Type** | Unsupervised Anomaly Detection + Supervised Classification |
| **Target Variables** | `anomaly_score` (continuous), `anomaly_flag` (binary), `anomaly_type` (multiclass) |
| **Grain** | `asset_type` + `asset_uuid` + `date` |
| **Primary Entities** | Port, refinery, pipeline, LNG terminal, power plant, storage facility, oil/gas field |
| **Temporal Resolution** | Daily |
| **Forecast Horizons** | Real-time detection + 7d forecast |
| **Required Sources** | Energy Service (all 14 tables), AIS, Port Congestion, GDELT Events, EIA |
| **Consumers** | Monitoring dashboard, digital twin, AI agents |

**Feature Groups:**

| Group | Features |
|---|---|
| Asset Profile | `asset_type`, `capacity`, `operational_status`, `criticality`, `region`, `country` |
| Operational History | `throughput_7d_avg`, `throughput_30d_avg`, `throughput_z_score`, `utilization_rate` |
| AIS-derived | `vessel_visits_7d`, `vessel_visits_deviation`, `avg_dwell_time` |
| Geopolitical | `country_risk_score`, `nearby_events_50km_7d`, `nearby_event_type_diversity` |
| Market | `commodity_price_z_score`, `supply_demand_imbalance` |
| Temporal | `day_of_week`, `month`, `maintenance_season_flag` |

**Label Construction:**
- `anomaly_score` = Isolation Forest + autoencoder reconstruction error
- `anomaly_flag` = score > 95th percentile of historical
- `anomaly_type` = cluster of anomaly pattern (dropout, surge, oscillation, drift)
- For supervised: expert-labeled historical anomalies

---

### Dataset 6: `supplier_reliability_v1`

| Attribute | Value |
|---|---|
| **Objective** | Predict supplier reliability and on-time delivery probability |
| **Prediction Type** | Regression + Classification |
| **Target Variables** | `reliability_score` (0-100), `on_time_probability` (binary), `quality_risk` (binary) |
| **Grain** | `supplier_uuid` + `month` |
| **Primary Entities** | Supplier, supplier country, commodity |
| **Temporal Resolution** | Monthly |
| **Forecast Horizons** | 1 month, 3 months |
| **Required Sources** | GDELT Events/GKG, sanctions, Port Congestion (aggregated), AIS (aggregated), Commodity Prices |
| **Consumers** | Procurement optimization, SPR optimization, risk models |

**Feature Groups:**

| Group | Features |
|---|---|
| Supplier Profile | `supplier_type`, `countries_served`, `commodities`, `contract_volume` |
| Country Risk | `supplier_country_risk_score` (from geopolitical_risk_index), `sanctions_active_flag` |
| Supply Chain | `exposed_port_congestion_avg`, `shipping_delay_avg`, `route_risk_score` |
| Market | `commodity_price_volatility_3m`, `input_cost_index` |
| Historical | `past_reliability_3m`, `past_reliability_12m`, `late_delivery_count_12m` |
| Geopolitical | `conflict_events_supplier_region_3m`, `strike_event_count`, `regulatory_change_flag` |

**Label Construction:**
- `reliability_score` = weighted composite of on-time %, quality score, and contract fulfillment %
- `on_time_probability` = 1 if delivery within contract window
- Labels from procurement records (future: digital contracts)

---

### Dataset 7: `procurement_optimization_v1`

| Attribute | Value |
|---|---|
| **Objective** | Recommend optimal order timing, quantity, and supplier allocation |
| **Prediction Type** | Decision + Optimization (not just prediction) |
| **Target Variables** | `recommended_order_quantity`, `recommended_supplier_id`, `recommended_timing` (week) |
| **Grain** | `commodity_code` + `week` |
| **Primary Entities** | Commodity, supplier, procurement region |
| **Temporal Resolution** | Weekly |
| **Forecast Horizons** | 4w, 12w, 26w |
| **Required Sources** | ALL upstream datasets: commodity_forecast, port_disruption, maritime_risk, supplier_reliability, geopolitical_risk |
| **Consumers** | Procurement AI agents, optimization engine, executive dashboards |

**This is a composite dataset — features are predictions from other models + static data.**

**Feature Groups:**

| Group | Features |
|---|---|
| Price Forecast | `price_forecast_4w`, `price_forecast_12w`, `price_direction`, `price_volatility_forecast` (from commodity_forecast) |
| Disruption Risk | `port_disruption_probability_4w`, `supplier_reliability_forecast` (from port_disruption, supplier_reliability) |
| Inventory | `current_inventory_level`, `days_of_cover`, `reorder_point`, `safety_stock` |
| Supply | `supplier_capacity_forecast`, `production_forecast`, `export_restriction_flag` |
| Geopolitical | `producer_risk_score`, `sanction_risk_flag` (from geopolitical_risk_index) |
| Cost | `holding_cost`, `ordering_cost`, `transport_cost_forecast`, `tariff_rate` |

**Label Construction:**
- `recommended_order_quantity` = output of inventory optimization model (newsvendor, min-max, or RL)
- Labels are simulated from optimal policy on historical data

---

### Dataset 8: `spr_optimization_v1`

| Attribute | Value |
|---|---|
| **Objective** | Recommend SPR release/storage decisions |
| **Prediction Type** | Decision + Optimization |
| **Target Variables** | `recommended_release_volume` (barrels), `recommended_storage_volume` (barrels), `spr_adequacy_score` |
| **Grain** | `country` + `month` |
| **Primary Entities** | Country, SPR facility, strategic reserve region |
| **Temporal Resolution** | Monthly |
| **Forecast Horizons** | 3m, 6m, 12m |
| **Required Sources** | commodity_forecast, geopolitical_risk_index, EIA SPR data, OPEC production |
| **Consumers** | Strategic planning, executive decision support |

**Feature Groups:**

| Group | Features |
|---|---|
| Price Forecast | `price_forecast_3m`, `price_forecast_6m`, `price_forecast_12m`, `price_volatility_forecast` |
| Supply Risk | `supply_deficit_probability_3m`, `opec_production_change`, `export_restriction_count` |
| Geopolitical | `global_risk_index_3m_avg`, `producer_region_risk`, `conflict_near_chokepoints` |
| SPR Status | `current_spr_level`, `spr_days_of_cover`, `spr_drawdown_capacity`, `spr_fill_rate` |
| Demand | `consumption_forecast`, `import_dependency`, `demand_growth` |

---

### Dataset 9: `energy_security_index_v1`

| Attribute | Value |
|---|---|
| **Objective** | Measure and predict national energy security |
| **Prediction Type** | Composite Index + Forecasting |
| **Target Variables** | `energy_security_score` (0-100), `security_regime` (secure/vulnerable/critical) |
| **Grain** | `country_code` + `month` |
| **Primary Entities** | Country, region |
| **Temporal Resolution** | Monthly |
| **Forecast Horizons** | 3m, 12m |
| **Required Sources** | ALL sources aggregated |
| **Consumers** | Executive dashboard, strategic planning, policy analysis |

**Sub-Indices:**

| Index | Weight | Components |
|---|---|---|
| Supply Diversity | 0.25 | Number of suppliers, HHI of supply sources, import dependency |
| Infrastructure Resilience | 0.20 | Port diversification, pipeline redundancy, storage capacity, chokepoint exposure |
| Geopolitical Stability | 0.20 | Country risk score, regional conflict density, sanction exposure |
| Economic Affordability | 0.15 | Price level, price volatility, import cost/GDP ratio |
| Environmental Transition | 0.10 | Renewable share, carbon intensity, transition readiness |
| Infrastructure Capacity | 0.10 | SPR coverage ratio, refinery capacity, LNG regasification capacity |

---

### Dataset 10: `digital_twin_v1`

| Attribute | Value |
|---|---|
| **Objective** | Simulate energy supply chain dynamics under scenarios |
| **Prediction Type** | Simulation + Reinforcement Learning Environment |
| **Target Variables** | State transitions: `throughput`, `inventory`, `vessel_position`, `congestion`, `price` |
| **Grain** | Multiple grains per entity type (vessel-hour, port-day, pipeline-day) |
| **Primary Entities** | All: ports, vessels, pipelines, refineries, storage, suppliers, consumers |
| **Temporal Resolution** | Hourly (simulation step) |
| **Forecast Horizons** | 7d, 30d, 90d simulation |
| **Required Sources** | ALL upstream datasets, ALL real-time sources |
| **Consumers** | Reinforcement learning, scenario planning, what-if analysis AI agents |

**This is a composite environment rather than a single training dataset. It contains:**
- Entity state definitions (port throughput, vessel position, inventory levels)
- Transition functions (learned from historical data)
- Scenario generators (price shock, conflict escalation, weather disruption)
- Reward functions (cost, resilience, security)

---

## 2. Feature Store Architecture

### Current State vs Target

| Aspect | Current | Target |
|---|---|---|
| Offline/Online | Single table | Separate: offline Parquet + online Redis/PG |
| Point-in-time | Not handled | `get_features(entity_id, as_of)` with time-travel |
| Freshness | None tracked | Per-feature freshness SLA + staleness alerts |
| Lineage | Partial (name + version) | Full: source_data → transform_code → params → hash |
| Versioning | Manual increment | Automatic on any dependency change |
| Metadata | Name, type, description, transform_config | + owner, SLA, distribution, drift baseline, cost, cardinality |
| Ownership | None | Feature group owner + feature-level code owner |

### Point-in-Time Architecture

```
Entity: Port "USNYC" at Time T

Step 1: Fetch all source data with timestamp <= T
  ├── AIS positions WHERE timestamp <= T
  ├── Port congestion WHERE date <= T
  ├── GDELT events WHERE day <= T
  └── World Port Index (static)

Step 2: Compute features as-of T
  ├── rolling_avg_waiting_days_7d = avg(waiting_days) OVER [T-7, T]
  ├── vessel_count_7d = count(vessels) OVER [T-7, T]
  └── risk_score = risk_model(country, T)

Step 3: Return {entity_id: "USNYC", as_of: T, features: {...}}
```

### Feature Freshness Tiers

| Tier | Freshness SLA | Storage | Example |
|---|---|---|---|
| Real-time | < 1min | Redis | Vessel position |
| Near-realtime | < 1h | Redis + PG | Commodity price, port waiting time |
| Daily | 24h | PG + Parquet | GDELT risk score, congestion |
| Weekly | 7d | PG + Parquet | Supplier reliability |
| Static | Never changes | PG + Parquet | World Port Index, vessel profile |

### Feature Lineage

Every feature should trace back to:
1. **Source dataset** (e.g., GDELT events v20240101)
2. **Canonical schema version** (v1, fields used)
3. **Normalization rules applied** (country, date, org)
4. **Transform code** (function name + git hash)
5. **Transform parameters** (window_size=7, agg_func='mean')
6. **Feature definition** (name + version in feature store)

Implementation:
- Each feature computation writes a lineage record:
  ```json
  {
    "feature_name": "waiting_days_7d_avg",
    "feature_version": 3,
    "source": {
      "type": "canonical",
      "dataset": "port_congestion",
      "version": "20240101"
    },
    "transform": {
      "function": "rolling_window",
      "parameters": {"window": 7, "agg": "mean"},
      "git_hash": "a1b2c3d4"
    },
    "computed_at": "2026-07-06T12:00:00Z"
  }
  ```

### Feature Versioning Strategy

- **Automatic version increment** when any input changes:
  - Source data schema changes
  - Transform code changes
  - Transform parameters change
- **Semantic versioning** for feature groups:
  - Major: breaking change (column removed, semantics changed)
  - Minor: additive (new features, non-breaking additions)
  - Patch: bug fixes, performance improvements
- **Version hash** = SHA256 of (source_data_schema + transform_code + transform_params)
- **Version registry** table: `ml.feature_versions` with all upstream dependency hashes

### Feature Metadata

```python
FeatureMetadata:
    name: str
    version: int
    display_name: str
    description: str
    feature_type: enum(numerical, categorical, boolean, timestamp, geospatial, text, embedding)
    owner: str                # team or individual
    freshness_sla: str        # e.g., "24h"
    staleness_threshold: str  # e.g., "48h"
    distribution_type: enum(normal, uniform, log_normal, discrete, categorical)
    expected_range: tuple[float, float]  # [min, max]
    cardinality: int          # for categorical
    null_percentage: float    # expected
    drift_baseline: str       # reference to drift_baseline record
    compute_cost: str         # "low", "medium", "high"
    privacy_level: str        # "public", "restricted", "confidential"
    git_hash: str             # code version
    created_at: datetime
    updated_at: datetime
```

### Feature Groups

| Group Name | Category | Features | Freshness | Owner |
|---|---|---|---|---|
| `port_profile` | Static | harbor_type, max_draft, cargo_types, country, region | Static | Platform |
| `port_congestion_historical` | Temporal | waiting_days_7d_avg, vessel_count_7d_avg, trend | Daily | Platform |
| `port_geopolitical_risk` | Derived | country_risk_score, events_50km_7d, goldstein_min | Daily | ML Team |
| `vessel_track` | Realtime | speed, course, destination, loitering_hours | < 1min | ML Team |
| `commodity_technical` | Derived | rsi_14, macd, bollinger, volume_avg | Hourly | ML Team |
| `commodity_macro` | External | usd_index, inflation, interest_rate | Weekly | Platform |
| `country_risk` | Derived | risk_score, risk_regime, conflict_density | Daily | ML Team |
| `supplier_profile` | Static | supplier_type, countries, contract_volume | Weekly | Procurement |
| `infrastructure_status` | Operational | throughput, utilization, status | Daily | Operations |

### Online vs Offline Serving

| Aspect | Offline (Training) | Online (Inference) |
|---|---|---|
| Storage | Parquet + PG | Redis + PG feature_vectors |
| Point-in-time | Required (as-of timestamp) | Best-effort (latest available) |
| Feature count | All features | Subset (most important 20-50) |
| Compute | Batch (daily/hourly) | Pre-computed + cached |
| Latency | Minutes | < 10ms |
| Freshness | T-24h | T-5min |

---

## 3. Dataset Lineage

### Complete Lineage DAG

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SOURCES (raw data)                              │
│  GDELT   AIS   WPI   EIA   FRED   OPEC  Sanctions  Commodity  PortCong    │
└────┬────────┬──────┬──────┬──────┬──────┬──────────┬──────────┬────────────┘
     │        │      │      │      │      │          │          │
     ▼        ▼      ▼      ▼      ▼      ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CANONICAL RECORDS (immutable, versioned)               │
│  events  mentions  gkg  ais  ports  congestion  eia  fred  opec  sanctions │
└────┬────────┬──────┬──────┬──────┬──────┬──────────┬──────────┬────────────┘
     │        │      │      │      │      │          │          │
     ▼        ▼      ▼      ▼      ▼      ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                NORMALIZED CANONICAL (cleaned, normalized)                   │
│  + iso_country  + normalized_org  + normalized_person  + utc_timestamps    │
│  + validated_coords  + dedup_cluster_id  + source_confidence               │
└────┬────────┬──────┬───────────────────────────────────────┬────────────────┘
     │        │      │                                       │
     │        │      │            FEATURE ENGINEERING        │
     │        │      │               ▼                       │
     │        │      │    ┌──────────────────────┐           │
     │        │      │    │ Feature Computation  │           │
     │        │      │    │ - Rolling windows    │           │
     │        │      │    │ - Aggregations       │           │
     │        │      │    │ - Encoding           │           │
     │        │      │    │ - Text extraction    │           │
     │        │      │    │ - Geospatial         │           │
     │        │      │    └──────────┬───────────┘           │
     │        │      │               │                       │
     ▼        ▼      ▼               ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FEATURE STORE (versioned, typed)                        │
│  ml.feature_definitions + ml.feature_vectors + Parquet snapshots           │
└────┬────────┬──────┬──────┬──────┬──────┬──────────┬──────────┬────────────┘
     │        │      │      │      │      │          │          │
     │        │      │      │      │      │          │          │
     ▼        ▼      ▼      ▼      ▼      ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       RESEARCH DATASETS (versioned, split)                  │
│                                                                             │
│  geopolitical_risk_index_v1                                                 │
│  port_disruption_risk_v1                                                    │
│  commodity_forecast_v1                                                      │
│  maritime_risk_v1                                                           │
│  infrastructure_anomaly_v1                                                  │
│  supplier_reliability_v1                                                    │
│  procurent_optimization_v1                                                  │
│  spr_optimization_v1                                                        │
│  energy_security_index_v1                                                   │
│  digital_twin_v1                                                            │
└────┬────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODEL CONSUMERS                                          │
│  XGBoost  LightGBM  CatBoost  LSTM  Transformers  RL Agents  Forecasting   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Transformation Tracking

Each edge in the lineage DAG must record:

```sql
CREATE TABLE ml.transformation_log (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID DEFAULT gen_random_uuid(),
    
    -- Source
    source_type     TEXT NOT NULL,      -- 'canonical', 'normalized', 'feature', 'dataset'
    source_name     TEXT NOT NULL,      -- e.g., 'gdelt_events'
    source_version  TEXT NOT NULL,      -- e.g., '20240101'
    
    -- Transform
    transform_name  TEXT NOT NULL,      -- e.g., 'country_normalizer', 'rolling_window'
    transform_params JSONB DEFAULT '{}', -- e.g., {"window": 7, "agg": "mean"}
    transform_hash  TEXT NOT NULL,      -- SHA256 of (code + params)
    git_hash        TEXT,               -- code version
    
    -- Produced
    target_type     TEXT NOT NULL,
    target_name     TEXT NOT NULL,
    target_version  TEXT NOT NULL,
    
    -- Metrics
    records_input   INTEGER,
    records_output  INTEGER,
    records_dropped INTEGER,
    duration_ms     INTEGER,
    quality_score   FLOAT,
    
    -- Provenance
    executed_by     TEXT DEFAULT 'system',
    executed_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_name, source_version, transform_hash, target_name, target_version)
);
```

---

## 4. Temporal Training Strategy

### Core Principle: No Future Leakage

The most critical issue in time-series ML for energy is **data leakage from the future**. GDELT events labeled with date `2024-01-01` represent knowledge available on that date. A feature computed as "7-day rolling average of tone" on January 1 uses data from December 25-31. If the label is "disruption on January 8", then features are computed on T and labels are over [T+1, T+H].

### Temporal Split Strategy

```
                     TRAINING                    VALIDATION    TEST
                     ┌──────────────────────┐   ┌─────────┐   ┌─────┐
                     │                      │   │         │   │     │
                     │  T_start             │   │         │   │     │
                     │         │            │   │         │   │     │
History:     2020-01-01 ─────────────────────── 2025-06-01 ── 2025-09-01 ── 2026-01-01
                                                                           
                     train_end ─── gap ──── val_start ── gap ── test_start
                                               (30d)              (30d)
```

- **Gap**: 30 days between train/val and val/test to prevent proximity leakage
- **Stratification**: By region, by commodity type (not random)
- **Walk-forward**: Multiple temporal folds for robust evaluation

### Walk-Forward Cross-Validation

```
Fold 1: Train [2020-01, 2024-06] → Val [2024-07, 2024-09] → Test [2024-10, 2024-12]
Fold 2: Train [2020-01, 2024-09] → Val [2024-10, 2024-12] → Test [2025-01, 2025-03]
Fold 3: Train [2020-01, 2024-12] → Val [2025-01, 2025-03] → Test [2025-04, 2025-06]
```

Each fold shifts forward by 3 months. Expanding window (more training data each fold).

### Multiple Forecast Horizons

Each dataset supports multiple horizons with separate labels:

| Horizon | Label Window | Use Case |
|---|---|---|
| Short-term (7d) | [T+1, T+7] | Operational decisions |
| Medium-term (30d) | [T+1, T+30] | Tactical planning |
| Long-term (90d) | [T+1, T+90] | Strategic planning |

At training time, each row is duplicated with the horizon as a feature:
```
| entity_id | date   | features... | label_7d | label_30d | label_90d |
|-----------|--------|-------------|----------|-----------|-----------|
| USNYC     | 01-01  | ...         | 0.3      | 0.6       | 0.8       |
```

Or separate datasets per horizon for model specialization.

### Leakage Prevention Checklist

Every dataset build must pass:

| Leakage Type | Detection | Prevention |
|---|---|---|
| **Temporal** | Feature uses data from > as_of date | Filter all source data by timestamp <= as_of |
| **Entity overlap** | Same entity in train AND test | Time-based split per entity |
| **Label leakage** | Label computed with future data | Never include target in feature computation |
| **Feature overlap** | Same feature in train and test | Snapshot feature store as-of train_end |
| **Global statistics** | mean/std computed on full dataset | Compute per-fold statistics |
| **Imputation** | Future values used to fill past | Impute with expanding window statistics |
| **Rolling windows** | Window includes future data | Strictly causal rolling (only look back) |
| **Cross-entity** | Entity A's future used for Entity B | Entity-isolated splits |

### Temporal Horizon Classes

```python
class TemporalSplitter:
    """
    Splits time-series data with strict temporal boundaries.
    Supports expanding and sliding windows with gaps.
    """
    strategies:
        - expanding_window: Train grows, val/test shift
        - sliding_window: Fixed-size training window
        - purged_kfold: Time-series CV with purged gap
        - combinatorial: All combinations of train/val/test cuts

    parameters:
        - train_end: latest date allowed in training
        - val_end: latest date allowed in validation
        - gap_days: days between train and val (leakage buffer)
        - min_train_days: minimum training size
        - horizon_days: forecast horizon (label window)
```

---

## 5. Automatic Dataset Outputs

Every dataset build should produce the following outputs automatically:

### Output 1: Profile Report

```json
{
    "dataset_name": "port_disruption_risk_v1",
    "version": 3,
    "row_count": 125430,
    "column_count": 47,
    "columns": {
        "waiting_days_7d_avg": {
            "dtype": "float64",
            "missing": 0.02,
            "mean": 3.4,
            "std": 2.1,
            "min": 0.0,
            "p25": 1.8,
            "p50": 3.0,
            "p75": 4.5,
            "max": 28.0,
            "skew": 2.1,
            "kurtosis": 8.3,
            "iqr": 2.7,
            "zeros": 0.05
        },
        "port_country": {
            "dtype": "categorical",
            "missing": 0.0,
            "cardinality": 87,
            "top_values": {"CN": 0.15, "US": 0.12, "NL": 0.08, "SG": 0.06},
            "entropy": 4.2
        }
    },
    "shape": (125430, 47),
    "memory_mb": 45.2
}
```

### Output 2: Quality Report

```json
{
    "dataset_name": "port_disruption_risk_v1",
    "version": 3,
    "overall_score": 0.87,
    "dimensions": {
        "completeness": 0.95,
        "consistency": 0.92,
        "uniqueness": 0.99,
        "timeliness": 0.85,
        "validity": 0.88,
        "integrity": 0.78
    },
    "issues": [
        {
            "severity": "warning",
            "dimension": "integrity",
            "column": "port_code",
            "description": "12 port_codes not found in World Port Index reference",
            "count": 12
        }
    ]
}
```

### Output 3: Coverage Report

```json
{
    "temporal_coverage": {
        "start_date": "2020-01-01",
        "end_date": "2026-01-01",
        "total_days": 2192,
        "gap_days": 3,
        "gap_percentage": 0.001,
        "largest_gap_days": 1
    },
    "entity_coverage": {
        "total_ports": 342,
        "ports_with_high_coverage": 280,
        "ports_with_low_coverage": 62,
        "low_coverage_ports": ["XYZ", "ABC"]
    },
    "geographic_coverage": {
        "countries": 87,
        "regions": 12,
        "regions_with_high_coverage": ["Western Europe", "SE Asia"],
        "regions_with_low_coverage": ["Central Africa", "Pacific Islands"]
    }
}
```

### Output 4: Correlation Report

```json
{
    "feature_to_target_correlations": {
        "waiting_days_7d_avg": 0.65,
        "vessel_count_7d_avg": 0.42,
        "country_risk_score": 0.38,
        "nearby_events_50km_7d": 0.25,
        "commodity_price_impact": 0.18
    },
    "high_feature_correlations": [
        {"feature_a": "waiting_days_7d_avg", "feature_b": "vessel_count_7d_avg", "r": 0.87},
        {"feature_a": "events_50km_7d", "feature_b": "events_200km_7d", "r": 0.82}
    ],
    "multicollinearity_warning": true,
    "vif_scores": {
        "waiting_days_7d_avg": 4.2,
        "vessel_count_7d_avg": 3.8,
        "country_risk_score": 1.2
    }
}
```

### Output 5: Drift Report (Version-to-Version)

```json
{
    "baseline_version": 2,
    "current_version": 3,
    "features_with_drift": [
        {
            "feature": "country_risk_score",
            "psi": 0.15,
            "psi_threshold": 0.1,
            "drift_detected": true,
            "baseline_mean": 42.5,
            "current_mean": 48.2,
            "baseline_std": 15.3,
            "current_std": 18.1
        }
    ],
    "overall_drift": "moderate",
    "recommended_action": "review country_risk_score distribution shift"
}
```

### Output 6: Leakage Report

```json
{
    "temporal_leakage": {
        "passed": true,
        "details": "All features computed as-of date, no future data used"
    },
    "entity_overlap": {
        "passed": true,
        "overlapping_entities": 0,
        "train_entities": 280,
        "test_entities": 62
    },
    "statistical_leakage": {
        "passed": true,
        "details": "Per-fold statistics computed within fold boundaries"
    },
    "rolling_window_leakage": {
        "passed": true,
        "details": "Causal rolling windows only look backward from as-of date"
    }
}
```

### Output 7: Feature Documentation

Markdown document for each feature:

```markdown
## waiting_days_7d_avg

**Type:** numerical  
**Feature Group:** port_congestion_historical  
**Owner:** ML Platform Team  
**Freshness SLA:** 24h  

**Description:**  
7-day rolling average of port waiting days. Computed from Port Congestion data.

**Source:** Port Congestion canonical records (versioned)  
**Transform:** `rolling_window(window=7, agg='mean')` on `waiting_days` column  

**Expected Range:** [0.0, 30.0]  
**Null %:** 2% (ports without congestion history)  
**Distribution:** Log-normal (right-skewed)  

**Usage Notes:**  
- Use log transform for linear models
- High correlation (r=0.87) with vessel_count_7d_avg — consider dropping one
```

### Output 8: Schema Documentation

```json
{
    "dataset_name": "port_disruption_risk_v1",
    "version": 3,
    "schema": [
        {"name": "port_code", "type": "string", "nullable": false, "description": "UNLOCODE"},
        {"name": "date", "type": "date", "nullable": false, "description": "Date of observation"},
        {"name": "country_code", "type": "string", "nullable": false, "description": "ISO-3166 alpha-2"},
        {"name": "waiting_days_7d_avg", "type": "float", "nullable": true, "description": "7d rolling avg waiting days"},
        ...
    ],
    "primary_key": ["port_code", "date"],
    "target_column": "disruption_probability",
    "feature_count": 45,
    "static_features": 5,
    "temporal_features": 40
}
```

---

## 6. Canonical Schema Assessment

### Current Schema (18 fields)

```python
{
    "entity_type": str,           # REQUIRED
    "entity_id": str,             # REQUIRED
    "entity_name": str,            # Human-readable
    "timestamp": str,              # ISO 8601
    "timestamp_precision": str,    # year/month/day/hour/minute/second
    "latitude": float | None,      # Decimal degrees [-90, 90]
    "longitude": float | None,     # Decimal degrees [-180, 180]
    "location_name": str | None,   # e.g., country name, port name
    "location_code": str | None,   # e.g., ISO country code, UNLOCODE
    "attributes": dict,            # SOURCE-SPECIFIC PAYLOAD (black hole)
    "relationships": list[dict],   # Related entities
    "source": str,                 # Source tag like "ais", "gdelt"
    "source_record_id": str | None, # ID in original source
    "confidence": float | None,    # [0.0, 1.0]
    "metadata": dict,              # Parser name + version + provenance
}
```

### Problem

The 18-field schema is a good **transport layer** but insufficient for **ML consumption** because:

1. **`attributes: dict` contains 80%+ of the valuable data** but is untyped, unvalidated, and unqueryable
2. **No standardized country representation** — some parsers use alpha-2, others alpha-3, others full names
3. **No standardized organization names** — raw source values with inconsistent casing and abbreviations
4. **No standardized person names** — raw source values
5. **No UTC timestamp normalization** — raw timestamps from source
6. **No coordinate validation flag** — must re-validate every time
7. **No cross-source dedup support** — entity_id is source-specific
8. **Confidence is rarely populated** — only 3 of 17 parsers compute it

### Proposed Addition: Normalized Canonical Layer (Immutable Canonical + Derived Normalized)

Keep the original canonical records **immutable** (never modify parser output).

Add a **Normalized Canonical Layer** with additional fields, derived from original canonical through deterministic transforms:

```python
NormalizedCanonicalRecord(CanonicalRecord):
    # Country normalization
    iso_country_code: str | None           # ISO-3166 alpha-2 (normalized)
    iso_country_name: str | None           # Full country name (normalized)
    iso_region_code: str | None            # UN M.49 region code
    iso_region_name: str | None            # UN M.49 region name

    # Entity normalization
    normalized_entity_name: str | None     # Cleaned entity name
    normalized_org_names: list[str]        # Organization names normalized
    normalized_person_names: list[str]     # Person names normalized
    
    # Location normalization
    normalized_location_name: str | None   # Cleaned location name
    coordinates_validated: bool            # Passed lat/lng validation?
    coordinate_source: str | None          # "actor1_geo", "action_geo", "primary"

    # Timestamp normalization
    timestamp_utc: datetime | None         # Normalized to UTC
    timestamp_timezone: str | None         # Detected timezone

    # Cross-source deduplication
    dedup_cluster_id: str | None           # Cluster ID for cross-source matching
    
    # Confidence
    normalized_confidence: float | None    # Re-computed with configurable formula
    confidence_components: dict | None     # Breakdown of confidence factors

    # Schema versioning
    canonical_schema_version: str          # Version of canonical schema used
    normalization_version: str             # Version of normalization rules applied
    
    # Provenance enrichment
    source_reliability_score: float | None # Reliability score for the data source
```

The normalized layer is **derived, not stored as source truth**. It's regenerated whenever normalization rules change. This keeps the original parser output clean.

### Migration Strategy

1. Keep CanonicalRecord unchanged (immutable base)
2. Add NormalizedCanonicalRecord as a subclass with additional fields
3. Transformation pipeline: CanonicalRecord → Normalize → NormalizedCanonicalRecord
4. Store normalized records as Parquet alongside original canonical records
5. Feature engineering reads from normalized records
6. Original canonical records remain for debug/audit

---

## 7. Energy Domain Coverage

### Current Coverage

| Domain Asset | Current Status | Data Source | Coverage Gaps |
|---|---|---|---|
| **Ports** | ✅ Strong | WPI (+10,000), AIS | Real-time congestion limited |
| **Oil Fields** | ✅ Present | Energy Service + EIA | Individual field production data |
| **Gas Fields** | ✅ Present | Energy Service + EIA | Individual field production data |
| **Pipelines** | ✅ Present | Energy Service | Operational capacity, utilization |
| **Refineries** | ✅ Present | Energy Service + EIA | Real-time throughput, maintenance |
| **Storage Facilities** | ⚠️ Partial | Energy Service + EIA | Only SPR, missing commercial storage |
| **Power Plants** | ⚠️ Partial | EIA + Energy Service | Only generation capacity, no dispatch |
| **Chokepoints** | ⚠️ Basic | Energy Service | Missing real-time status, transit times |

### Critical Gaps to Fill

| Asset Type | Priority | Required For | Suggested Approach |
|---|---|---|---|
| **LNG Terminals** | 🔴 High | commodity_forecast, port_disruption | Add to Energy Service schema: regasification capacity, storage, loading rates, berth count |
| **Critical Minerals** | 🔴 High | commodity_forecast, procurement | New source: USGS Mineral Commodity Summaries, S&P Global. Lithium, cobalt, nickel, rare earths, graphite, manganese |
| **Maritime Chokepoints** | 🔴 High | maritime_risk, port_disruption | Add real-time status: Hormuz, Malacca, Suez, Panama, Bab-el-Mandeb, Bosporus, Danish Straits. Transit time, waiting tankers, draft restrictions |
| **Shipping Lanes** | 🟡 Medium | maritime_risk, digital_twin | Derive from AIS historical tracks. Major lane segments with typical transit times |
| **Renewable Assets** | 🟡 Medium | energy_security_index | New source: IRENA, EIA. Solar/wind/hydro/geothermal capacity and generation |
| **Transmission Grid** | 🟡 Medium | infrastructure_anomaly | Cross-border interconnectors, HVDC lines, substation capacity |
| **Waterways** | 🟢 Low | maritime_risk | Inland waterways, locks, draft restrictions (Mississippi, Rhine, Danube, Yangtze) |
| **Rail Networks** | 🟢 Low | procurement | Mineral transport corridors (future source) |

### Priority Implementation Order

1. **LNG Terminals** — already partially inferable from Energy Service; add explicit schema table
2. **Chokepoint Monitoring** — add real-time status endpoint; scrape AIS for transit counts
3. **Critical Minerals** — add USGS digest reader/parser; add to source registry
4. **Renewable Assets** — add IRENA data source; add to energy infrastructure builder
5. **Transmission Grid** — add cross-border interconnector data from EIA/ENTSO-E

---

## 8. Revised Implementation Roadmap

Ordered by **research value** (impact on AI model quality) rather than engineering convenience:

### Phase 1: Foundation (Weeks 1-3)

**Highest value — enables all downstream work.**

1. **Normalized Canonical Layer** (Week 1)
   - `NormalizedCanonicalRecord` class
   - `CountryNormalizer`, `OrgNormalizer`, `PersonNormalizer`, `TimestampNormalizer` integration
   - Automatic application as pipeline stage
   - Normalization versioning

2. **`geopolitical_risk_index_v1` Dataset** (Weeks 2-3)
   - Feature group: event volume, conflict intensity, tone, actor activity, theme density
   - Country-day grain, daily resolution
   - Composite risk score label
   - Auto-profiling + quality gating

### Phase 2: Core Energy Datasets (Weeks 4-8)

3. **Temporal Split Framework** (Week 4)
   - `TemporalSplitter` class (expanding + sliding window)
   - Leakage prevention (purged gap, causal features)
   - Multiple horizon support (7d, 30d, 90d)
   - Walk-forward cross-validation folds

4. **`port_disruption_risk_v1` Dataset** (Weeks 5-6)
   - Port-day grain using AIS + Port Congestion + GDELT + WPI
   - Auto-feature engine: rolling averages, entity statistics
   - Feature group: port_profile, congestion_history, ais_derived, geopolitical

5. **`commodity_forecast_v1` Dataset** (Weeks 7-8)
   - Commodity-day grain using Prices + Futures + GDELT + EIA + FRED + OPEC
   - Technical indicators (RSI, MACD, Bollinger) auto-generated
   - Supply-demand features from multiple sources
   - Multi-horizon labels (7d, 30d, 90d)

### Phase 3: Risk & Reliability (Weeks 9-12)

6. **`maritime_risk_v1` Dataset** (Weeks 9-10)
   - Vessel-day grain from AIS + GDELT + sanctions + port congestion
   - Route risk scoring (chokepoint proximity, event density)
   - Vessel track features (speed variance, loitering)

7. **`infrastructure_anomaly_v1` Dataset** (Weeks 10-11)
   - Asset-day grain with Isolation Forest baseline
   - Operational deviation features
   - Expert-labeled anomaly validation set

8. **`supplier_reliability_v1` Dataset** (Weeks 11-12)
   - Supplier-month grain
   - Composite reliability label from delivery + quality data
   - Country risk + port disruption + sanctions features

### Phase 4: Optimization (Weeks 13-16)

9. **Point-in-Time Feature Store** (Weeks 13-14)
   - `get_features(entity_id, as_of)` time-travel API
   - Offline (Parquet) + Online (Redis) separation
   - Feature versioning automation
   - Feature freshness monitoring

10. **`procurement_optimization_v1` Dataset** (Weeks 14-15)
    - Feeds from: commodity_forecast + port_disruption + supplier_reliability + geopolitical
    - Composite dataset with predictions-as-features
    - Optimization targets (order quantity, timing, supplier)

11. **`spr_optimization_v1` Dataset** (Weeks 15-16)
    - Country-month grain
    - SPR decision targets
    - Multi-horizon strategic labels

### Phase 5: Intelligence (Weeks 17-20)

12. **`energy_security_index_v1` Dataset** (Weeks 17-18)
    - Country-month composite index
    - 6 sub-indices from all upstream data
    - Executive dashboard output

13. **`digital_twin_v1` Environment** (Weeks 19-20)
    - RL environment with state/action/reward definitions
    - Scenario generators (price shock, conflict, weather)
    - Gym-compatible interface

### Phase 6: Automation & Quality (Ongoing)

- **Auto-feature engine** improvements (rolling, volatility, entity centrality, news velocity)
- **Dataset profiling automation** (8 output reports per build)
- **Quality gates** (reject/quarantine below-threshold datasets)
- **Freshness monitoring** + alerting for stale features
- **Cross-source deduplication** (GDELT identity resolution)
- **Implementation of stub builders** (all 12 builders from data lake sources)

---

## 9. Appendix: Feature Catalog

| Feature | Type | Dataset(s) | Transform | Source Fields |
|---|---|---|---|---|
| `event_count` | numerical | geopolitical_risk | count | GDELT GlobalEventID |
| `event_count_7d_rolling` | numerical | geopolitical_risk | rolling_window(7, 'count') | GDELT GlobalEventID |
| `avg_goldstein_scale` | numerical | geopolitical_risk | mean | GDELT GoldsteinScale |
| `goldstein_volatility_7d` | numerical | geopolitical_risk | rolling_window(7, 'std') | GDELT GoldsteinScale |
| `avg_tone` | numerical | geopolitical_risk, commodity_forecast | mean | GDELT AvgTone |
| `tone_volatility_7d` | numerical | geopolitical_risk | rolling_window(7, 'std') | GDELT AvgTone |
| `conflict_event_ratio` | numerical | geopolitical_risk | ratio | GDELT EventCode (conflict codes) |
| `negative_tone_ratio` | numerical | geopolitical_risk | ratio | GDELT AvgTone < 0 |
| `unique_actor1_count` | numerical | geopolitical_risk | nunique | GDELT Actor1Code |
| `theme_count` | numerical | geopolitical_risk, commodity_forecast | count | GKG V2Themes |
| `waiting_days_7d_avg` | numerical | port_disruption_risk | rolling_window(7, 'mean') | PortCongestion waiting_days |
| `vessel_count_7d_avg` | numerical | port_disruption_risk | rolling_window(7, 'mean') | PortCongestion vessel_count |
| `congestion_level_trend` | categorical | port_disruption_risk | trend extraction | PortCongestion congestion_level |
| `vessels_approaching_7d` | numerical | port_disruption_risk | count | AIS destination matches port |
| `avg_speed_approach` | numerical | port_disruption_risk | mean | AIS speed, filtered by approach |
| `nearby_events_50km_7d` | numerical | port_disruption_risk | haversine_filter + count | GDELT Geo_Lat/Long + port coordinates |
| `distance_to_chokepoint` | geospatial | port_disruption_risk, maritime_risk | haversine | Port coordinates + chokepoint coordinates |
| `price_7d_avg` | numerical | commodity_forecast | rolling_window(7, 'mean') | CommodityPrices price |
| `price_30d_avg` | numerical | commodity_forecast | rolling_window(30, 'mean') | CommodityPrices price |
| `rsi_14` | numerical | commodity_forecast | rsi(14) | CommodityPrices price |
| `macd` | numerical | commodity_forecast | macd(12, 26, 9) | CommodityPrices price |
| `bollinger_pct` | numerical | commodity_forecast | bollinger(20, 2) | CommodityPrices price |
| `front_month_price` | numerical | commodity_forecast | filter_front_month | CommodityFutures price, contract_month |
| `contango_backwardation_flag` | boolean | commodity_forecast | compare(front, back) | CommodityFutures front/back month |
| `opec_production` | numerical | commodity_forecast | sum | OPEC production_kbbl per country |
| `eia_inventories` | numerical | commodity_forecast | filter_series | EIA series_id matching inventory |
| `usd_index` | numerical | commodity_forecast | join | FRED series "DTWEXBGS" |
| `ship_type_category` | categorical | maritime_risk | map | AIS ShipType → category |
| `speed_avg_7d` | numerical | maritime_risk | rolling_window(7, 'mean') | AIS Speed |
| `speed_std_7d` | numerical | maritime_risk | rolling_window(7, 'std') | AIS Speed |
| `course_variance` | numerical | maritime_risk | circular_variance | AIS Course |
| `loitering_hours` | numerical | maritime_risk | loitering_detection | AIS speed < 0.5 knots duration |
| `events_along_route_100km_7d` | numerical | maritime_risk | spatial_join | GDELT + vessel route |
| `flag_country_risk_score` | numerical | maritime_risk | join | AIS flag_country → geopolitical_risk_index |
| `throughput_z_score` | numerical | infrastructure_anomaly | z_score | Energy Service throughput |
| `utilization_rate` | numerical | infrastructure_anomaly | ratio | throughput / capacity |
| `vessel_visits_deviation` | numerical | infrastructure_anomaly | z_score | AIS visits count |
| `nearby_event_type_diversity` | numerical | infrastructure_anomaly | shannon_entropy | GDELT EventCode near asset |
| `supplier_country_risk_score` | numerical | supplier_reliability | join | Supplier country → geopolitical_risk_index |
| `sanctions_active_flag` | boolean | supplier_reliability, maritime_risk | join | Sanctions list contains entity |
| `past_reliability_3m` | numerical | supplier_reliability | rolling_window(3, 'mean') | Historical delivery records |
| `port_disruption_probability_4w` | numerical | procurement_optimization | forecast | port_disruption_risk model output |
| `price_forecast_4w` | numerical | procurement_optimization | forecast | commodity_forecast model output |
| `current_inventory_level` | numerical | procurement_optimization | direct | Inventory records |
| `days_of_cover` | numerical | procurement_optimization | ratio | inventory / daily_consumption |
| `safety_stock` | numerical | procurement_optimization | formula | lead_time_demand * σ * z_score |
| `global_risk_index_3m_avg` | numerical | spr_optimization | rolling_window(90, 'mean') | geopolitical_risk_index |
| `supply_deficit_probability_3m` | numerical | spr_optimization | forecast | commodity_forecast + production data |
| `current_spr_level` | numerical | spr_optimization | direct | EIA SPR data |
| `spr_days_of_cover` | numerical | spr_optimization | ratio | spr_level / daily_consumption |
| `import_dependency` | numerical | energy_security_index | ratio | net_imports / total_consumption |
| `supply_hhi` | numerical | energy_security_index | hhi | Supply source concentration |
| `renewable_share` | numerical | energy_security_index | ratio | renewable_generation / total_generation |

---

*End of Architecture Document v2. Ready for review and approval before implementation begins.*
