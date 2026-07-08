# Static Feature Review

## 1. Overview

Static features are included in every country-week row but do not vary week-to-week. They are joined by country via LEFT JOIN and repeated for every week of that country.

This review examines every static feature source for:
- Bias introduction
- Leakage risk
- Encoding appropriateness
- Long-term validity

---

## 2. OFAC Sanctions (`sanction_count`)

### Current Encoding
Single integer: total number of OFAC SDN entries associated with a country's name.

### Bias Assessment

| Concern | Risk | Explanation |
|---------|------|-------------|
| **Country identity leakage** | HIGH | Sanction count is essentially a country fingerprint. The US, Iran, North Korea, Russia have very high counts (500-2000+). Most other countries have 0. A tree model can split on `sanction_count > 500` to isolate specific countries, learning country identity rather than generalizable risk patterns. |
| **Repeat value bias** | MEDIUM | The same value appears in every weekly row for a country. Models can use this as a persistent signal, inflating feature importance. In cross-validation, the same country appears in both train and test splits (since we split by week, not by country), allowing the model to memorize country-level patterns. |
| **Temporal staleness** | MEDIUM | OFAC data is a snapshot. If sanctions change during the dataset period, the count is wrong for some weeks. However, for a 3-month window, this is minor. |
| **Name mapping noise** | LOW | Multiple OFAC country name variants mapping to the same ISO3 produced duplicate rows (now fixed by aggregation). |

### Recommendation
**Alternative encodings to evaluate:**

| Encoding | Effect |
|----------|--------|
| Log transform: `log(1 + sanction_count)` | Compresses the long tail (Iran=2000, Germany=0) into a more linear scale |
| Binned: `none / low / medium / high / critical` | Reduces model's ability to isolate individual countries via exact counts |
| Country-group: sanction tier (based on OFAC program type) | Focuses on *type* of sanctions (trade, terrorism, weapons) rather than count |
| **Drop and rely on GDELT features only** | Eliminates leakage risk entirely at the cost of losing signal |

**Preferred approach:** Log transform + sanction tier as separate features. This captures both intensity and nature of sanctions without enabling exact country identification.

---

## 3. Ports (`port_count`)

### Current Encoding
Single integer: count of ports in the global ports database for a country.

### Bias Assessment

| Concern | Risk | Explanation |
|---------|------|-------------|
| **Country size proxy** | HIGH | Port count strongly correlates with coastline length. Landlocked countries have 0. Island nations have fewer than large coastal nations. This is essentially a "country size / geography" proxy. |
| **Country identity leakage** | MEDIUM | Fewer discrete values than sanctions (0-50 range, not 0-2000), so less leakage potential. However, "0 ports" perfectly identifies ~65 landlocked countries. |
| **Economic development bias** | MEDIUM | Developed maritime nations (US, China, Netherlands, Singapore) have high port counts. This introduces economic development level as a confounder. |
| **Temporal staleness** | LOW | Port infrastructure changes slowly. |

### Recommendation
| Encoding | Effect |
|----------|--------|
| Binary: `has_port` (0/1) | Eliminates granularity that enables country identification |
| Log transform | Compresses distribution but preserves ordinality |
| **Port density**: `port_count / coastline_km` | Normalizes by geography (requires external coastline data) |

**Preferred approach:** Keep as-is for now but monitor feature importance. If `port_count` appears among top-5 features, it likely indicates country leakage rather than genuine predictive signal.

---

## 4. Global Energy Pricing (7 fuel × 2 years = 14 features)

### Current Encoding
Country-mean fuel prices per year. Sub-national market prices aggregated to country level.

### Bias Assessment

| Concern | Risk | Explanation |
|---------|------|-------------|
| **Extreme sparsity** | HIGH | ~96% null across all 5,953 country-weeks. Only 11 countries have any pricing data. These 11 countries are predominantly developed/emerging economies. |
| **Country identification via missingness** | HIGH | The pattern of "which fuel prices are available" uniquely identifies specific countries. Missingness is not random — it's systematically correlated with data collection priorities. |
| **Year-level mismatch** | MEDIUM | 2025 and 2026 data merged into a 2024-Q1 dataset. These are future prices relative to the dataset period, creating temporal inconsistency. |
| **No temporal variance** | HIGH | One value per country per year repeated across all weeks of that year. No week-to-week signal. |

