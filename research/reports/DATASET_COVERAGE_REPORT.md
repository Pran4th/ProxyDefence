# Dataset Coverage Report

## 1. GDELT Events

### Coverage

| Dimension | Value |
|-----------|-------|
| **Source** | GDELT 2.0 Event Export (data.gdeltproject.org) |
| **Time period** | 2024-01-01 to 2024-03-27 (87 days) |
| **Temporal coverage** | Daily 15-minute intervals, 96 files/day |
| **Event date range** | 2023-01-01 to 2024-03-27 (events have Day values spanning this range) |
| **Total events** | 21,649,424 |
| **Countries** | 224 (ISO3) |
| **Weekly coverage** | 14 ISO weeks |
| **Country-weeks** | 5,953 (unique country × week combinations) |
| **Avg events/week** | 1,546,388 |
| **Avg events/country-week** | 3,637 |

### Data Quality

| Metric | Value |
|--------|-------|
| **GoldsteinScale non-null** | ~85% |
| **ActionGeo_CountryCode non-null** | ~92% |
| **QuadClass non-null** | ~88% |
| **AvgTone non-null** | ~75% |
| **Actor1CountryCode non-null** | ~60% |
| **Actor2CountryCode non-null** | ~50% |
| **Malformed rows** | <0.1% (header lines, truncated files) |
| **Duplicate events** | Near zero by GlobalEventID |

### Update Frequency
GDELT publishes new data every 15 minutes with a ~15-minute lag. Our snapshot is from a single download — no ongoing updates.

### Feature Contribution
- 14 base features → 44 engineered features (with lags, rolling, WoW change)
- Core of the dataset: all GDELT-derived features have <5% null rate
- Critical for temporal risk patterns

### Long-Term Value
**Essential.** GDELT is the primary dynamic data source. Without it, the dataset has no temporal dimension. Should be refreshed monthly to expand temporal coverage.

---

## 2. OFAC SDN

### Coverage

| Dimension | Value |
|-----------|-------|
| **Source** | US Treasury OFAC SDN list |
| **File** | `datasets/raw/sdn.csv` |
| **Rows** | 19,130 |
| **Columns** | 12 (no header) |
| **Countries** | 60 unique country values (before ISO3 mapping) → 47 countries (after ISO3 dedup) |
| **No-country entries** | ~17,669 entries with "-0-" placeholder |
| **Temporal coverage** | Single snapshot (as-of download date) |

### Data Quality

| Metric | Value |
|--------|-------|
| **Country field null rate** | ~92% (17,669 / 19,130 have "-0-") |
| **Country name ambiguity** | Medium — multiple name variants per country |
| **Schema** | No header — column indices hardcoded |
| **Duplicate ISO3 mappings** | Identified and fixed (47 unique ISO3 from 60 raw names) |

### Update Frequency
OFAC list is updated periodically by the US Treasury. Our copy is a snapshot.

### Feature Contribution
- `sanction_count`: integer per country
- Zero for countries not in OFAC

### Long-Term Value
**Medium.** Sanctions are a useful macro-level risk indicator but the high null rate in the country field limits coverage to 47 countries. Country identity leakage risk is significant (see Static Feature Review).

---

## 3. Ports

### Coverage

| Dimension | Value |
|-----------|-------|
| **Source** | Global ports database |
| **File** | `datasets/raw/ports.csv` |
| **Rows** | ~2,065 |
| **Columns** | ~22 |
| **Countries** | 159 (ISO3 already present) |
| **Temporal coverage** | Single snapshot |

### Data Quality

| Metric | Value |
|--------|-------|
| **ISO3 field** | Clean — no mapping needed |
| **Missing values** | Low (<5% across key columns) |
| **Duplicates** | None expected (one row per port) |

### Update Frequency
Infrequent — port infrastructure changes slowly.

### Feature Contribution
- `port_count`: integer per country

### Long-Term Value
**Low-medium.** Provides maritime trade exposure proxy, but value is limited for landlocked countries (port_count=0). If country identification is a concern, this is a candidate for dropping or simplifying to binary.

---

## 4. Global Energy Pricing

### Coverage

| Dimension | Value |
|-----------|-------|
| **Source** | Global Energy Monitor / energy pricing dataset |
| **Files** | `global_energy_2025.csv`, `global_energy_2026.csv` |
| **Rows** | ~3,247 per file (market × month level) |
| **Columns** | 62 per file |
| **Countries** | 10 (after ISO3 mapping) |
| **Temporal coverage** | 2025 annual, 2026 annual (future relative to 2024 dataset) |
| **Spatial coverage** | Sub-national markets within each country |

### Data Quality

| Metric | Value |
|--------|-------|
| **Null rate after merge** | ~96% (5,735/5,953 rows have no energy data) |
| **Fuel price completeness** | Varies by fuel: diesel most complete, super_petrol rarest |
| **Spatial granularity** | Sub-national market → aggregated to country mean |
| **Temporal alignment** | 2025/2026 data in a 2024-Q1 dataset is misaligned |

### Update Frequency
Annual (implied by 2025/2026 filenames).

### Feature Contribution
14 features: 7 fuel prices × 2 years.

