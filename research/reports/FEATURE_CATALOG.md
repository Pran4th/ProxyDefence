# Feature Catalog — geopolitical_risk_index_v1

Version: 1.0
Date: 2026-07-07
Total Features: 82 (2 identifiers + 1 target + 44 GDELT temporal + 28 static + 7 cyclical)

---

## Section A: Identifier Columns

### A1. `country`
| Property | Value |
|----------|-------|
| **Source** | GDELT ActionGeo_CountryCode → FIPS 2-letter → ISO3 lookup |
| **Definition** | ISO 3166-1 alpha-3 country code |
| **Aggregation window** | N/A (identifier) |
| **Expected range** | 224 unique ISO3 codes |
| **Null rate** | 0% |
| **Leakage risk** | None (identifier, not a feature) |
| **Notes** | All downstream joins use this key |

### A2. `year`
| Property | Value |
|----------|-------|
| **Source** | GDELT Day → pd.to_datetime → isocalendar().year |
| **Definition** | ISO year number |
| **Expected range** | 2024 |
| **Null rate** | 0% |

### A3. `week`
| Property | Value |
|----------|-------|
| **Source** | GDELT Day → pd.to_datetime → isocalendar().week |
| **Definition** | ISO week number (1-53) |
| **Expected range** | 1-13 (14 weeks of data) |
| **Null rate** | 0% |

---

## Section B: Target Column

### B1. `risk_flag`
| Property | Value |
|----------|-------|
| **Source** | GDELT GoldsteinScale |
| **Definition** | 1 if goldstein_neg_count > median of training set, else 0 |
| **Expected range** | {0, 1} |
| **Null rate** | 0% |
| **Leakage risk** | CRITICAL — see TARGET_DESIGN_REVIEW.md |
| **Predictive hypothesis** | Countries with elevated negative event counts this week tend to have identifiable patterns in event volume, tone, and actor diversity |

---

## Section C: GDELT Event Volume Features

### C1. `total_events`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → groupby(country, year, week).count() |
| **Definition** | Total number of GDELT events mentioning this country in this week |
| **Aggregation window** | 1 week |
| **Business interpretation** | News attention volume. Higher values indicate more newsworthy activity. |
| **Expected range** | 0 - 500,000+ (USA ≈ 400K/week, small countries ≈ 1-10/week) |
| **Null rate** | <1% |
| **Leakage risk** | None (same-week aggregation of public data) |
| **Predictive hypothesis** | Sudden increases in news volume precede conflict escalation |

### C2. `total_mentions`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → NumMentions.sum() |
| **Definition** | Sum of NumMentions (number of times each event appeared in news sources) |
| **Aggregation window** | 1 week |
| **Business interpretation** | Media saturation. Higher than total_events means stories are being repeated across outlets. |
| **Expected range** | 0 - 2,000,000+ |
| **Null rate** | <1% |
| **Leakage risk** | None |

### C3. `total_sources`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → NumSources.sum() |
| **Definition** | Sum of unique news sources reporting events for this country-week |
| **Expected range** | 0 - 500,000+ |
| **Null rate** | <1% |

### C4. `total_articles`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → NumArticles.sum() |
| **Definition** | Sum of articles mentioning events for this country-week |
| **Expected range** | 0 - 500,000+ |
| **Null rate** | <1% |

---

## Section D: GDELT Tone Features

### D1. `goldstein_mean`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → GoldsteinScale.mean() |
| **Definition** | Average GoldsteinScale across all events in country-week |
| **Aggregation window** | 1 week |
| **Business interpretation** | Overall cooperative (positive) vs conflictual (negative) tone. Scale: -10 (most conflictual) to +10 (most cooperative). |
| **Expected range** | -10 to +10 (typically -2 to +2 for most countries) |
| **Null rate** | <5% |
| **Leakage risk** | None |
| **Predictive hypothesis** | Decreasing goldstein_mean (trending negative) signals rising conflict risk |

### D2. `goldstein_std`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → GoldsteinScale.std() |
| **Definition** | Standard deviation of GoldsteinScale across all events in country-week |
| **Business interpretation** | Event tone diversity. High values mean a mix of very negative and very positive events. |
| **Expected range** | 0 to 10 |
| **Null rate** | <5% (0-filled where only 1 event) |
| **Predictive hypothesis** | High variance in event tone may indicate volatile, unpredictable situations |

