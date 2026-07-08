# Manual Validation Checklist — ProxyDefence ML Platform

## Purpose
This checklist is the official verification procedure for every model release. Every item must be verified and signed off before a model can be promoted to staging or production.

## How to Use
1. Start at Stage 1 and proceed in order.
2. For each item, perform the verification manually.
3. Record the result (PASS / FAIL / N/A) and any observations.
4. If any item FAILS, the release is BLOCKED until the issue is resolved.
5. Only after ALL items in a stage PASS, proceed to the next stage.

---

## Stage 1 — Raw Data Inventory

Verify every file in `datasets/raw/` exists and is readable.

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 1.1 | All expected files present | `ls -la datasets/raw/` | No missing files | ☐ |
| 1.2 | No corrupted zip files | `unzip -t *.zip` | All zips pass CRC check | ☐ |
| 1.3 | No empty files | `find . -size 0` | No zero-byte files | ☐ |
| 1.4 | No download artifacts | `ls *.crdownload` | No incomplete downloads | ☐ |
| 1.5 | CSVs open correctly | `pd.read_csv()` on each CSV | No parse errors | ☐ |
| 1.6 | Excel files open correctly | `pd.read_excel()` on each xlsx | No openpyxl errors | ☐ |
| 1.7 | GDELT directories have content | Count files per date dir | ≥96 files per complete date | ☐ |
| 1.8 | AEO text files are readable | Check first 10 lines | Proper ASCII/UTF-8 content | ☐ |

**Stage 1 Sign-off:** _________ **Date:** _________

---

## Stage 2 — Raw Data Schema Validation

Verify every dataset's schema matches expectations.

### 2A. OFAC SDN (`sdn.csv`)

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 2.1 | Row count within expected range | `wc -l` | ~19,000-20,000 | ☐ |
| 2.2 | Column count is consistent | `pd.read_csv(header=None).shape[1]` | 12 columns | ☐ |
| 2.3 | Country column (index 9) has no unexpected nulls | `df[9].isna().sum()` | "-0-" is expected, not NaN | ☐ |
| 2.4 | No binary/garbled characters | Check first/last 5 rows | Clean ASCII text | ☐ |
| 2.5 | Unique country values listable | `df[9].unique()` | ~60 values | ☐ |

### 2B. Ports (`ports.csv`)

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 2.6 | Row count | `len(df)` | ~2,000-2,100 | ☐ |
| 2.7 | Column count | `len(df.columns)` | ~22 columns | ☐ |
| 2.8 | ISO3 column exists and is populated | Check for "ISO3" column | All rows have ISO3 | ☐ |
| 2.9 | No duplicate ports | `df.duplicated().sum()` | 0 | ☐ |
| 2.10 | Country names match ISO3 codes | Spot-check 5 entries | Names correspond to codes | ☐ |

### 2C. Global Energy Pricing

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 2.11 | Both years exist | File check | 2025.csv and 2026.csv | ☐ |
| 2.12 | Column count per file | `len(df.columns)` | ~62 columns | ☐ |
| 2.13 | ISO3 column present | "ISO3" in df.columns | Yes | ☐ |
| 2.14 | Fuel price columns are numeric-parseable | `pd.to_numeric(errors='coerce').isna().sum()` | <10% parsing failures | ☐ |
| 2.15 | Prices are positive | `df[price_cols].min()` | ≥0 | ☐ |
| 2.16 | Date range is 2025/2026 years | `df['year'].unique()` | [2025] or [2026] | ☐ |

### 2D. GDELT Events

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 2.17 | All date directories have extracted CSVs | Count files in `extracted/` per dir | 96 per complete date | ☐ |
| 2.18 | No malformed CSV lines | `pd.read_csv(errors='coerce')` | <0.1% loss | ☐ |
| 2.19 | Tab separation confirmed | Check first line | Tab-separated, not comma | ☐ |
| 2.20 | Column count consistent across files | Check 3 random files | 61 columns | ☐ |
| 2.21 | GoldsteinScale is numeric-parseable | Sample 1000 rows | >80% parseable | ☐ |
| 2.22 | ActionGeo_CountryCode is FIPS 2-letter | Sample 100 rows | 2-letter codes | ☐ |
| 2.23 | Day column is YYYYMMDD format | Sample 100 rows | 8-digit dates | ☐ |
| 2.24 | No duplicate GlobalEventIDs within file | `df['GlobalEventID'].duplicated()` | 0 | ☐ |