### Recommendation
**Consider dropping entirely for v1.** The 96% null rate means these features are dropped by the baseline model's null filter anyway. They add column noise without contributing signal.

If kept for future:
- Only use the price columns (diesel, gas, kerosene, gasoline) — drop metadata (ISO3, lat, lon, geo_id, etc.)
- Consider the time alignment issue: 2025/2026 data in a 2024 dataset is anachronistic

---

## 5. GEM Trackers (~28 binary/small-count features)

### Current Encoding
Count of assets per (tracker, sheet) combination per country. Example: `Global-Coal-Mine-Tra_Historical Prod` = 1 if country appears in that sheet.

### Bias Assessment

| Concern | Risk | Explanation |
|---------|------|-------------|
| **Country fingerprinting** | HIGH | Each tracker-sheet combination creates a binary feature. With 28+ such features, the pattern across all of them essentially forms a country fingerprint. For example, only Saudi Arabia has certain oil/gas combinations. The model can memorize "Saudi Arabia → high risk" without learning generalizable patterns. |
| **Sparsity** | MEDIUM | ~50-80% null depending on the tracker. Only certain countries have nuclear, solar, or hydropower assets. |
| **Count vs capacity** | HIGH | Current encoding uses asset *count*, not capacity. A country with 1 small coal plant gets the same value as a country with 50 large coal plants. This discards materiality. |
| **No temporal dimension** | MEDIUM | Asset counts are from the latest available tracker snapshot. Infrastructure changes over time but is treated as static. |

### Recommendation

| Priority | Change | Rationale |
|----------|--------|-----------|
| 1 | **Drop or regularize** | 28+ near-binary features from static sources create strong country fingerprints. Either drop them for the first model iteration, or apply strong L1 regularization. |
| 2 | **Group into energy categories** | Instead of individual tracker-sheet flags, create 4-5 aggregate features: `has_coal`, `has_oil_gas`, `has_renewable`, `has_nuclear`, `has_hydro`. This preserves energy exposure signal without enabling country identification. |
| 3 | **Capacity-based** | When asset capacity data is available (MW for power plants, tonnes for mines), use that instead of count. Capacity has more variance and is more economically meaningful. |

---

## 6. Summary: Static Feature Recommendations

| Feature | Issue | Recommendation | Priority |
|---------|-------|----------------|----------|
| `sanction_count` | Country identity leakage | Log-transform + sanction tier | High |
| `port_count` | Geography proxy | Binary `has_port` or log transform | Medium |
| `energy_*` | 96% null + temporal mismatch | Drop for v1; revisit with proper temporal alignment | High |
| `GEM_*` | Country fingerprinting | Group into energy categories or regularize heavily | High |

## 7. Broader Concern: Country Identity Leakage

When static features are LEFT JOINed onto a panel sorted by (country, week), every row for "Iran" has the same set of static values. A model can learn:

```
if sanction_count > 500 and port_count > 10 and has_oil_gas == 1 → country = Iran → high risk
```

This bypasses learning actual geopolitical patterns. The model memorizes country-level lookup tables.

### Mitigations

| Mitigation | Effect |
|------------|--------|
| **Drop static features** | Forces model to rely on temporal GDELT patterns; cleanest option for first model |
| **L1 regularization** | Penalizes static features; model will only use them if they are genuinely predictive beyond country identity |
| **Country random effects** | Statistical model that treats country as a random intercept; not suitable for tree-based models |
| **Stratified cross-validation by country** | Ensures model is tested on countries it hasn't seen during training |

### Final Recommendation
**Run baseline models with and without static features.** Compare:
1. GDELT-only model
2. GDELT + static features

If the static-feature model outperforms by more than the amount explainable by country identity leakage (>5% ROC AUC improvement), then the static features contribute genuine signal. Otherwise, drop them.