### D3. `goldstein_min`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → GoldsteinScale.min() |
| **Definition** | Most negative GoldsteinScale in country-week |
| **Expected range** | -10 to 0 |
| **Null rate** | <5% |
| **Predictive hypothesis** | Extremely negative single events are leading indicators of escalating conflict |

### D4. `goldstein_max`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → GoldsteinScale.max() |
| **Definition** | Most positive GoldsteinScale in country-week |
| **Expected range** | 0 to +10 |
| **Null rate** | <5% |
| **Predictive hypothesis** | Positive cooperation events may briefly precede or follow conflict resolution |

### D5. `avg_tone`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → AvgTone.mean() |
| **Definition** | Average media tone across all articles mentioning events in country-week. Scale: -100 (extremely negative) to +100 (extremely positive). |
| **Expected range** | -20 to +20 |
| **Null rate** | ~25% |
| **Leakage risk** | None |
| **Predictive hypothesis** | Negative media tone amplifies negative event impacts and may correlate with escalation |

---

## Section E: GDELT Conflict Features

### E1. `goldstein_neg_count`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → sum(GoldsteinScale < -5) |
| **Definition** | Count of events with strongly negative GoldsteinScale (< -5: military action, crisis, etc.) |
| **Expected range** | 0 - 100,000+ |
| **Null rate** | <5% |
| **Predictive hypothesis** | **Core conflict proxy.** High negative event counts are the most direct GDELT signal for geopolitical risk. This is the current target variable. |

### E2. `goldstein_pos_count`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → sum(GoldsteinScale > 5) |
| **Definition** | Count of events with strongly positive GoldsteinScale (> 5: cooperation, agreement, etc.) |
| **Expected range** | 0 - 50,000+ |
| **Predictive hypothesis** | Positive events may indicate de-escalation or diplomatic solutions |

### E3. `quadclass_verbal_conflict`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → sum(QuadClass == 3) |
| **Definition** | Count of events classified as QuadClass 3 (verbal conflict: threats, accusations, demands) |
| **Expected range** | 0 - 100,000+ |
| **Predictive hypothesis** | Verbal conflict often precedes material conflict. Leading indicator. |

### E4. `quadclass_material_conflict`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → sum(QuadClass == 4) |
| **Definition** | Count of events classified as QuadClass 4 (material conflict: military action, border clashes, attacks) |
| **Expected range** | 0 - 50,000+ |
| **Predictive hypothesis** | Direct measure of violent conflict. Highest business impact for energy supply chain. |

### E5. `conflict_event_ratio`
| Property | Value |
|----------|-------|
| **Source** | (quadclass_verbal_conflict + quadclass_material_conflict) / total_events |
| **Definition** | Fraction of all events that are conflict-related (QuadClass 3 or 4) |
| **Expected range** | 0.0 to 1.0 |
| **Null rate** | <1% |
| **Predictive hypothesis** | High conflict ratio indicates the country is primarily in the news for negative reasons. More robust than raw counts for cross-country comparison. |

---

## Section F: GDELT Actor Diversity Features

### F1. `unique_actors1`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → Actor1CountryCode.nunique() |
| **Definition** | Number of distinct Actor1 country codes appearing in events for this country-week |
| **Expected range** | 0 - 150 |
| **Predictive hypothesis** | High actor diversity indicates many foreign countries are involved in events about this country — proxy for internationalization of conflict |

### F2. `unique_actors2`
| Property | Value |
|----------|-------|
| **Source** | GDELT Events → Actor2CountryCode.nunique() |
| **Definition** | Number of distinct Actor2 country codes appearing in events for this country-week |
| **Expected range** | 0 - 150 |
| **Predictive hypothesis** | Same as unique_actors1 but for secondary actors. Together, these measure how multilateral the conflict/activity is. |

---

## Section G: Lag Features (t-1 and t-4)

For each of 6 base features (`total_events`, `goldstein_mean`, `goldstein_neg_count`, `total_mentions`, `avg_tone`, `conflict_event_ratio`):

### Pattern: `{feature}_lag1`
| Property | Value |
|----------|-------|
| **Definition** | Value of feature from 1 week before the current row, within the same country |
| **Aggregation window** | t-1 (previous week) |
| **Business interpretation** | Short-term memory. The previous week's activity is the strongest predictor of this week's activity. |
| **Expected null rate** | ~15% (first week per country has no lag) |

