# Target Design Review

## 1. Current Target: `risk_flag` (goldstein_neg_count > median)

### Definition
Binary flag: 1 if the country-week has above-median count of negative Goldstein events (Goldstein < -5), else 0.

### Business Meaning
"Is this country-week more conflictual than average?"

### Problems

| Issue | Severity | Explanation |
|-------|----------|-------------|
| **Median is dataset-dependent** | Critical | The median is computed from training data only. If the training period is unusually peaceful or violent, the threshold shifts. A model trained on 2024-Q1 data cannot be compared with one trained on 2023 data — the target definition changes. |
| **No prediction horizon** | Critical | The target is computed from the **same week** as the features. This is nowcasting, not forecasting. There is no forward-looking component. The model learns "what is happening now" not "what will happen next." |
| **Relative, not absolute** | High | A country can have `risk_flag=1` even if all events are mildly negative (Goldstein -4 to -6) if there happens to be more of them. The target measures *relative* conflict volume, not *absolute* severity. |
| **Class balance is accidental** | Medium | The 50/50 split is a property of using median, not a design choice. A truly peaceful period would produce less balanced targets. |
| **No temporal semantics** | High | The target doesn't distinguish between "sustained conflict escalation" and "one bad week." A country with chronically high conflict gets the same label as one where conflict suddenly spikes. |

### Recommendation
**Replace.** The current target is acceptable for a baseline proof-of-concept but unsuitable for a production geopolitical risk system.

---

## 2. Candidate Target Definitions

### Candidate A: Next-Week Risk Flag

| Property | Value |
|----------|-------|
| **Definition** | `risk_flag_{t+1}` = 1 if `goldstein_neg_count_{t+1}` > median of training period |
| **Business meaning** | "Will next week have above-average conflict?" |
| **Prediction horizon** | +1 week (true forecasting) |
| **Class balance** | ~50/50 (by construction) |
| **Leakage risk** | None — target is from future week, features are from current/past weeks |
| **Implementation complexity** | Low — shift target by 1 row per country |
| **Pros** | Simple, interpretable, directly useful for early warning |
| **Cons** | Still median-based (dataset dependent); doesn't measure *escalation* |

### Candidate B: Next-Week Conflict Escalation

| Property | Value |
|----------|-------|
| **Definition** | `escalation_flag_{t+1}` = 1 if `goldstein_neg_count_{t+1}` > `goldstein_neg_count_t` * 1.5 (50% increase) |
| **Business meaning** | "Will conflict intensity increase significantly next week?" |
| **Prediction horizon** | +1 week |
| **Class balance** | ~15-25% positive (imbalanced by nature — escalation is rare) |
| **Leakage risk** | None — compares future to present |
| **Implementation complexity** | Low — simple threshold |
| **Pros** | Measures change, not level; directly actionable (escalation is what decision-makers care about) |
| **Cons** | Rare events class imbalance; threshold (1.5x) is arbitrary; no escalation in baseline weeks |

### Candidate C: Next-Week Disruption Flag

| Property | Value |
|----------|-------|
| **Definition** | `disruption_flag_{t+1}` = 1 if `goldstein_neg_count_{t+1}` > 95th percentile of that country's historical distribution |
| **Business meaning** | "Will next week be unusually disruptive for this specific country?" |
| **Prediction horizon** | +1 week |
| **Class balance** | ~5% positive (rare events) |
| **Leakage risk** | Country-specific percentile uses historical data — requires careful time-series split |
| **Implementation complexity** | Medium — needs per-country historical baseline |
| **Pros** | Country-specific; measures anomaly, not routine conflict; directly maps to "this country is having a bad week" |
| **Cons** | Very imbalanced; requires enough history per country to estimate percentile (14 weeks may be insufficient) |

### Candidate D: Sustained Negative Trend Flag