### 2E. GEM Trackers

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 2.25 | All expected tracker files exist | Compare against KEY_TRACKERS list | All 9 present | ☐ |
| 2.26 | Each file opens without error | `pd.read_excel()` | No exceptions | ☐ |
| 2.27 | Country column exists in at least one sheet per file | Manual inspection | Has "country" or similar | ☐ |
| 2.28 | No password-protected sheets | `pd.read_excel(sheet_name=None)` | All sheets readable | ☐ |

**Stage 2 Sign-off:** _________ **Date:** _________

---

## Stage 3 — Country Mapping Validation

Verify every country identifier in every dataset maps correctly to ISO3.

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 3.1 | FIPS→ISO3 mapping covers all GDELT country codes | Check `country_mapper.py` FIPS dict | 190+ mappings | ☐ |
| 3.2 | No FIPS code maps to wrong ISO3 | Spot-check 10 codes: FIPS "US" → ISO "USA" | All correct | ☐ |
| 3.3 | OFAC country names map to ISO3 with no name collisions | Check 5 ambiguous names | Correct mapping | ☐ |
| 3.4 | Port ISO3 column matches country name | Cross-check 5 random rows | Consistent | ☐ |
| 3.5 | Global Energy ISO3 column matches country name | Cross-check 5 random rows | Consistent | ☐ |
| 3.6 | Unknown country codes logged | Check builder output for unmapped codes | <1% unmapped | ☐ |
| 3.7 | No data loss from mapping failures | Compare raw country count vs mapped | <5% loss | ☐ |

**Stage 3 Sign-off:** _________ **Date:** _________

---

## Stage 4 — Dataset Builder Correctness

Verify the builder transforms raw data into the correct research dataset.

### 4A. GDELT Aggregation

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 4.1 | All 87 dates processed | Check `stages.gdelt_dates.count` | 87 | ☐ |
| 4.2 | Total raw events matches expected | `stages.gdelt_loaded.raw_events` | ~21.6M | ☐ |
| 4.3 | Country-week count is correct | `stages.gdelt_aggregated.country_weeks` | ~5,953 | ☐ |
| 4.4 | No duplicate (country, year, week) rows | Post-merge check | 0 duplicates | ☐ |
| 4.5 | Each week has multiple countries | Check 3 random weeks | >100 countries each | ☐ |
| 4.6 | GoldsteinScale is correctly aggregated | Manual: sum events in a week, check mean | Mean ≈ sum/count | ☐ |

### 4B. Merge Correctness

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 4.7 | OFAC countries all appear in final dataset | `set(ofac.country) ⊆ set(final.country)` | True | ☐ |
| 4.8 | Port countries all appear in final dataset | `set(ports.country) ⊆ set(final.country)` | True | ☐ |
| 4.9 | GDELT-only countries have NaN static features | Check a country not in OFAC | sanction_count is NaN/0 | ☐ |
| 4.10 | No row explosion from merge | Rows after merge = rows before merge | True (LEFT JOIN) | ☐ |

### 4C. Temporal Split

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 4.11 | Train weeks are chronologically before val weeks | Compare week ranges | Train max < Val min | ☐ |
| 4.12 | Val weeks before test weeks | Compare week ranges | Val max < Test min | ☐ |
| 4.13 | No week appears in multiple splits | Intersection check | Empty intersection | ☐ |
| 4.14 | Train/val/test proportions reasonable | Ratio check | ~80/10/10 or similar | ☐ |

**Stage 4 Sign-off:** _________ **Date:** _________

---

## Stage 5 — Target Validation