### Pattern: `{feature}_lag4`
| Property | Value |
|----------|-------|
| **Definition** | Value of feature from 4 weeks before the current row, within the same country |
| **Aggregation window** | t-4 (one month prior) |
| **Business interpretation** | Month-over-month comparison. Captures medium-term trends. |
| **Expected null rate** | ~30% (first 4 weeks per country have no 4-week lag) |

### Lag Features List
| Feature | Equation |
|---------|----------|
| `total_events_lag1` | total_events at (country, year, week-1) |
| `total_events_lag4` | total_events at (country, year, week-4) |
| `goldstein_mean_lag1` | goldstein_mean at (country, year, week-1) |
| `goldstein_mean_lag4` | goldstein_mean at (country, year, week-4) |
| `goldstein_neg_count_lag1` | goldstein_neg_count at (country, year, week-1) |
| `goldstein_neg_count_lag4` | goldstein_neg_count at (country, year, week-4) |
| `total_mentions_lag1` | total_mentions at (country, year, week-1) |
| `total_mentions_lag4` | total_mentions at (country, year, week-4) |
| `avg_tone_lag1` | avg_tone at (country, year, week-1) |
| `avg_tone_lag4` | avg_tone at (country, year, week-4) |
| `conflict_event_ratio_lag1` | conflict_event_ratio at (country, year, week-1) |
| `conflict_event_ratio_lag4` | conflict_event_ratio at (country, year, week-4) |

---

## Section H: Rolling Window Features

### Pattern: `{feature}_rolling4_mean`
| Property | Value |
|----------|-------|
| **Definition** | 4-week rolling mean of feature, including current week, within the same country |
| **Aggregation window** | t-3 to t (current plus 3 previous weeks) |
| **Business interpretation** | Smoothed trend. Filters out weekly noise to reveal underlying direction. |
| **Null rate** | 0% (min_periods=1, fills with available data) |
| **Leakage risk** | Non-causal if the rolling window includes the current week's value. For nowcasting this is acceptable. For forecasting (t+1), the rolling window should use only t-4 to t-1. |

### Rolling Features List
- `total_events_rolling4_mean`
- `goldstein_mean_rolling4_mean`
- `goldstein_neg_count_rolling4_mean`
- `total_mentions_rolling4_mean`
- `avg_tone_rolling4_mean`
- `conflict_event_ratio_rolling4_mean`

---

## Section I: Week-over-Week Change Features

### Pattern: `{feature}_change_wow`
| Property | Value |
|----------|-------|
| **Definition** | Current value minus lag-1 value: `feature_t - feature_{t-1}` |
| **Aggregation window** | t-1 to t |
| **Business interpretation** | Rate of change. Positive values mean the metric is increasing week-over-week. |
| **Expected range** | Feature-dependent |
| **Predictive hypothesis** | **Rapid changes (positive or negative) are often more informative than absolute levels.** A sudden spike in goldstein_neg_count is more alarming than a consistently high level. |

### WoW Change Features List
- `total_events_change_wow`
- `goldstein_mean_change_wow`
- `goldstein_neg_count_change_wow`
- `total_mentions_change_wow`
- `avg_tone_change_wow`
- `conflict_event_ratio_change_wow`

---

## Section J: Cyclical Time Features

### J1. `week_sin`
| Property | Value |
|----------|-------|
| **Definition** | sin(2π × week / 52) |
| **Business interpretation** | Cyclical encoding of week number. Allows the model to learn seasonal patterns (e.g., "Q4 is always more conflictual"). |
| **Expected range** | -1.0 to 1.0 |
| **Null rate** | 0% |

### J2. `week_cos`
| Property | Value |
|----------|-------|
| **Definition** | cos(2π × week / 52) |
| **Business interpretation** | Complementary cyclical encoding (together with week_sin, uniquely identifies the position in the year). |
| **Expected range** | -1.0 to 1.0 |
| **Null rate** | 0% |

---

## Section K: Static Features

### K1. `sanction_count`
| Property | Value |
|----------|-------|
| **Source** | OFAC SDN list |
| **Definition** | Count of OFAC sanctions associating this country's name |
| **Expected range** | 0 - 2000+ |
| **Null rate** | ~0% (0-filled) |
| **Leakage risk** | HIGH (country identity leakage) |
| **Predictive hypothesis** | Heavily sanctioned countries have restricted access to global markets, increasing supply chain risk |