| Property | Value |
|----------|-------|
| **Definition** | `sustained_risk_flag_{t+1}` = 1 if rolling 4-week mean of goldstein_neg_count at t+1 is increasing and > median |
| **Business meaning** | "Is a sustained negative trend developing?" |
| **Prediction horizon** | +1 week (predicting trend direction) |
| **Class balance** | ~30-40% positive |
| **Leakage risk** | Rolling windows must not overlap with target period |
| **Implementation complexity** | Medium — rolling computation + trend detection |
| **Pros** | Filters out one-week spikes; captures structural shifts; aligns with intelligence community's "watchlist" concept |
| **Cons** | Smoothes signal; delays detection by 4 weeks; fewer positive samples |

### Candidate E: Multi-Class Risk Level

| Property | Value |
|----------|-------|
| **Definition** | 0 = Low (goldstein_neg_count <= median), 1 = Elevated (> median and < 90th pctile), 2 = High (>= 90th pctile) |
| **Business meaning** | "What is the risk level next week?" |
| **Prediction horizon** | +1 week |
| **Class balance** | ~50% / ~40% / ~10% |
| **Leakage risk** | Percentile-based threshold (same issue as median) |
| **Implementation complexity** | Medium — multi-class loss; ordinal interpretation |
| **Pros** | Richer signal; allows graduated response (monitor / alert / evacuate) |
| **Cons** | Harder to evaluate; ordinal relationships must be preserved; threshold choice is arbitrary |

---

## 3. Comparison Matrix

| Criterion | Current | A: Next-Week Risk | B: Escalation | C: Disruption | D: Sustained Trend | E: Multi-Class |
|-----------|---------|-------------------|---------------|---------------|-------------------|----------------|
| **Forecasting** | No | Yes | Yes | Yes | Yes | Yes |
| **Absolute measure** | No | No | Yes | Yes | Yes | Partial |
| **Interpretability** | High | High | High | Medium | Medium | Medium |
| **Class balance** | ~50/50 | ~50/50 | ~20/80 | ~5/95 | ~35/65 | ~50/40/10 |
| **Leakage safe** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Business value** | Low | Medium | High | Medium | High | Medium |
| **Implementation effort** | Done | Low | Low | Medium | Medium | Medium |

---

## 4. Recommendation

### Primary Target: **Candidate B — Next-Week Conflict Escalation**

**Why:**
1. **Forecasting, not nowcasting** — +1 week horizon means the model must learn leading indicators, not just describe the present
2. **Measures change** — The ProxyDefence mission is to predict *deterioration*, not steady-state conflict. A model that flags "more of the same" is less useful than one that flags "things are getting worse."
3. **Actionable** — 50% increase in negative events is a clear trigger for intelligence review. It answers: "Should I pay attention to this country next week?"
4. **Business alignment** — Energy supply chain resilience depends on anticipating *disruptions*, not measuring ongoing conflicts

### Secondary Target: **Candidate A — Next-Week Risk Flag**

**Why:**
- Useful as a baseline for comparison with the current target
- Allows a 2-head model (classification head for escalation, regression head for risk level)
- Easier to achieve high precision/recall, useful for initial trust-building with stakeholders

### Rejected Candidates

| Candidate | Reason for Rejection |
|-----------|---------------------|
| Current (same-week median) | Not a forecasting target |
| C: Disruption | 5% positive class with only 14 weeks of history makes per-country percentile unreliable |
| D: Sustained Trend | Too much signal smoothing for 14-week dataset; 4-week rolling window loses 30% of temporal data |
| E: Multi-Class | Premature before binary targets are validated; ordinal constraints add complexity without proven benefit |

---

## 5. Next Steps

1. Implement `escalation_flag_{t+1}` = 1 if `goldstein_neg_count_{t+1}` > `goldstein_neg_count_t` * 1.5
2. Retain the current `risk_flag` as a second target head for evaluation
3. Verify no temporal leakage: ensure features at week t use only data from weeks ≤ t
4. Evaluate class balance after implementation (expected: 15-25% positive)
5. If escalation proves too imbalanced, fall back to Candidate A (next-week risk flag)