Verify the target variable is correctly generated and free from leakage.

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 5.1 | Target is generated from GDELT data only | Check `generate_target()` code | No external data | ☐ |
| 5.2 | Target uses same-week events | Verify Day column is same week as `(year, week)` | Consistent | ☐ |
| 5.3 | No future information in target | Verify median is computed from training weeks only | No test data in median | ☐ |
| 5.4 | Target distribution is as expected | `value_counts()` | ~50/50 for median-based | ☐ |
| 5.5 | No missing target values | `target.isna().sum()` | 0 | ☐ |
| 5.6 | If forecasting target (t+1): features use ≤t data only | Shift check | Feature weeks ≤ target week - 1 | ☐ |
| 5.7 | Random sample inspection: pick 3 rows, manually verify | Manual GDELT lookup | Correct label | ☐ |

**Stage 5 Sign-off:** _________ **Date:** _________

---

## Stage 6 — Feature Engineering Validation

Verify every engineered feature is correctly computed.

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 6.1 | Lag features use previous weeks only | Spot-check: lag1 value = value from week-1 | Consistent | ☐ |
| 6.2 | First week per country has NaN lags | Check countries with only first week | NaN for lag1, lag4 | ☐ |
| 6.3 | Rolling mean does not include future data | Verify min_periods and shift behavior | Rolling uses t, t-1, t-2, t-3 | ☐ |
| 6.4 | WoW change = current - lag1 | Spot-check 5 rows | Accurate | ☐ |
| 6.5 | Week_sin/cos form a unit circle | Check sin² + cos² ≈ 1 | ~1 for all rows | ☐ |
| 6.6 | Static features identical for same country across weeks | Group by country, check variance | Variance = 0 | ☐ |
| 6.7 | No feature has all NaN or all 0 | `df.describe()` | All features have variance | ☐ |

**Stage 6 Sign-off:** _________ **Date:** _________

---

## Stage 7 — Leakage Investigation

Treat every feature as suspicious. Attempt to prove leakage exists.

### 7A. Temporal Leakage

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 7.1 | Rolling windows use only current and past | Check `rolling()` parameters | min_periods, center=False | ☐ |
| 7.2 | No global statistics computed on full dataset | Check min/max/mean computation | Train-only statistics | ☐ |
| 7.3 | Target computed from training median only | Check `generate_target()` | Train median, not global | ☐ |
| 7.4 | Split is chronological, not random | Check weeks in each split | Time-ordered | ☐ |

### 7B. Static Feature Leakage

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 7.5 | No static feature uniquely identifies a country | Variance check | No single feature → 1 country | ☐ |
| 7.6 | Static features are not proxies for country fixed effects | Train model with/without static features | <5% AUC difference | ☐ |
| 7.7 | Same country appears in train and test | Check country sets | True (split is by week, not country) | ☐ |
| 7.8 | Static feature distribution is similar in train/test | KS test or visual check | Not significantly different | ☐ |

### 7C. Label Leakage

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 7.9 | Target does not appear in any feature | Check column list | Target excluded from features | ☐ |
| 7.10 | Feature computation doesn't use target information | Trace `engineer_features()` | No target input | ☐ |
| 7.11 | No inverse correlation (feature = f(target)) | Random 1000 rows, check correlations | No perfect correlations | ☐ |

### 7D. Duplicate Leakage

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 7.12 | No duplicate rows in train | `train.duplicated().sum()` | 0 | ☐ |
| 7.13 | No duplicate rows in test | `test.duplicated().sum()` | 0 | ☐ |
| 7.14 | No overlapping country-weeks between splits | Intersection check | 0 | ☐ |

**Stage 7 Sign-off:** _________ **Date:** _________

---

## Stage 8 — Dataset Quality Assessment

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 8.1 | Target class balance is acceptable | `value_counts(normalize=True)` | >30% minority class | ☐ |
| 8.2 | At least 50 countries have ≥5 weeks of data | Country-week count per country | ≥50 countries | ☐ |
| 8.3 | No feature has >95% null rate | `df.isnull().mean()` | All features ≤95% null | ☐ |
| 8.4 | Feature variance is non-zero for most features | `df.std() > 0`.sum() | >50% of features | ☐ |
| 8.5 | Train has more rows than val+test combined | Compare sizes | True (~80/10/10) | ☐ |
| 8.6 | Dataset is appropriate for supervised ML | Overall assessment | Sufficient rows, features, variance | ☐ |