### K2. `port_count`
| Property | Value |
|----------|-------|
| **Source** | Global ports database |
| **Definition** | Number of ports in country |
| **Expected range** | 0 - 50+ |
| **Null rate** | ~0% (0-filled) |
| **Leakage risk** | MEDIUM (geography proxy) |

### K3–K9. `energy_{2025,2026}_{fuel}`
| Properties | 14 features: 7 fuels × 2 years |
|------------|------------------------------|
| **Fuels** | diesel, gas, kerosene, petrol_gasoline, petrol_gasoline_95_octane, petrol_gasoline_parallel_market, super_petrol |
| **Definition** | Country-level mean fuel price |
| **Expected range** | 0 - 200 (local currency units) |
| **Null rate** | ~96% |
| **Leakage risk** | HIGH (null pattern identifies specific countries) |

### K10–K37. GEM Tracker Features
| Property | Value |
|----------|-------|
| **Source** | 9 GEM tracker Excel files |
| **Definition** | Binary/count indicators of energy infrastructure presence |
| **Expected range** | 0 - 100+ |
| **Null rate** | 50-80% |
| **Leakage risk** | HIGH (country fingerprinting) |

| Feature | Tracker + Sheet |
|---------|----------------|
| `GEM-GGIT-Gas-Pipelin_Pipelines` | GGIT Gas Pipelines |
| `GEM-GOIT-Oil-NGL-Pip_Data` | GOIT Oil/NGL Pipelines |
| `Global-Coal-Mine-Tra_Historical Prod` | Coal Mine Tracker (Historical Production) |
| `Global-Coal-Plant-Tr_Units` | Coal Plant Tracker |
| `Global-Hydropower-Tr_Data` | Hydropower Tracker |
| `Global-Hydropower-Tr_Below Threshold` | Hydropower (Below Threshold) |
| `Global-Nuclear-Power_Data` | Nuclear Power Tracker |
| `Global-Oil-and-Gas-E_Field-level mai` | Oil & Gas Extraction (Field-level maintenance) |
| `Global-Oil-and-Gas-E_Field-level res` | Oil & Gas Extraction (Field-level reserves) |
| `Global-Oil-and-Gas-E_Field-level pro` | Oil & Gas Extraction (Field-level production) |
| `Global-Oil-and-Gas-E_Project-level m` | Oil & Gas Extraction (Project-level M) |
| `Global-Oil-and-Gas-E_Project-level r` | Oil & Gas Extraction (Project-level R) |
| `Global-Oil-and-Gas-E_Project-level p` | Oil & Gas Extraction (Project-level P) |
| `Global-Solar-Power-T_Utility-Scale (` | Solar Power Tracker (Utility-Scale) |
| `Global-Solar-Power-T_Distributed (_1` | Solar Power Tracker (Distributed) |
| `Global-Wind-Power-Tr_Data` | Wind Power Tracker |
| `Global-Wind-Power-Tr_Below Threshold` | Wind Power Tracker (Below Threshold) |

---

## Section L: Feature Engineering Summary

### By Type
| Type | Count | Examples |
|------|-------|---------|
| Base GDELT | 14 | total_events, goldstein_mean |
| Cyclical time | 2 | week_sin, week_cos |
| Lag (t-1) | 6 | total_events_lag1 |
| Lag (t-4) | 6 | total_events_lag4 |
| Rolling (4-week) | 6 | goldstein_neg_count_rolling4_mean |
| WoW change | 6 | goldstein_neg_count_change_wow |
| Static | ~42 | sanction_count, GEM_* |
| **Total** | **~82** | |

### By Dataset Source
| Source | Feature Count | Temporal |
|--------|---------------|----------|
| GDELT Events | 44 (base + engineered) | Yes |
| OFAC SDN | 1 | No |
| Ports | 1 | No |
| Global Energy | 14 | No |
| GEM Trackers | ~28 | No |
| Engineered (time) | 2 | Yes |

### Missing Feature Groups
- **GKG (GDELT Knowledge Graph)**: Not yet integrated. Would add theme/topic features.
- **Mentions**: Not yet integrated. Would add source diversity and influence metrics.
- **Political Violence**: Not yet integrated.
- **AEO**: Not yet integrated.
