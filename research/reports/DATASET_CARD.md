# Dataset Card — geopolitical_risk_index_v1

## Dataset Overview

| Field | Value |
|-------|-------|
| **Name** | `geopolitical_risk_index_v1` |
| **Version** | 1.0 |
| **Created** | 2026-07-07 |
| **Format** | Apache Parquet (4 files: full, train, val, test) |
| **Location** | `research/datasets/geopolitical_risk_v1/` |
| **Size** | ~930 KB (5,953 rows) |
| **Builder** | `research/datasets/geopolitical_risk_builder.py` |
| **Reproducibility** | Deterministic build — same inputs produce identical output |

---

## Objective

Predict geopolitical risk at the country-week level using global event data, sanctions, energy infrastructure, and media attention. The model is designed to support the ProxyDefence Energy Supply Chain Resilience platform by providing early warning of disruptive geopolitical events.

---

## Target

### Current Target
- **Name**: `risk_flag`
- **Type**: Binary classification
- **Definition**: 1 if `goldstein_neg_count` > median of training set, else 0
- **Distribution**: 3,015 negative (0) / 2,938 positive (1) — 49.3% positive rate
- **Status**: ⚠️ **Under review** — see `TARGET_DESIGN_REVIEW.md`

### Proposed Target (for v2)
- **Name**: `escalation_flag_{t+1}`
- **Type**: Binary classification
- **Definition**: 1 if `goldstein_neg_count_{t+1}` > `goldstein_neg_count_t` × 1.5
- **Prediction horizon**: +1 week forward
- **Status**: Proposed, not yet implemented

---

## Prediction Horizon

| Horizon | Status | Definition |
|---------|--------|------------|
| Nowcast (t) | ✅ Current | Features and target from same week |
| Forecast (t+1) | 🔄 Proposed | Features from week t, target from week t+1 |
| Forecast (t+2) | ❌ Future | Not yet designed |

---

## Grain

- **Primary key**: `(country, year, week)`
- **Country**: ISO 3166-1 alpha-3
- **Time**: ISO week calendar
- **Rows**: 5,953 unique country-weeks
- **Countries**: 224
- **Weeks**: 14 (ISO weeks 1-13 of 2024)

---

## Features by Category

| Category | Count | Description |
|----------|-------|-------------|
| Base temporal | 14 | GDELT event volume, tone, conflict, actor diversity |
| Temporal lags | 12 | Values from 1 and 4 weeks prior |
| Rolling windows | 6 | 4-week moving averages |
| WoW change | 6 | Week-over-week differences |
| Cyclical | 2 | Sin/cos encoding of week number |
| Static | ~42 | OFAC, ports, energy prices, GEM infrastructure |
| **Total** | **~82** | |

---

## Data Sources

| Source | Type | Temporal | Countries | Used For |
|--------|------|----------|-----------|----------|
| GDELT 2.0 Events | News events | Daily (15-min) | 224 | Core temporal features |
| OFAC SDN | Sanctions list | Static | 47 | Sanction intensity |
| Ports database | Infrastructure | Static | 159 | Maritime exposure |
| Global Energy Monitor | Infrastructure | Static | 207 | Energy asset presence |
| Global Energy Pricing | Market prices | Static (annual) | 10 | Fuel price levels |

### Sources NOT Yet Integrated
- GDELT Mentions (media diversity)
- GDELT GKG (themes, topics)
- ACLED Political Violence (independent conflict data)
- AEO Energy Outlooks (energy price forecasts)

---

## Joins

```
              ┌──────────────────────────┐
              │  GDELT Events            │
              │  (country × week pivot)  │
              │  grain: country,week     │
              └───────────┬──────────────┘
                          │ LEFT JOIN on country
              ┌───────────┼──────────────┐
              │           │              │
     ┌────────┴──┐  ┌────┴────┐  ┌──────┴──────┐
     │  OFAC     │  │ Ports   │  │ GEM + Energy│
     │(country)  │  │(country)│  │ (country)   │
     └───────────┘  └─────────┘  └─────────────┘
```

All joins are LEFT JOIN on ISO3 country code. Static tables have 1 row per country, which is broadcast to all weeks for that country.

---