**Stage 8 Sign-off:** _________ **Date:** _________

---

## Stage 9 — Baseline Model Training

### 9A. Logistic Regression

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 9.1 | Model converges | No convergence warning | Converged | ☐ |
| 9.2 | ROC AUC > 0.5 | `roc_auc_score` | >0.5 (better than random) | ☐ |
| 9.3 | Coefficients are not extreme | `abs(coef)` | <100 | ☐ |
| 9.4 | Precision and recall are balanced | F1 score | Precision ≈ Recall | ☐ |
| 9.5 | Calibration curve is reasonable | `calibration_curve` | Not perfectly diagonal | ☐ |

### 9B. Random Forest

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 9.6 | Model does not achieve perfect 1.0 scores | Check all metrics | <1.0 for at least one metric | ☐ |
| 9.7 | Feature importances are distributed | Top feature < 50% of total importance | Distributed | ☐ |
| 9.8 | Train-test gap is reasonable | Train AUC - Test AUC | <0.2 | ☐ |

### 9C. XGBoost

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 9.9 | Model does not achieve perfect 1.0 scores | Check all metrics | <1.0 for at least one metric | ☐ |
| 9.10 | Early stopping is effective | Check best_iteration | < n_estimators | ☐ |
| 9.11 | Feature importance is not dominated by 1 feature | Top feature < 50% | Mixed | ☐ |

### 9D. Cross-Validation

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 9.12 | Walk-forward CV: train on weeks 1-k, test on week k+1 | `TimeSeriesSplit` | Consistent scores | ☐ |
| 9.13 | CV scores similar to holdout test | Compare mean CV AUC vs test AUC | Within 0.1 | ☐ |
| 9.14 | No week where model is dramatically worse | Check per-week CV scores | <0.2 std dev | ☐ |

**Stage 9 Sign-off:** _________ **Date:** _________

---

## Stage 10 — Explainability

### 10A. Global Explanations

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 10.1 | SHAP summary plot shows expected features | `shap.summary_plot` | Goldstein features top | ☐ |
| 10.2 | Top 5 SHAP features are interpretable | Business review | Each has a clear story | ☐ |
| 10.3 | No feature contradicts domain knowledge | SME review | All features make sense | ☐ |
| 10.4 | SHAP dependence plots show monotonic trends | `shap.dependence_plot` | No unexpected shapes | ☐ |

### 10B. Local Explanations

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 10.5 | Force plot for a high-risk prediction explains why | `shap.force_plot` | Clear drivers | ☐ |
| 10.6 | Force plot for a low-risk prediction explains why | `shap.force_plot` | Clear drivers | ☐ |
| 10.7 | False positive: SHAP shows why the model was wrong | Pick 3 FPs, analyze | Understandable error | ☐ |
| 10.8 | False negative: SHAP shows why the model missed it | Pick 3 FNs, analyze | Understandable error | ☐ |

**Stage 10 Sign-off:** _________ **Date:** _________

---

## Stage 11 — Error Analysis

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 11.1 | False positives are concentrated in specific countries | Country-level FP analysis | No single country >50% of FPs | ☐ |
| 11.2 | False negatives are concentrated in specific countries | Country-level FN analysis | No single country >50% of FNs | ☐ |
| 11.3 | Model performs similarly across large and small countries | Split by "high-event" vs "low-event" countries | AUC difference < 0.15 | ☐ |
| 11.4 | No week where model catastrophically fails (AUC < 0.5) | Per-week AUC | All weeks AUC > 0.5 | ☐ |
| 11.5 | Prediction uncertainty correlates with error | Compare uncertainty vs error | Higher uncertainty → more errors | ☐ |

**Stage 11 Sign-off:** _________ **Date:** _________

