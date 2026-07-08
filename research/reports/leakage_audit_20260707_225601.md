# Leakage Audit Report
**Generated**: 2026-07-07T22:56:01.118061
**Mode**: all_features

---

## 1. Duplicate Columns (identical values across features)

- `energy_2025_fuel_petrol_gasoline_95_octane` == `energy_2026_fuel_petrol_gasoline_95_octane`
- `energy_2025_fuel_petrol_gasoline_95_octane` == `energy_2026_fuel_super_petrol`
- `energy_2026_fuel_petrol_gasoline_95_octane` == `energy_2026_fuel_super_petrol`

---

## 2. Constant Columns (single unique value)

- `energy_2025_fuel_gas`
- `energy_2025_fuel_kerosene`
- `energy_2025_fuel_petrol_gasoline_parallel_market`
- `energy_2025_fuel_super_petrol`
- `energy_2026_fuel_gas`
- `energy_2026_fuel_kerosene`
- `energy_2026_fuel_petrol_gasoline_parallel_market`
- `Global-Solar-Power-T_Distributed (_1`

---

## 3. Zero-Variance Columns (std = 0 after dropping NaN)

_None detected_

---

## 4. Highly Correlated Feature Pairs (>0.99)

| Feature 1 | Feature 2 | Correlation |
|-----------|-----------|-------------|
| `total_mentions` | `total_articles` | 1.0000 |
| `energy_2025_fuel_diesel` | `GEM-GGIT-Gas-Pipelin_Pipelines` | 1.0000 |
| `energy_2025_fuel_diesel` | `Global-Coal-Mine-Tra_Historical Prod` | -1.0000 |
| `energy_2025_fuel_diesel` | `Global-Coal-Plant-Tr_Units` | 1.0000 |
| `energy_2025_fuel_petrol_gasoline` | `Global-Coal-Plant-Tr_Units` | -1.0000 |
| `energy_2025_fuel_petrol_gasoline` | `Global-Nuclear-Power_Data` | 1.0000 |
| `energy_2025_fuel_petrol_gasoline` | `Global-Oil-and-Gas-E_Project-level r` | 1.0000 |
| `energy_2026_fuel_diesel` | `GEM-GGIT-Gas-Pipelin_Pipelines` | 1.0000 |
| `energy_2026_fuel_diesel` | `Global-Coal-Mine-Tra_Historical Prod` | -1.0000 |
| `energy_2026_fuel_diesel` | `Global-Coal-Plant-Tr_Units` | 1.0000 |
| `energy_2026_fuel_petrol_gasoline` | `Global-Coal-Plant-Tr_Units` | -1.0000 |
| `energy_2026_fuel_petrol_gasoline` | `Global-Nuclear-Power_Data` | 1.0000 |
| `energy_2026_fuel_petrol_gasoline` | `Global-Oil-and-Gas-E_Project-level r` | 1.0000 |
| `total_events` | `total_sources` | 0.9999 |
| `total_events` | `total_events_change_wow` | 0.9999 |
| `goldstein_neg_count` | `goldstein_neg_count_change_wow` | 0.9999 |
| `total_mentions` | `total_mentions_change_wow` | 0.9999 |
| `total_articles` | `total_mentions_change_wow` | 0.9999 |
| `total_sources` | `total_events_change_wow` | 0.9998 |
| `goldstein_neg_count` | `goldstein_neg_count_rolling4_mean` | 0.9997 |
| `total_events` | `total_events_rolling4_mean` | 0.9996 |
| `total_mentions` | `total_mentions_rolling4_mean` | 0.9996 |
| `total_articles` | `total_mentions_rolling4_mean` | 0.9996 |
| `total_sources` | `total_events_rolling4_mean` | 0.9995 |
| `goldstein_neg_count_rolling4_mean` | `goldstein_neg_count_change_wow` | 0.9995 |
| `total_events_rolling4_mean` | `total_events_change_wow` | 0.9994 |
| `total_mentions_rolling4_mean` | `total_mentions_change_wow` | 0.9994 |
| `total_events_lag4` | `total_mentions_lag4` | 0.9993 |
| `total_events` | `total_articles` | 0.9990 |
| `total_articles` | `total_events_change_wow` | 0.9990 |
| `total_events` | `total_mentions` | 0.9989 |
| `total_sources` | `total_articles` | 0.9989 |
| `total_events_rolling4_mean` | `total_mentions_rolling4_mean` | 0.9989 |
| `total_events_change_wow` | `total_mentions_change_wow` | 0.9989 |
| `total_events` | `total_mentions_change_wow` | 0.9988 |
| `total_mentions` | `total_sources` | 0.9988 |
| `total_mentions` | `total_events_change_wow` | 0.9988 |
| `total_sources` | `total_mentions_change_wow` | 0.9987 |
| `total_articles` | `total_events_rolling4_mean` | 0.9986 |
| `total_events` | `total_mentions_rolling4_mean` | 0.9985 |
| `total_mentions` | `total_events_rolling4_mean` | 0.9985 |
| `total_sources` | `total_mentions_rolling4_mean` | 0.9984 |
| `total_events_change_wow` | `total_mentions_rolling4_mean` | 0.9984 |
| `goldstein_pos_count` | `total_mentions` | 0.9983 |
| `goldstein_pos_count` | `total_articles` | 0.9983 |
| `goldstein_pos_count` | `total_mentions_change_wow` | 0.9982 |
| `total_events_rolling4_mean` | `total_mentions_change_wow` | 0.9982 |
| `total_events_lag1` | `total_mentions_lag1` | 0.9980 |
| `goldstein_pos_count` | `total_mentions_rolling4_mean` | 0.9978 |
| `total_events` | `goldstein_pos_count` | 0.9969 |
| `goldstein_pos_count` | `total_events_change_wow` | 0.9969 |
| `energy_2026_fuel_diesel` | `energy_2026_fuel_petrol_gasoline` | 0.9969 |
| `goldstein_pos_count` | `total_sources` | 0.9967 |
| `goldstein_pos_count` | `total_events_rolling4_mean` | 0.9965 |
| `quadclass_verbal_conflict` | `total_sources` | 0.9935 |
| `total_events` | `quadclass_verbal_conflict` | 0.9934 |
| `quadclass_verbal_conflict` | `quadclass_material_conflict` | 0.9933 |
| `quadclass_verbal_conflict` | `total_events_change_wow` | 0.9933 |
| `energy_2025_fuel_diesel` | `energy_2025_fuel_petrol_gasoline` | 0.9933 |
| `quadclass_verbal_conflict` | `total_events_rolling4_mean` | 0.9930 |
| `unique_actors1` | `unique_actors2` | 0.9922 |
| `energy_2025_fuel_diesel` | `energy_2026_fuel_petrol_gasoline` | 0.9909 |
| `quadclass_verbal_conflict` | `total_articles` | 0.9902 |

---

## 5. Target Leakage Check (feature correlation with target > 0.95)

### risk_flag

_No features exceed 0.95 correlation threshold_

### escalation_flag_t1

_No features exceed 0.95 correlation threshold_

---

## 6. Future Leakage Check

_Structural check: all lag features use shift(+1) or shift(+4) (backward-looking). 
Rolling windows use min_periods=1 with no center=True. 
No features computed from future week data._

---

## 7. Duplicate Country-Week Rows

_0 duplicate rows_

---

## Interpretation Notes

- **Duplicate columns**: If features A and B have identical values, one is redundant. Consider dropping.
- **Constant columns**: No predictive value (zero variance). Safe to drop.
- **Highly correlated pairs**: May cause multicollinearity in linear models. Tree-based models are robust.
- **Target leakage**: Features with >0.95 correlation to target likely contain target information. Investigate immediately.
- **Future leakage**: None detected by structural analysis. Verify temporal split does not allow test data into training.

---
*Report generated by `GeopoliticalRiskDatasetBuilder.leakage_audit()` in all_features mode.*