### Long-Term Value
**Low for v1.** 96% null rate means these features contribute no signal for most countries. The temporal misalignment (future data in historical dataset) creates validity concerns. Should be dropped from v1 or replaced with a properly time-aligned energy price source.

---

## 5. GEM Energy Infrastructure Trackers

### Coverage

| Dimension | Value |
|-----------|-------|
| **Source** | Global Energy Monitor (31 tracker files) |
| **Location** | `datasets/raw/gem-data/` (30+ files) + root directory (additional files) |
| **Formats** | Excel (.xlsx), some with companion .zip (spatial data) |
| **Trackers used** | 9 KEY_TRACKERS selected by builder |
| **Countries** | 207 (after ISO3 mapping) |
| **Temporal coverage** | Single snapshot per tracker (various release dates: Sep 2024 - Jun 2026) |

### Data Quality

| Metric | Value |
|--------|-------|
| **Sheet structure** | Multiple sheets per file (varies by tracker) |
| **Country column** | Present but varies in name ("Country", "country", etc.) |
| **Null rate in builder** | 50-80% across tracker features |
| **Encoding** | Excel files with mixed data types |

### Key Tracker Coverage

| Tracker | Release Date | Sheets Used | Countries | Null Rate |
|---------|-------------|-------------|-----------|-----------|
| Global Coal Mine Tracker | Dec 2024 + Sep 2024 + May 2026 | Historical Prod | 207 | 67% |
| Global Coal Plant Tracker | Jan 2026 | Units | 207 | variable |
| GEM GOIT Oil/NGL Pipelines | Jun 2026 | Data | 207 | 52% |
| GEM GGIT Gas Pipelines | Nov 2025 | Pipelines | 207 | variable |
| Global Nuclear Power Tracker | Sep 2025 | Data | 207 | 67% |
| Global Solar Power Tracker | Feb 2026 | Utility-Scale, Distributed | 207 | variable |
| Global Wind Power Tracker | Feb 2026 | Data, Below Threshold | 207 | variable |
| Global Hydropower Tracker | Mar 2026 | Data, Below Threshold | 207 | variable |
| Global Oil & Gas Extraction | Mar 2026 | Field-level maintenance/reserves/production, Project-level | 207 | ~50-70% |

### Update Frequency
Variable — GEM releases updates quarterly to annually per tracker.

### Feature Contribution
~28 binary/small-count features (presence/absence per tracker-sheet).

### Long-Term Value
**Medium.** Valuable for understanding energy infrastructure exposure, but current binary encoding discards materiality. High-value potential if capacity-based metrics (MW, tonnes, km) are extracted instead of asset counts. Country fingerprinting risk needs mitigation.

---

## 6. Political Violence & Demonstrations (Not Yet Integrated)

### Coverage

| Dimension | Value |
|-----------|-------|
| **Source** | ACLED or similar |
| **Files** | 2 Excel files |
| **Granularity** | Country-year |
| **Temporal coverage** | As-of Jun 2026 |
| **Current status** | Not included in the builder |

### Long-Term Value
**Potentially high.** Direct measure of political violence, complementary to GDELT's news-based events. Year-level granularity is too coarse for weekly prediction — would need daily/weekly version from the same source.

---

## 7. AEO Energy Outlooks (Not Yet Integrated)

### Coverage

| Dimension | Value |
|-----------|-------|
| **Source** | US EIA Annual Energy Outlook |
| **Files** | AEO2026.txt (extracted), AEO2025.zip, AEO2023.zip |
| **Format** | Text files with structured data tables |
| **Current status** | Partially explored, not integrated |

### Long-Term Value
**Medium.** Useful for energy price/production forecasts as features, but large text files (260 MB, 179 MB) require custom parsers.

---

## 8. Summary: Dataset Health

| Dataset | Coverage | Quality | Temporal Signal | Country Count | Contribution | Overall Health |
|---------|----------|---------|-----------------|---------------|--------------|----------------|
| GDELT Events | High | High | Strong | 224 | Core | ✅ |
| OFAC SDN | Low | Medium | None (static) | 47 | Medium | ⚠️ |
| Ports | Medium | High | None (static) | 159 | Low | ⚠️ |
| Global Energy | Very Low | Low | Misaligned | 10 | Negligible | ❌ Drop |
| GEM Trackers | High | Medium | None (static) | 207 | Medium | ⚠️ |
| Political Violence | Not integrated | TBD | Annual | TBD | TBD | ❓ |
| AEO | Not integrated | TBD | Annual | TBD | TBD | ❓ |

### Weak Datasets
1. **Global Energy Pricing** — 96% null, temporal misalignment, 10-country coverage. Recommend dropping for v1.
2. **OFAC** — Country identity leakage risk, 92% null in country field, only 47 countries. Use with caution.
3. **Ports** — Low signal, geography proxy. Consider binary encoding or dropping.

### Strengths
1. **GDELT Events** — The backbone of the dataset. High coverage, quality, and temporal signal.
2. **GEM Trackers** — Broad country coverage. Need better encoding (capacity-based) and regularization to reduce fingerprinting.