---

## Stage 12 — Stress Testing

| # | Test | Method | Expected Behavioral Change | Result |
|---|------|--------|---------------------------|--------|
| 12.1 | Double sanction_count for all countries | Modified inference | Risk increases for sanctioned countries | ☐ |
| 12.2 | Set goldstein_neg_count to 0 for all countries | Modified inference | Risk decreases | ☐ |
| 12.3 | Increase total_events by 10× for all rows | Modified inference | Volatility increases, risk may increase | ☐ |
| 12.4 | Make avg_tone very negative (-50) for all rows | Modified inference | Risk increases | ☐ |
| 12.5 | Set all conflict_event_ratio to 1.0 | Modified inference | Max risk for all | ☐ |
| 12.6 | Swap a stable country's features with a volatile country's | Modified inference | Model should predict volatility for stable | ☐ |
| 12.7 | Zero out all features for one country | Modified inference | Predictions should move toward prior | ☐ |
| 12.8 | Extreme values: goldstein_min = -10, goldstein_max = +10 | Modified inference | Risk elevated but not max | ☐ |

**Rule**: If prediction changes do not make logical sense, investigate for overfitting or feature misinterpretation.

**Stage 12 Sign-off:** _________ **Date:** _________

---

## Stage 13 — End-to-End Pipeline Validation

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 13.1 | Raw data exists and is valid | Stages 1-2 | All PASS | ☐ |
| 13.2 | Country mapping is correct | Stage 3 | All PASS | ☐ |
| 13.3 | Dataset builder produces consistent output | Stage 4 | Deterministic | ☐ |
| 13.4 | Target is valid and leakage-free | Stage 5 | All PASS | ☐ |
| 13.5 | Features are correctly engineered | Stage 6 | All PASS | ☐ |
| 13.6 | No leakage detected | Stage 7 | All PASS | ☐ |
| 13.7 | Dataset quality is acceptable | Stage 8 | All PASS | ☐ |
| 13.8 | Baseline models train and produce reasonable scores | Stage 9 | All PASS | ☐ |
| 13.9 | Model predictions are explainable | Stage 10 | All PASS | ☐ |
| 13.10 | Errors are understood and documented | Stage 11 | All PASS | ☐ |
| 13.11 | Model responds logically to stress tests | Stage 12 | All PASS | ☐ |
| 13.12 | Full pipeline reproducibility: delete output, rebuild, compare | `git stash; build; compare` | Identical output | ☐ |

## Final Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| ML Engineer | | | |
| Domain Expert | | | |
| Tech Lead | | | |

**Decision:** ☐ Promote to Staging ☐ Promote to Production ☐ BLOCKED — issues: _________

---

## Appendix: Quick Reference Commands

```python
# Load the dataset
import pandas as pd
df = pd.read_parquet("research/datasets/geopolitical_risk_v1/geopolitical_risk_v1.parquet")

# Basic stats
df.describe()
df.isnull().mean().sort_values(ascending=False)
df['country'].nunique()
df['risk_flag'].value_counts(normalize=True)
df.duplicated(subset=['country', 'year', 'week']).sum()

# Check temporal split
train = pd.read_parquet("research/datasets/geopolitical_risk_v1/train.parquet")
test = pd.read_parquet("research/datasets/geopolitical_risk_v1/test.parquet")
print(f"Train weeks: {train['week'].min()}-{train['week'].max()}")
print(f"Test weeks: {test['week'].min()}-{test['week'].max()}")
print(f"Overlap: {set(train['week']) & set(test['week'])}")

# Quick model
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
features = [c for c in df.columns if c not in ('country', 'year', 'week', 'risk_flag')]
X = df[features].select_dtypes('number').dropna(axis=1, how='all').fillna(0)
y = df['risk_flag']
lr = LogisticRegression(max_iter=1000).fit(X.iloc[:4000], y.iloc[:4000])
print(f"AUC: {roc_auc_score(y.iloc[4000:], lr.predict_proba(X.iloc[4000:])[:,1]):.3f}")
```
