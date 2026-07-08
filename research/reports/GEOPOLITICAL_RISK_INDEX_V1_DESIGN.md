# Geopolitical Risk Index v1 — Dataset Design

## Objective
Build a supervised ML dataset that predicts geopolitical risk at the country-week level. The model learns patterns from historical events, media attention, sanctions, and energy infrastructure to flag weeks where a country experiences significant negative geopolitical events.

## Target Variable

### Primary: `risk_flag` (binary classification)
- **Positive class (1)**: Country-week has > median number of negative Goldstein scale events (Goldstein < -5)
- **Negative class (0)**: Country-week has ≤ median negative events
- Rationale: Binary targets are clean, interpretable, and allow straightforward evaluation (precision, recall, F1)

### Secondary (extensible): `mean_goldstein` (regression)
- Continuous: Mean Goldstein scale of all events in country-week
- Useful as auxiliary output or for regression baselines

### Tertiary: `risk_level` (multi-class, future v2)
- Low: Goldstein mean >= 0, no negative events
- Medium: Some negative events but below threshold
- High: Above median negative events
- Critical: Extreme negative events (Goldstein < -8 or event count > 95th percentile)

## Grain
- **Country** (ISO 3166-1 alpha-3)
- **Week** (ISO week number, 1-53)
- **Year**
- Unique key: `(country, year, week)`

### Why country-week?
- Country: Natural geopolitical unit, all sources have country identifiers
- Week: Smooths daily noise while preserving temporal signal; enough rows for ML (52 per country/year)
- Trade-off: Day is too sparse (many zero-event days), month is too coarse (blends crises over 30 days)

## Prediction Horizon
- **Nowcasting (t)**: Predict current week's risk using features from same week
- **Forecasting (t+1)**: Predict next week's risk using features up to current week
- v1 focuses on nowcasting; forecasting requires more temporal engineering

## Feature Domains

| Domain | Source | Features | Temporality |
|--------|--------|----------|-------------|
| Event Activity | GDELT Events | Event counts by type (root code), Actor1/Actor2 stats, Goldstein stats (mean, min, max, std) | Weekly |
| Media Attention | GDELT Mentions | Mention count, source diversity (unique sources/articles) | Weekly |
| Knowledge Graph | GDELT GKG | Theme counts, tone stats (avg, min, max), entity mentions | Weekly |
| Sanctions | OFAC SDN | Sanction count by country, sanction type distribution | Static (current snapshot) |
| Energy Infrastructure | GEM Trackers | Plant counts by type (coal, gas, solar, wind, nuclear, hydro, bioenergy, geothermal), pipeline length (km) by status | Static (current snapshot) |
| Ports | Ports | Port count, total vessel capacity, port type distribution | Static |
| Global Energy | global_energy_2025/2026 | Production/consumption by energy type, by country | Static (annual) |
| Temporal | Engineered | Week of year, month, quarter, year | Weekly |

## Country Mapping Strategy

Different sources use different country identifiers:

| Source | Country Field | Format | Mapping Needed |
|--------|--------------|--------|---------------|
| GDELT Events | Actor1Geo_CountryCode | FIPS 2-letter | FIPS → ISO alpha-3 |
| GDELT Mentions | (joined via EventID to Events) | — | Inherit from Events |
| GDELT GKG | (joined via GKGRECORDID to Events) | — | Inherit via V2Themes/event mapping |
| OFAC SDN | program, type | Text | Fuzzy match country name → ISO |
| GEM Trackers | Country (varies by tracker) | Text/Mixed | Clean country name → ISO |
| Ports | country | Text | Clean country name → ISO |
| Global Energy | Various (country, location) | Text | Clean country name → ISO |

**Resolution**: Build `research/datasets/country_mapper.py` — a centralized mapping module with FIPS→ISO, country name→ISO, fuzzy matching fallback.

## Static Feature Extraction (from non-temporal sources)

### OFAC Sanctions → Country Features
- Count of sanctions by country
- Sanction type distribution (SDN, etc.)
- Program/regime distribution

### GEM Trackers → Country Features
For each tracker, extract:
- Total plant/facility count by country
- Capacity (MW, tonnes) by country
- Status distribution (operating, construction, announced, retired)
- Fuel type distribution

### Ports → Country Features
- Port count by country
- Vessel capacity statistics by country
- Port function type distribution

## Temporal Feature Engineering

### Lag Features (t-1, t-2, t-4)
- Previous week's Goldstein stats
- Previous week's event counts
- Previous week's mention counts

### Rolling Features
- 4-week moving average of Goldstein
- 4-week rolling event count
- 4-week rolling mention count

### Rate of Change
- Week-over-week change in event count
- Week-over-week change in mean Goldstein

## Data Splitting Strategy

### Temporal Split (no random shuffle — prevent leakage)
- **Train**: Weeks 1-40 of available time range
- **Validation**: Weeks 41-46
- **Test**: Weeks 47-52

### Why temporal split?
- Geopolitical events have temporal autocorrelation
- Random splits leak future information into training
- Real-world deployment requires predicting future, not past

## Dataset Size Estimate

With 1 year of GDELT data:
- ~200 countries × 52 weeks = ~10,400 rows
- After filtering to countries with any events: ~100 countries × 52 weeks = ~5,200 rows
- Feature count: 50-100 (depends on feature engineering choices)
- Target prevalence: ~20-30% positive class (varies by threshold)

## Pipeline Architecture

```
GDELT Pipeline (discover → download → parse)
        ↓
country-week aggregation (Events + Mentions + GKG)
        ↓
OFAC Sanctions → country features
        ↓
GEM Trackers → country features
        ↓
Ports → country features
        ↓
Global Energy → country features
        ↓
Join all feature domains by (country, year, week)
        ↓
Engineer temporal features (lags, rolling, rate-of-change)
        ↓
Generate targets (risk_flag, mean_goldstein)
        ↓
Remove leakage (no future data in features)
        ↓
Temporal train/val/test split
        ↓
Validate (schema, duplicates, leakage check)
        ↓
Register in dataset catalog
```

## Versioning
- Dataset version: v1 (incremented for schema changes, new features, new data)
- All versions logged to ML Platform's `ml.datasets` table
- Associated with `feature_version` for feature store lineage
- DVC tracked for data versioning

## Success Criteria
- Binary classification F1 ≥ 0.70 on test set
- No temporal leakage in features
- Precision ≥ 0.75 (minimize false alarms)
- Recall ≥ 0.60 (capture most risk events)
- Feature importance interpretable (SHAP analysis)
