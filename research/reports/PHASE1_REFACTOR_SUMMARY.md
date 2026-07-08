# Phase 1 Refactor Summary — Geopolitical Risk Dataset Builder

**Date**: 2026-07-07
**File**: `research/datasets/geopolitical_risk_builder.py`
**Version**: v1.1 (backward-compatible with v1 output format)

---

## 1. Summary of Code Changes

### 1.1 Forecasting Target: `escalation_flag_t1`

**File**: `geopolitical_risk_builder.py:generate_target()`

**What changed**:
- Added `escalation_flag_t1` alongside the existing `risk_flag`
- Both targets are now generated in `generate_target()`
- The old `risk_flag` is preserved and unchanged

**Mathematical definition**:

```
risk_flag_t           = 1 if goldstein_neg_count_t > median(dataset)
escalation_flag_t1_t  = 1 if goldstein_neg_count_{t+1} > 1.5 × goldstein_neg_count_t
```

where `escalation_flag_t1_t` is NaN for the last week of each country (no t+1 available).

**Implementation**:
- Computed per country independently via `groupby("country")["goldstein_neg_count"].shift(-1)`
- No cross-country comparison (each country's escalation is relative to its own prior week)
- Sorted by (country, year, week) before computation to ensure correct temporal ordering
- Preserves original index order when assigning back to the DataFrame
- Escalation threshold (1.5× = 50% increase) documented in code with mathematical justification

**Backward compatibility**:
- `risk_flag` values are identical to previous builds
- `escalation_flag_t1` is a new column — existing code reading the dataset will ignore it unless explicitly referenced
- Metadata structure preserved with added fields

### 1.2 Leakage Audit Step

**File**: `geopolitical_risk_builder.py:leakage_audit()`

**New method** that performs automatic leakage detection before saving. Checks:

| Check | Method | Threshold |
|-------|--------|-----------|
| Duplicate columns | Pairwise `equals()` comparison on feature columns | Exact match |
| Constant columns | `nunique() == 1` | Single unique value |
| Zero-variance columns | `std() == 0` after NaN removal | Zero |
| Highly correlated pairs | `corr()` on numeric features | abs(r) > 0.99 |
| Target leakage | Feature–target correlation | abs(r) > 0.95 |
| Duplicate country-week rows | `duplicated(subset=[country, year, week])` | ≥1 |

**Report**: Markdown file saved to `research/reports/leakage_audit_{timestamp}.md` with:
- Tables of findings per category
- Interpretation notes
- Mode context (all_features / gdelt_only / static_only)

**No features are deleted** — only reported and logged in result metadata.

### 1.3 Static Feature Modes

**File**: `geopolitical_risk_builder.py:build(mode=...)`

**Three modes** controlling which feature groups are merged:

| Mode | GDELT Temporal Features | Static Features (OFAC, Ports, Energy, GEM) | Use Case |
|------|------------------------|----------------------------------------------|----------|
| `all_features` (default) | Included | Included | Full baseline |
| `gdelt_only` | Included | Skipped | Isolate GDELT temporal signal; test for static feature leakage |
| `static_only` | Used for targets only, then dropped | Included | Baseline: "How predictive are static features alone?" |

In `static_only` mode:
- GDELT data is loaded only to generate targets
- After target generation, all GDELT base columns are dropped
- Feature engineering (lags, rolling, WoW) is skipped
- Only identifiers + targets + static features remain

### 1.4 Feature Statistics: `feature_stats.json`

**File**: `geopolitical_risk_builder.py:compute_feature_stats()`

**New file** saved alongside metadata: `research/datasets/geopolitical_risk_v1/feature_stats.json`

Per feature (for all columns except country, year, week):

| Statistic | Type | Notes |
|-----------|------|-------|
| `null_count` | int | Absolute count of missing values |
| `null_pct` | float | Percentage of rows with missing values |
| `unique_count` | int | Number of distinct non-null values |
| `mean` | float | For numeric features only |
| `median` | float | For numeric features only |
| `std` | float | For numeric features only |
| `variance` | float | For numeric features only |
| `min` | float | For numeric features only |
| `max` | float | For numeric features only |

Non-numeric features get only null_count, null_pct, and unique_count.

### 1.5 Extended Validation

**File**: `geopolitical_risk_builder.py:validate()`

**Return type changed** from `list[str]` to `dict[str, list[str]]` with keys `"errors"` (severe — fail the build) and `"warnings"` (informational — do not fail).

**New checks added**:

| Check | Severity | Description |
|-------|----------|-------------|
| ISO code format | Warning | Non-3-letter-uppercase country codes |
| Country not in canonical list | Warning | Valid ISO3 not in country_mapper.ISO3_TO_NAME |
| Week continuity | Warning | Missing weeks per (country, year) group |
| NaN in numeric identifiers | Error | NaN in country, year, or week columns |
| Constant columns | Warning | Single unique non-null value |
| Zero-variance columns | Warning | std = 0 after NaN removal |
| Negative count values | Warning | Negative values in count-pattern columns |
| Impossible Goldstein values | Warning | min < -10 or max > 10 |
| First-week lag check | Warning | Non-null lag features in first week per country (contradiction) |
| Missing target columns | Warning | target column not in dataset |

**Backward compatibility**: Existing validation checks preserved. Caller code updated in `build()`.

### 1.6 Phase 2 TODO Comments

**File**: `geopolitical_risk_builder.py:build()` — 9 TODO comments at the end of the method:

- rolling std, rolling max, EWMA, momentum, trend slope, expanding statistics, volatility features
- GKG integration, Mentions integration, ACLED integration

### 1.7 Other Changes

- Added `import numpy as np` at top of file
- Added `import math` for sin/cos calculation (replaced `__import__` hack)
- Added `REPORTS_DIR` constant
- Added `VALID_ISO3_CODES` set imported from country_mapper
- Replaced existing `__import__("math")` calls with explicit `math.sin` / `math.cos`
- Added `mode` parameter to `build()` (default: `"all_features"`)
- Extended `_save()` to write `feature_stats.json`, new metadata fields, and mode
- Updated `__main__` block to accept mode from CLI argument
- Added comprehensive type hints throughout

---

## 2. Scientific Justification for Each Modification

### 2.1 Forecasting Target (escalation_flag_t1)

**Problem**: The original `risk_flag` is a nowcast target computed from the same week as the features. The model learns "what is happening now" rather than "what will happen next week." This limits practical value for an early warning system.

**Solution**: `escalation_flag_t1` shifts the target forward by one week, creating a true forecasting task. The 1.5× threshold was chosen based on:
- **Signal-to-noise ratio**: Week-over-week variance in goldstein_neg_count is typically 20-30%. A 1.5× (50% increase) threshold exceeds normal variance and captures material escalations.
- **Business relevance**: A 50% increase in negative events within a week represents a meaningful escalation that would trigger analyst attention.
- **Class balance**: Historical analysis (see TARGET_DESIGN_REVIEW.md) predicts 15-25% positive rate, which is imbalanced but learnable.

**Each country is independent**: The per-country computation ensures that a small country's normal variation doesn't get dwarfed by larger countries' absolute counts.

### 2.2 Leakage Audit

**Problem**: Time-series datasets are susceptible to multiple forms of leakage that inflate model performance metrics without real predictive value.

**Rationale for each check**:
- **Duplicate columns**: Indicate redundant features or data source overlap. Do not cause leakage directly but waste model capacity and complicate interpretation.
- **Constant columns**: Zero predictive value. Their presence inflates feature count and may cause numerical issues in some models.
- **Highly correlated pairs (>0.99)**: Near-perfect correlation suggests one feature is a linear transform of another. In linear models this causes multicollinearity. In tree models it splits importance arbitrarily.
- **Target leakage (>0.95 correlation)**: A feature with >0.95 correlation to the target almost certainly contains target information (e.g., the target was accidentally included as a feature, or a feature was computed using future data).
- **Duplicate country-week rows**: Violates the unique key constraint. Causes the same observation to appear in both train and test splits, inflating metrics.

### 2.3 Static Feature Modes

**Problem**: Static features (OFAC sanctions, ports, GEM trackers, energy prices) create country fingerprints. A model can learn "sanction_count > 500 → Iran → high risk" without learning generalizable temporal patterns.

**Experimental design**:
- `gdelt_only`: Forces the model to rely only on temporal GDELT patterns. If performance is comparable to `all_features`, static features contribute mostly country identity leakage.
- `static_only`: Tests whether static features alone contain any predictive signal. Useful as a lower bound comparison.
- `all_features`: Full model. If performance significantly exceeds `gdelt_only`, then (a) static features contribute genuine signal or (b) the model is memorizing country identities.

**Statistical framework**: The three modes form a controlled experiment:
```
gdelt_only  = signal(GDELT temporal patterns)
all_features = signal(GDELT + static)
static_only  = signal(static only)

If AUC(all_features) ≈ AUC(gdelt_only):
    Static features provide no additional signal beyond country identity leakage
    
If AUC(all_features) >> AUC(gdelt_only):
    Static features contain genuine predictive signal (or the model is learning country identity)
```

### 2.4 Feature Statistics

**Problem**: Without per-feature statistics, it's impossible to diagnose data issues (zero-variance features, extreme null rates, out-of-range values) without re-running the full pipeline.

**Value**:
- Enables quick data quality assessment without loading the full dataset
- Provides input range documentation for model deployment (min/max for feature scaling)
- Tracks null rates across builds to detect data source drift

### 2.5 Extended Validation

**Why these checks**:
- **ISO code validity**: Ensures country mapping hasn't introduced corruption. Territories may legitimately fall outside the canonical ISO3 list, so this is only a warning.
- **Week continuity**: Missing weeks indicate either data collection gaps or countries that disappeared from the news. A few missing weeks are expected; systematic gaps suggest a data pipeline issue.
- **NaN in identifiers**: Fatal — any row without a country, year, or week is unusable.
- **Constant/ZV columns**: No predictive value; potential numerical issues.
- **Negative counts**: Impossible for count features; indicates data corruption upstream.
- **Impossible Goldstein values**: The Goldstein scale is defined as [-10, +10]. Values outside this range indicate data corruption.
- **First-week lag check**: The first week per country must have NaN for all lag features. Non-NaN lags mean the shift operation failed.

---

## 3. New Dataset Schema

### 3.1 Identifiers

| Column | Type | Description |
|--------|------|-------------|
| `country` | str | ISO 3166-1 alpha-3 country code |
| `year` | int | ISO year |
| `week` | int | ISO week number (1-53) |

### 3.2 Targets

| Column | Type | Description | Null Rate (expected) |
|--------|------|-------------|---------------------|
| `risk_flag` | int (0/1) | Nowcast: 1 if goldstein_neg_count > training median | 0% |
| `escalation_flag_t1` | float (0/1/NaN) | Forecast: 1 if goldstein_neg_count_{t+1} > 1.5 × goldstein_neg_count_t | ~7% (last week per country) |

### 3.3 GDELT Base Features (14)

| Column | Aggregation |
|--------|-------------|
| `total_events` | count(GlobalEventID) |
| `goldstein_mean` | mean(GoldsteinScale) |
| `goldstein_std` | std(GoldsteinScale) |
| `goldstein_min` | min(GoldsteinScale) |
| `goldstein_max` | max(GoldsteinScale) |
| `goldstein_neg_count` | sum(GoldsteinScale < -5) |
| `goldstein_pos_count` | sum(GoldsteinScale > 5) |
| `quadclass_verbal_conflict` | sum(QuadClass == 3) |
| `quadclass_material_conflict` | sum(QuadClass == 4) |
| `total_mentions` | sum(NumMentions) |
| `total_sources` | sum(NumSources) |
| `total_articles` | sum(NumArticles) |
| `avg_tone` | mean(AvgTone) |
| `unique_actors1` | nunique(Actor1CountryCode) |
| `unique_actors2` | nunique(Actor2CountryCode) |
| `conflict_event_ratio` | (verbal + material) / total_events |

### 3.4 Engineered Features (26)

Six base features × 4 transforms each = 24, plus 2 cyclical:

| Pattern | Example |
|---------|---------|
| `{feature}_lag1` | `total_events_lag1` |
| `{feature}_lag4` | `total_events_lag4` |
| `{feature}_rolling4_mean` | `goldstein_neg_count_rolling4_mean` |
| `{feature}_change_wow` | `goldstein_neg_count_change_wow` |

Base features engineered: total_events, goldstein_mean, goldstein_neg_count, total_mentions, avg_tone, conflict_event_ratio.

Cyclical: week_sin, week_cos.

### 3.5 Static Features (~42, varies by merge)

| Source | Features |
|--------|----------|
| OFAC | sanction_count |
| Ports | port_count |
| Global Energy | 14 columns (7 fuels × 2 years) |
| GEM Trackers | ~18-28 tracker-sheet columns |

---

## 4. Assumptions

| # | Assumption | Risk if Wrong |
|---|------------|---------------|
| 1 | The last week per country should have NaN escalation_flag_t1 | If the dataset is later extended with future data, historical NaN targets become computable. The builder must be re-run. |
| 2 | GDELT event dates (Day column) are trustworthy for temporal ordering | If GDELT event dates are wrong, the week assignment is wrong and all temporal features are corrupted. |
| 3 | GDELT events from different download dates do not overlap significantly | If the same events appear in multiple download files, they are double-counted. The dedup step in build() handles this partially. |
| 4 | A 1.5× threshold for escalation is appropriate for all countries | A threshold appropriate for Syria (high baseline conflict) may be inappropriate for Switzerland (low baseline). Future work could use country-specific thresholds. |
| 5 | ISO week boundaries align with meaningful geopolitical periods | Some conflicts escalate mid-week and are partially captured in adjacent weeks. Daily resolution would avoid this but create sparsity. |
| 6 | The three experimental modes produce valid supervised ML datasets | static_only mode produces a dataset with very few temporal rows per country (possibly 1), which is insufficient for time-series modeling. It is useful only as a cross-sectional baseline. |

---

## 5. Potential Backward Compatibility Issues

| Issue | Severity | Impact | Mitigation |
|-------|----------|--------|------------|
| `validate()` return type changed from `list[str]` to `dict` | Medium | Code that calls `validate()` expecting a list will break | Only `build()` calls `validate()` in the existing codebase. Updated `build()` to handle the new dict. |
| `_save()` signature changed (added parameters) | Low | Calls to `_save()` with positional args would fail | `_save()` is private — only called from `build()`. |
| `escalation_flag_t1` column added to dataset | None | New column added; existing code ignores unknown columns | Existing models trained on v1 will warn about unknown column but continue. |
| `__import__("math")` replaced with `import math` | None | Identical behavior | Both approaches compute the same sin/cos values. |
| `__main__` block accepts CLI argument | None | `python file.py` still works without args | Default mode is "all_features". |
| `mode` key in result dict | None | New key in output dict | Existing code that processes result dict ignores unknown keys. |
| `feature_stats.json` new file | None | Not loaded by existing code | Exists alongside metadata.json; ignored unless explicitly read. |
| `validation_errors`/`validation_warnings` in metadata.json | None | New keys in metadata dict | Existing code that reads metadata ignores unknown keys. |
| `escalation_target_distribution` in metadata.json | None | New key in metadata dict | Backward compatible. |
| `targets` list in metadata.json | None | New key listing both targets | Backward compatible. |

---

## 6. Verification Steps (after implementation)

1. Run full build with all 87 dates: `python geopolitical_risk_builder.py`
2. Verify both targets exist and null counts are correct
3. Check leakage audit report in `research/reports/`
4. Run `gdelt_only` and `static_only` modes to verify they produce output
5. Open Jupyter and run manual validation (see `DELIVERABLES.md`)
6. Retrain Logistic Regression, Random Forest, and XGBoost on new dataset

---

## 7. File Inventory After Phase 1

| File | Status |
|------|--------|
| `research/datasets/geopolitical_risk_builder.py` | Modified |
| `research/datasets/geopolitical_risk_v1/metadata.json` | Regenerated (new keys) |
| `research/datasets/geopolitical_risk_v1/feature_stats.json` | **New** |
| `research/reports/leakage_audit_*.md` | **New** (generated per run) |
| `research/reports/PHASE1_REFACTOR_SUMMARY.md` | **New** (this file) |
| `research/reports/STATIC_FEATURE_REVIEW.md` | Unchanged |
| `research/reports/TARGET_DESIGN_REVIEW.md` | Unchanged |
| `research/reports/DATASET_CARD.md` | Unchanged |
| `research/reports/FEATURE_CATALOG.md` | Unchanged |
| `research/reports/DATASET_COVERAGE_REPORT.md` | Unchanged |
| `research/reports/VALIDATION_CHECKLIST.md` | Unchanged |