## Assumptions

| # | Assumption | Risk if Wrong |
|---|------------|---------------|
| 1 | GDELT event coverage is balanced across countries | Countries with less English-language news coverage are systematically underrepresented |
| 2 | GoldsteinScale is a valid proxy for geopolitical risk | Goldstein measures cooperation/conflict, not risk specifically |
| 3 | 14 weeks of data captures meaningful temporal patterns | Seasonal or annual patterns cannot be learned from 3 months |
| 4 | Static features provide useful context beyond country identity | Static features may cause country-level overfitting (see STATIC_FEATURE_REVIEW) |
| 5 | FIPS → ISO3 mapping is lossless | Some FIPS codes map to territories not in ISO3, causing data loss |
| 6 | OFAC country names map cleanly to ISO3 | ~17K entries have "-0-" (no country), limiting sanction feature coverage |

---

## Limitations

### 1. Temporal Coverage
Only 14 weeks (Q1 2024). This is insufficient for:
- Learning seasonal patterns
- Training models for annual risk cycles
- Evaluating model performance across different geopolitical regimes

### 2. Nowcasting, Not Forecasting
The current target (`risk_flag`) is computed from the same week as the features. This produces a descriptive model, not a predictive one. A forecasting target (t+1) is proposed but not implemented.

### 3. Static Feature Leakage
Static features (sanction_count, port_count, GEM indicators) create country fingerprints. The model may learn country identity rather than generalizable risk patterns. Cross-validation by country is recommended.

### 4. Data Source Bias
GDELT is primarily English-language news. This systematically underreports events in:
- Non-English-speaking countries
- Countries with limited press freedom
- Regions with less international news interest

### 5. No External Validation
The dataset has not been validated against independent conflict measures (ACLED, UCDP, etc.). We cannot confirm whether GDELT-based risk flags correlate with real-world outcomes.

### 6. Energy Pricing Mismatch
Global energy pricing data (2025/2026) is temporally misaligned with GDELT events (2024). This data should not be used as-is for time-series modeling.

### 7. No GKG/Mentions Integration
GDELT's Knowledge Graph (themes, emotions) and Mentions (source diversity) are available but not yet integrated. These would provide richer feature sets.

---

## Intended Consumers

| Consumer | Use Case | Priority |
|----------|----------|----------|
| **ML Platform** (services/ml-platform/) | Model training, inference, prediction API | Primary |
| **Research** (research/experiments/) | Baseline models, feature experiments, error analysis | Primary |
| **Energy Service** (services/energy-service/) | Contextual risk scoring for energy assets | Secondary |
| **Frontend** (services/frontend/) | Risk dashboard, alerting | Tertiary |

---

## Versioning and Updates

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-07-07 | Initial release. GDELT + static features. 14 weeks. |
| v1.1 | TBD | Fix target to forecast (t+1) |
| v1.2 | TBD | Integrate GKG and Mentions features |
| v2 | TBD | Expanded temporal coverage (12+ months) |
| v2.1 | TBD | Add ACLED validation |

---

## Related Documentation

| Document | Location |
|----------|----------|
| Target Design Review | `research/reports/TARGET_DESIGN_REVIEW.md` |
| Static Feature Review | `research/reports/STATIC_FEATURE_REVIEW.md` |
| Dataset Coverage Report | `research/reports/DATASET_COVERAGE_REPORT.md` |
| Feature Catalog | `research/reports/FEATURE_CATALOG.md` |
| Dataset Design | `research/reports/GEOPOLITICAL_RISK_INDEX_V1_DESIGN.md` |
| Dataset Builder | `research/datasets/geopolitical_risk_builder.py` |

---

## Ethical Considerations

1. **Bias in news coverage**: GDELT overrepresents English-language, Western news sources. Risk predictions may be systematically less accurate for non-English-speaking countries.
2. **Conflict amplification**: The model may learn that "more news coverage = more risk," penalizing countries with active news environments.
3. **Energy vs conflict conflation**: Countries with significant energy infrastructure may appear riskier simply because they are better documented.
4. **Use case limitation**: Predictions should inform human analysts, not automate decisions. The model identifies potentially elevated risk weeks — it does not determine causality or appropriate response.
