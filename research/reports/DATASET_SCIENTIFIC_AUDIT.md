# Scientific Dataset Audit — ProxyDefence

**Author**: Principal ML Research Scientist  
**Date**: 2026-07-07  
**Version**: 1.0  
**Scope**: All datasets in `datasets/raw/`, `datasets/processed/`, `research/datasets/`  
**Method**: Systematic review of every available data source, builder, and generated artifact  

---

## Executive Summary

ProxyDefence has assembled an ambitious collection of 40+ data sources spanning global news events, energy infrastructure, sanctions, maritime logistics, and economic projections. The data estate is **broad but uneven** — several world-class datasets (GDELT, GEM) coexist with empty staging directories and critically absent high-value sources (real-time AIS, actual ACLED, commodity prices).

The current flagship dataset (`geopolitical_risk_v1`) is built on **5.9% of available data** — using only GDELT Events while ignoring GDELT Mentions, GKG, AEO projections, and ACLED summaries that are already downloaded. The dataset suffers from fundamental scientific problems: same-week nowcasting target, static feature country leakage, and extreme temporal sparsity (14 weeks).

**Bottom line**: The data foundation is salvageable but requires a systematic integration program before credible ML models can be trained.

---

## Table of Contents

1. [Individual Dataset Reviews](#1-individual-dataset-reviews)
2. [Dataset-to-Use-Case Scoring Matrix](#2-dataset-to-use-case-scoring-matrix)
3. [Final Evaluation Matrix](#3-final-evaluation-matrix)
4. [Top 10 Highest Value Datasets](#4-top-10-highest-value-datasets)
5. [Low Value Datasets](#5-low-value-datasets)
6. [Missing Datasets](#6-missing-datasets)
7. [Current Feature Set Review](#7-current-feature-set-review)
8. [Current Target Critique](#8-current-target-critique)
9. [Strategic Recommendations](#9-strategic-recommendations)

---

## 1. Individual Dataset Reviews

---

### 1.1 GDELT Events (CORE)

**1. What is this dataset?**  
Global Database of Events, Language, and Tone — the world's largest open-source event database. Extracts structured events (who did what to whom, where, when) from news articles in 65+ languages. Each event is coded using the CAMEO (Conflict and Mediation Event Observations) taxonomy with ~300 event types.

**2. Who publishes it?**  
GDELT Project (Kalev Leetaru, Georgetown University). Funded by Google Jigsaw, Yahoo, and the US Intelligence Community.

**3. Temporal resolution**  
15-minute intervals (96 files/day). Event dates go back decades, but the project maintains a 75-day rolling window in daily exports.

**4. Spatial resolution**  
Country (ActionGeo_CountryCode via FIPS 2-letter), ADM1 (state/province), city (lat/lng). Three separate geographic fields (Actor1Geo, Actor2Geo, ActionGeo).

**5. Coverage**  
224 countries. 21.6M events downloaded (2024-01-01 to 2024-03-27, plus historical events back to 2014 within those exports). 61 columns per event. 87 days of exports (96 files/day = 8,352 files).

**6. Update frequency**  
Real-time (15-minute batches). Our copy is a static snapshot.

**7. Schema quality**  
Excellent (8/10). Well-documented 61-column schema. Consistent tab-separation. Some columns have high null rates (Actor2CountryCode ~50% null).

**8. Missing value analysis**  
- ActionGeo_CountryCode: ~8% null  
- Actor1CountryCode: ~40% null  
- Actor2CountryCode: ~50% null  
- AvgTone: ~25% null  
- GoldsteinScale: ~15% null  
- QuadClass: ~12% null  

**9. Data quality**  
High (8/10). Automated extraction from news, but inherits news bias. GoldsteinScale and CAMEO coding have been validated in 200+ academic papers.

**10. Reliability**  
High. GDELT has been continuously operational since 2013. Backfill available from data.gdeltproject.org.

**11. Business usefulness**  
9/10. Directly measures geopolitical events — the core signal for every risk model.

**12. ML usefulness**  
9/10. Rich feature space (event codes, actors, tones, geography). Well-suited for time-series, NLP, and graph models.

**13. Feature richness**  
9/10. 61 raw columns → 14+ base features → 40+ engineered features. GoldsteinScale (-10 to +10) is a validated conflict/cooperation measure.

**14. Future scalability**  
9/10. Can extend to daily updates, historical backfill to 1979, real-time streaming.

**15. Limitations**  
- English-language news bias (underrepresents non-English-speaking countries)  
- Rolling 75-day window means old events disappear from daily exports  
- News coverage ≠ ground truth (media attention amplifies some events, ignores others)  
- No economic or financial data  
- Actor coding is noisy (automated entity resolution with ~80% accuracy)

**16. Biases**  
- Linguistic bias (English news overrepresented)  
- Western news source bias (US/UK/Canada media dominate)  
- Conflict amplification (more news = more events = appears riskier)  
- State actor bias (non-state actors less well-coded)

**17. Potential leakage**  
Minimal for past data. The 75-day rolling window means events are static once downloaded. No forward-looking information.

**18. Integration complexity**  
Low (8/10). Tab-separated CSV, well-documented schema. Current builder handles it adequately.

**19. Current integration status**  
✅ **Partially integrated**. Events loading works. However, only 13 of 61 columns are used (21%). GoldsteinScale, QuadClass, and basic actor counts are used. Event code hierarchy (EventRootCode, EventBaseCode), mention/source/article counts, and detailed geography are available but unused.

**20. Should we keep it?**  
✅ **Absolutely essential**. Core dataset. Expand column usage from 13 to 25+.

---

### 1.2 GDELT Mentions (NOT INTEGRATED)

**1. What is it?**  
Citation records linking GDELT events to specific news articles. Each row is one mention of an event in a news article.

**2. Publisher**  
GDELT Project.

**3. Temporal resolution**  
15-minute (aligned with events).

**4. Spatial resolution**  
N/A (links events to articles; inherits event geography).

**5. Coverage**  
Aligned with event downloads: ~138 files, roughly 2 weeks of data (2024-01-01 to 2024-01-02 fully available plus partial). 16 columns.

**6. Update frequency**  
Same as events (15-min real-time).

**7. Schema quality**  
8/10. Well-documented. 16 columns including GlobalEventID, mention timestamp, source, URL, sentiment, and article counts.

**8. Missing value analysis**  
Minimal — field extraction from parsed articles is generally complete.

**9. Data quality**  
7/10. URLs may be dead links, but the structured data (source, timestamp, article counts) is reliable.

**10. Reliability**  
High, same as Events.

**11. Business usefulness**  
7/10. Source diversity and media influence metrics are valuable for estimating "how much attention is an event getting."

**12. ML usefulness**  
7/10. Features: source diversity (number of unique sources), media influence (weighted by source prominence), article count velocity, sentiment diffusion.

**13. Feature richness**  
6/10. 16 columns, most useful are: source, URL, article counts, tone scores.

**14. Future scalability**  
9/10. Same as Events — can extend to the full 87-day download window.

**15. Limitations**  
- Not currently downloaded for full period (only partial)  
- URL decay over time  
- Source prominence scoring requires external data

**16. Biases**  
Same as Events (English-language news bias).

**17. Potential leakage**  
None. Mentions reference past articles.

**18. Integration complexity**  
Low. Join on GlobalEventID. Current `load_gdelt_events` reads only event CSVs; Mentions would require adding a `load_gdelt_mentions` method.

**19. Current integration status**  
❌ **Not integrated**. Data exists on disk but not loaded by the builder.

**20. Should we keep it?**  
✅ **Yes — high priority for Phase 2**. Source diversity metrics are well-established predictors of information campaigns and conflict escalation.

---

### 1.3 GDELT GKG (NOT INTEGRATED)

**1. What is it?**  
Global Knowledge Graph — extracted themes, emotions, organizations, locations, and people from every news article. Each GKG row represents one article with semi-colon delimited lists of themes, emotions, named entities, and tone counts.

**2. Publisher**  
GDELT Project.

**3. Temporal resolution**  
15-minute.

**4. Spatial resolution**  
Article-level (lat/lng, country, ADM1, city extracted from article text).

**5. Coverage**  
~138 files, same download window as Mentions (~2 days). 27 columns.

**6. Update frequency**  
15-minute real-time.

**7. Schema quality**  
8/10. Complex (nested delimited fields), but well-documented. 27 columns.

**8. Missing value analysis**  
High sparsity in theme/entity fields. Many articles have no themes, no named entities. The theme column alone has 100+ possible values.

**9. Data quality**  
6/10. Theme/entity extraction quality varies. Some noise (irrelevant themes, over-matching).

**10. Reliability**  
High (same as Events).

**11. Business usefulness**  
8/10. Themes like "CRISISLEX_CRISISLEXREC", "TAX_FNCACT", "ECE_ECON_ECONRISK" provide rich qualitative signal beyond simple event counts.

**12. ML usefulness**  
8/10. Topic modeling, theme frequency analysis, entity co-occurrence, emotion tracking. Enables NLP-style features on millions of articles.

**13. Feature richness**  
9/10. 27 columns with nested sub-fields: themes (100+), emotions, tone counts (anger, fear, joy, sadness), named entities, quotes, image tags.

**14. Future scalability**  
9/10. Same as Events.

**15. Limitations**  
- Not downloaded for full period (only ~2 days)  
- Parsing delimited fields requires careful engineering  
- Theme taxonomy is large (500+ values) and changes over time

**16. Biases**  
Same as Events + thematic extraction bias (some themes are more detectable than others).

**17. Potential leakage**  
None.

**18. Integration complexity**  
Medium. Parsing semi-colon-delimited theme/entity fields requires new code. Joining on GKGRECORDID or timestamp to Events is non-trivial.

**19. Current integration status**  
❌ **Not integrated**. Data on disk but untouched.

**20. Should we keep it?**  
✅ **Yes — highest priority for Phase 2**. Theme features (economic risk, crisis lexicon, political violence) are the most powerful underutilized signal in the project.

---

### 1.4 OFAC SDN Sanctions

**1. What is it?**  
US Treasury Office of Foreign Assets Control — Specially Designated Nationals list. Individuals, organizations, and entities sanctioned by the US government.

**2. Publisher**  
US Department of Treasury (OFAC).

**3. Temporal resolution**  
Static snapshot (updated periodically by Treasury).

**4. Spatial resolution**  
Country (via nationality/country field, index 9 in CSV). Entity-level (individuals, companies, vessels, aircraft).

**5. Coverage**  
19,130 entries. ~47 countries with identifiable country references. ~92% of entries have "-0-" (no country). 12 columns (no header).

**6. Update frequency**  
Irregular (days to months). Our copy is a static snapshot.

**7. Schema quality**  
4/10. No header, inconsistent formatting, missing value codes ("-0-"), country field is free text with name variants.

**8. Missing value analysis**  
- Country field: 92% missing ("-0-")  
- Address fields: highly variable  
- Name parsing: complex (multiple aliases per entry)

**9. Data quality**  
5/10. Authoritative source (US government), but structured for legal use, not ML. High noise-to-signal in country field.

**10. Reliability**  
10/10 (authoritative). OFAC is the official US sanctions list.

**11. Business usefulness**  
6/10. Sanctions are a critical risk factor for energy supply chains. But 92% country null rate severely limits feature value.

**12. ML usefulness**  
3/10. Only `sanction_count` per country (47 countries). Binary feature essentially. Country identity leakage risk.

**13. Feature richness**  
1/10. One feature: integer count.

**14. Future scalability**  
2/10. Static list; no temporal dimension. Would need OFAC program type parsing to improve.

**15. Limitations**  
- 92% null country field  
- No temporal information (when sanctions were imposed/lifted)  
- No sanction type granularity in current builder  
- Static — cannot learn from changes over time

**16. Biases**  
US-centric sanctions policy. Over-represents US adversarial states (Iran, Russia, North Korea, Cuba).

**17. Potential leakage**  
HIGH. Country identity leakage. `sanction_count > 500` isolates Iran. The model can learn country names rather than risk patterns.

**18. Integration complexity**  
Low. Currently integrated.

**19. Current integration status**  
✅ **Integrated** as `sanction_count` (integer per country).

**20. Should we keep it?**  
✅ **Yes, but significantly improved.** Parse sanction type (SDN, sectoral, etc.), program (Iran, Russia, terrorism, etc.), and temporal information if available. Log-transform the count.

---

### 1.5 Ports Database (World Port Index)

**1. What is it?**  
Global port database covering 2,000+ ports worldwide with location, capacity, and industry attributes.

**2. Publisher**  
World Port Index (US National Geospatial-Intelligence Agency) / various commercial sources. The local copy appears to be a combined/cleaned version.

**3. Temporal resolution**  
Static snapshot.

**4. Spatial resolution**  
Port-level (lat/lng, country, ISO3).

**5. Coverage**  
~2,066 ports, 159 countries, 22 columns.

**6. Update frequency**  
Annual (US NGA updates).

**7. Schema quality**  
6/10. Clean CSV with headers. ISO3 codes present. Some port name inconsistencies.

**8. Missing value analysis**  
Low (<5% across key columns).

**9. Data quality**  
6/10. Port locations and names are reliable. Vessel counts and capacities may be estimated.

**10. Reliability**  
6/10 (good for static geography, moderate for dynamic data like vessel counts).

**11. Business usefulness**  
7/10. Port infrastructure is critical for maritime intelligence and supply chain resilience.

**12. ML usefulness**  
3/10. Currently collapsed to `port_count` (one integer per country). Loses: port types, capacities, vessel counts, lat/lng clustering.

**13. Feature richness**  
7/10 (raw) → 1/10 (as used). Raw 22 columns are rich; current builder discards 21 of them.

**14. Future scalability**  
3/10. Static data; only improves if updated.

**15. Limitations**  
- Static — cannot detect port congestion or operational status changes  
- Country-level aggregation discards all spatial intelligence  
- No temporal dimension

**16. Biases**  
Maritime nations overrepresented. Landlocked countries have zero ports (65 countries).

**17. Potential leakage**  
MEDIUM. Geography proxy — port_count correlates with coastline length, economic development, and maritime trade volume.

**18. Integration complexity**  
Low. Currently integrated.

**19. Current integration status**  
✅ **Partially integrated** as `port_count` (integer per country). 21 of 22 columns discarded.

**20. Should we keep it?**  
✅ **Yes, but expand feature extraction.** At minimum: port density, port type diversity, aggregate capacity, and lat/lng-based chokepoint proximity scoring.

---

### 1.6 Global Energy Monitor Trackers (GEM)

**1. What is it?**  
A family of 25+ trackers covering global energy infrastructure: coal, oil & gas, solar, wind, hydro, nuclear, bioenergy, geothermal, pipelines, LNG terminals, steel, cement, chemicals.

**2. Publisher**  
Global Energy Monitor (GEM) — an NGO tracking the global energy transition.

**3. Temporal resolution**  
Static snapshot (annual or semi-annual updates per tracker).

**4. Spatial resolution**  
Asset-level (plant, mine, terminal, pipeline with lat/lng, country, region).

**5. Coverage**  
207 countries. 25+ Excel files totaling ~200 MB. Each tracker has 1-10 sheets covering: data, units, capacity, status, ownership, financing.

**6. Update frequency**  
Varies by tracker (6-18 months).

**7. Schema quality**  
5/10. Inconsistent across trackers. Some have well-structured sheets; others have merged cells, inconsistent column names, and non-standard country fields. Sheet names vary between "Data", "Units", "Capacity", etc.

**8. Missing value analysis**  
50-80% null across tracker features due to sparse coverage (only countries with that infrastructure type are non-null).

**9. Data quality**  
7/10. GEM is research-grade. Asset counts and capacities are verified. The unstructured Excel format is the main quality barrier.

**10. Reliability**  
7/10. GEM is widely cited by IEA, UN, and academic researchers.

**11. Business usefulness**  
9/10. Energy infrastructure is the core domain for ProxyDefence's energy security mission.

**12. ML usefulness**  
5/10 (as used) → 9/10 (if capacity-weighted). Current builder collapses each tracker-sheet to a binary count, losing capacity (MW), status (operating/construction/announced), and fuel type.

**13. Feature richness**  
9/10 (raw) → 3/10 (as used). ~20+ columns per tracker covering: unit capacity, fuel type, status, technology, operator, ownership, year, coordinates. Current builder extracts only country presence.

**14. Future scalability**  
8/10. GEM releases updated trackers regularly. GIS data (GeoJSON, GPKG) also downloaded for pipelines and coal mines.

**15. Limitations**  
- Excel format (hard to parse reliably)  
- Inconsistent schemas across trackers  
- Static snapshots (no time series of changes)  
- Country names vary between trackers

**16. Biases**  
Coverage priorities reflect GEM's research focus (coal, oil & gas, renewables). Smaller countries may have less detailed data.

**17. Potential leakage**  
HIGH. Country fingerprinting. The pattern of which 28 trackers a country appears in uniquely identifies it (e.g., only Saudi Arabia has certain oil/gas combinations).

**18. Integration complexity**  
High. Current loader is fragile (try/except per file, hardcoded tracker names, single country column detection).

**19. Current integration status**  
✅ **Partially integrated**. 9 of ~25 trackers are loaded. Each tracker-sheet pair becomes a binary count feature. Capacity, status, and other dimensions are ignored.

**20. Should we keep it?**  
✅ **Essential — but fundamentally rework the loader.** Track capacity-weighted features (MW of coal, GW of solar), status-based features (capacity under construction), and fuel type diversity scores. Drop binary country-presence flags.

---

### 1.7 Global Energy Pricing (2025/2026)

**1. What is it?**  
Monthly fuel prices by country for 2025 and 2026. Covers 7 fuel types (diesel, gas, kerosene, petrol, etc.) plus trust metrics and inflation.

**2. Publisher**  
Global Energy Pricing dataset (source unclear from available metadata — likely World Bank or GTAP).

**3. Temporal resolution**  
Monthly (but aggregated to yearly in builder).

**4. Spatial resolution**  
ADM1/ADM2 (sub-national regions) → aggregated to country in builder.

**5. Coverage**  
~11 countries with any data. 4,585 rows (2025) + 1,911 rows (2026). 62 columns.

**6. Update frequency**  
Unknown (likely annual).

**7. Schema quality**  
4/10. Complex 62-column schema with many irrelevant metadata columns (ISO3, lat, lon, geo_id, etc.). Fuel price columns are a small subset.

**8. Missing value analysis**  
**96% null overall.** Only 11 countries have pricing data. Some fuel columns are 100% null.

**9. Data quality**  
3/10. High missingness, temporal misalignment (2025/2026 data in a 2024-Q1 dataset), constant values per country.

**10. Reliability**  
4/10. Source methodology unclear.

**11. Business usefulness**  
4/10. Fuel prices are directly relevant to energy security. But 96% null makes this dataset unusable in its current form.

**12. ML usefulness**  
1/10. 96% null → dropped by filters. Surviving columns are constant per country (zero variance).

**13. Feature richness**  
2/10 (as used) → 6/10 (if complete). 14 fuel price features × 2 years.

**14. Future scalability**  
2/10. No pipeline for updates.

**15. Limitations**  
- 96% null rate  
- Temporal mismatch (2025/2026 data in 2024 research period)  
- Country-level mean discards within-country price variance  
- Only 11 countries represented

**16. Biases**  
Developed/emerging economy bias (only 11 well-documented countries). Entire continents (Africa) absent.

**17. Potential leakage**  
MEDIUM. Missingness pattern identifies specific countries.

**18. Integration complexity**  
Low. Already integrated (though the data is useless).

**19. Current integration status**  
✅ **Integrated** as 14 fuel price features (7 fuels × 2 years). All features are essentially null or constant.

**20. Should we keep it?**  
❌ **Drop for v1.** 96% null, temporal mismatch, constant columns. Revisit if source improves coverage and temporal alignment is fixed.

---

### 1.8 AEO (Annual Energy Outlook) — NOT INTEGRATED

**1. What is it?**  
EIA Annual Energy Outlook — comprehensive US energy projection. 250+ MB JSONL files covering price, consumption, generation, capacity, and emissions projections under multiple scenarios.

**2. Publisher**  
US Energy Information Administration (EIA).

**3. Temporal resolution**  
Annual projections (2021-2050 for AEO2023; 2024-2050 for AEO2026).

**4. Spatial resolution**  
US-focused (national, regional). Some international energy trade.

**5. Coverage**  
AEO2023 (260 MB), AEO2025 (190 MB), AEO2026 (179 MB). Thousands of time series each. Scenarios: High LNG Price, Low LNG Price, Fast Builds, Alternative Transportation, Low Oil/Gas Supply, High Zero-Carbon Tech Cost, Alternative Electricity.

**6. Update frequency**  
Annual (EIA publishes AEO each year).

**7. Schema quality**  
7/10. JSONL format (one JSON object per line). Each series has: series_id, name, units, description, data (array of [year, value] pairs), start, end. Well-documented EIA API schema.

**8. Missing value analysis**  
Low. Each series has data for its full projection horizon.

**9. Data quality**  
8/10. EIA is the gold standard for US energy data. Peer-reviewed methodology.

**10. Reliability**  
9/10. EIA is authoritative. Projections are model-based but transparent.

**11. Business usefulness**  
8/10. US energy projections directly support energy security models, price forecasting, and scenario simulation.

**12. ML usefulness**  
7/10. As features: US energy price trends, electricity generation mix, CO2 pathways. As evaluation: scenario-based backtesting.

**13. Feature richness**  
9/10. Thousands of time series covering: electricity prices by source, generation capacity by fuel, consumption by sector, CO2 emissions, fuel production, energy trade.

**14. Future scalability**  
8/10. Annual updates available. Historical backfiles available from EIA.

**15. Limitations**  
- US-only (limits global relevance)  
- JSONL parsing is memory-intensive (250 MB files)  
- Projections are model-based, not observations

**16. Biases**  
US-centric. Model assumptions (policy scenarios, technology cost curves) may not reflect reality.

**17. Potential leakage**  
None. Projections are forward-looking but scenarios are pre-defined.

**18. Integration complexity**  
Medium. Requires JSONL parser, scenario selection logic, series taxonomy classifier.

**19. Current integration status**  
❌ **Not integrated.** Files sit in `datasets/raw/` unprocessed.

**20. Should we keep it?**  
✅ **Yes for US-centric use cases.** Not useful for global geopolitics. Essential for energy security, SPR optimization, and commodity price forecasting.

---

### 1.9 ACLED Political Violence (SUMMARY ONLY)

**1. What is it?**  
Pre-aggregated country-year counts of political violence and demonstration events. NOT the full ACLED event database.

**2. Publisher**  
Armed Conflict Location & Event Data Project (ACLED).

**3. Temporal resolution**  
Yearly (aggregated from daily event data).

**4. Spatial resolution**  
Country.

**5. Coverage**  
2,754 rows (political violence) + 2,926 rows (demonstrations). 3 columns: COUNTRY, YEAR, EVENTS. Countries: 200+. Years: 2017-2021 for most.

**6. Update frequency**  
Unknown (this appears to be a one-off extract, not the full ACLED feed).

**7. Schema quality**  
5/10. Only 3 columns. Country names are free text (not ISO3-coded). Pre-aggregated — lost all spatial and temporal granularity.

**8. Missing value analysis**  
None (simple schema).

**9. Data quality**  
5/10. ACLED is high quality, but the aggregation destroys most of its value.

**10. Reliability**  
8/10 (ACLED source) → 4/10 (aggregated format).

**11. Business usefulness**  
6/10 (as-is) → 9/10 (if full ACLED). Country-year counts are too coarse for weekly risk prediction.

**12. ML usefulness**  
2/10. Country-year counts are not useful at the country-week prediction grain.

**13. Feature richness**  
1/10. Three columns. No event type, location, actor, or temporal detail.

**14. Future scalability**  
7/10 (full ACLED API is available). 0/10 (this summary format is dead-end).

**15. Limitations**  
- Yearly aggregation only (not useful for weekly prediction)  
- Only 3 columns  
- Country names not ISO3-coded  
- No event-type breakdown (protests, battles, explosions, etc.)

**16. Biases**  
Severity bias — higher-casualty events more reliably recorded. Underreporting in conflict zones (data collection is harder where conflict is worst).

**17. Potential leakage**  
None (past data).

**18. Integration complexity**  
Low (for this format). But the format is inadequate.

**19. Current integration status**  
❌ **Not integrated.** Files exist in `datasets/raw/` but are not loaded by the builder.

**20. Should we keep it?**  
⚠️ **Only if supplemented with full ACLED data.** The yearly summaries are too coarse. Replace with the full ACLED event database (available via API).

---

### 1.10 Coal Mine Boundaries and Methane Sources — NOT INTEGRATED

**1. What is it?**  
GeoJSON/XLSX pairs for individual coal mine boundaries worldwide. 3.8 MB zip, 503 files. Part of GEM's coal mine tracker.

**2. Publisher**  
Global Energy Monitor.

**3. Temporal resolution**  
Static snapshot.

**4. Spatial resolution**  
Mine-level (polygon boundaries in GeoJSON, attributes in XLSX).

**5. Coverage**  
~500 mines worldwide (subset of GEM's coal mine tracker).

**6. Update frequency**  
Unknown.

**7. Schema quality**  
7/10 (GeoJSON is standard, XLSX has mine attributes).

**8. Missing value analysis**  
Not assessed (individual files).

**9. Data quality**  
7/10 (research-grade spatial data).

**10. Reliability**  
7/10 (GEM quality).

**11. Business usefulness**  
3/10 (niche — methane-specific use cases). Not directly useful for most ProxyDefence objectives.

**12. ML usefulness**  
2/10. Spatial features would require a graph or geospatial model.

**13. Feature richness**  
N/A (per-mine spatial data).

**14. Future scalability**  
N/A.

**15. Limitations**  
- Mine-level boundaries are difficult to integrate into country-week models  
- Methane-specific (coal mines only)  
- 500 mines is a small sample

**16. Biases**  
Coal mine focus (not oil/gas methane).

**17. Potential leakage**  
None.

**18. Integration complexity**  
High. Requires geospatial processing (shapely, geopandas).

**19. Current integration status**  
❌ **Not integrated.**

**20. Should we keep it?**  
❌ **Low priority.** Only relevant for methane-specific use cases.

---

### 1.11 Oil/NGL Pipeline GIS (GEM) — NOT INTEGRATED

**1. What is it?**  
GeoJSON and GPKG files for global oil and NGL pipelines from GEM's GOIT tracker. 66 MB zip.

**2. Publisher**  
GEM.

**3. Temporal resolution**  
Static (2026-06 snapshot).

**4. Spatial resolution**  
Pipeline-segment-level (linestrings with attributes).

**5. Coverage**  
Global oil and NGL pipelines.

**6. Update frequency**  
Periodic GEM updates.

**7. Schema quality**  
8/10 (standard GeoJSON/GPKG).

**8-19** Similar to pipeline tabular data but with spatial geometry.

**20. Should we keep it?**  
✅ **Yes for maritime/energy use cases.** Pipeline proximity scoring, chokepoint analysis, supply route modeling. Requires spatial integration.

---

### 1.12 LNG Carrier Tracker — NOT INTEGRATED

**1. What is it?**  
Excel tracker of LNG carrier vessels worldwide. 312 KB. Part of GEM.

**2. Publisher**  
GEM.

**3. Temporal resolution**  
Static (December 2025 snapshot).

**4. Spatial resolution**  
Vessel-level (country, operator, capacity).

**5. Coverage**  
Global LNG carrier fleet.

**6. Update frequency**  
Unknown.

**7. Schema quality**  
5/10 (Excel, varies by sheet).

**8-19.** Similar to GEM trackers.

**20. Should we keep it?**  
✅ **Yes for LNG intelligence.** Fleet size, age, and capacity are useful for supply chain modeling.

---

### 1.13 GEM LNG Terminals (GIS) — NOT INTEGRATED

**1. What is it?**  
GeoJSON and GPKG for global LNG terminals.

**2. Publisher**  
GEM.

**3. Temporal resolution**  
Static (2025-09 snapshot).

**4. Spatial resolution**  
Terminal-level points.

**20. Should we keep it?**  
✅ **Yes for LNG intelligence.**

---

### 1.14 Global Iron & Steel Tracker (GEM) — NOT INTEGRATED

Three files: plant-level data, iron units, steel units. 1.6 MB total. Part of GEM. Critical minerals focus.

**20. Should we keep it?**  
✅ **Yes for critical minerals intelligence.** Iron ore and steel are essential to supply chain monitoring.

---

### 1.15 Global Cement & Concrete Tracker (GEM) — NOT INTEGRATED

**20. Should we keep it?**  
✅ **Yes for critical minerals / supply chain.** Cement is a strategic commodity.

---

### 1.16 Global Chemicals Inventory (GEM) — NOT INTEGRATED

**20. Should we keep it?**  
✅ **Yes for supply chain / sanctions.** Chemicals are highly relevant to procurement optimization.

---

### 1.17 Generated Dataset: `geopolitical_risk_v1`

**1. What is it?**  
Country-week panel dataset for geopolitical risk classification. 717 rows (5,953 in full build), 75 columns. Built from GDELT Events + OFAC + Ports + Energy + GEM.

**2. Publisher**  
Internal ProxyDefence builder.

**3. Temporal resolution**  
Weekly (ISO week).

**4. Spatial resolution**  
Country (ISO3).

**5. Coverage**  
224 countries, 14 weeks (in full build). Current test build: 717 rows across multiple years.

**6. Update frequency**  
Re-built manually.

**7. Schema quality**  
7/10. Well-documented in metadata.json, feature_stats.json, and reports.

**8. Missing value analysis**  
- escalation_flag_t1: ~30% NaN (expected — last week per country)  
- Energy features: 96-100% null  
- GEM features: 50-80% null  
- Lag-4 features: 83% null (insufficient history)

**9. Data quality**  
5/10. Usable but known issues: static feature leakage, temporal sparsity, energy price contamination.

**10. Reliability**  
6/10. Deterministic build process. But depends on GDELT data quality.

**11. Business usefulness**  
5/10 (current) → 8/10 (with escalation target + GKG/Mentions integration).

**12. ML usefulness**  
5/10. Small dataset (5,953 rows), high feature-to-sample ratio, known leakage issues. RF/XGBoost achieve perfect 1.0 AUC — very suspicious.

**13. Feature richness**  
7/10. 14 base GDELT features + 26 engineered + ~42 static. Good breadth but many are low quality.

**14. Future scalability**  
7/10. Can expand to more GDELT columns, add Mentions/GKG, refresh with more data.

**15. Limitations**  
- Only 14 weeks of temporal coverage  
- Same-week target (nowcasting, not forecasting)  
- Static feature leakage (country identity)  
- Energy features are useless (96% null)  
- No GKG/Mentions integration  
- Empty validation split in current build

**16. Biases**  
Inherits all GDELT biases.

**17. Potential leakage**  
- Static features leak country identity  
- risk_flag uses same-week events (no temporal leakage, but no forecasting value)  
- escalation_flag_t1: computed from t+1 data — potential cross-split contamination

**18. Integration complexity**  
N/A (it's the integration output).

**19. Current integration status**  
N/A.

**20. Should we keep it?**  
✅ **Yes, as the primary output of the builder.** But address the issues above before using it for model training.

---

## 2. Dataset-to-Use-Case Scoring Matrix

Score definitions: 0 = useless, 5 = moderately useful, 10 = essential.

| Dataset | GeoRisk | Conflict Escalation | Energy Security | Oil Supply | LNG Intel | Critical Minerals | Procurement | SPR | Digital Twin | Maritime | Ports | Shipping | Supply Chain | Econ Forecast | Commodity Prices | Country Risk | Policy | Sanctions | KG | RAG | Agent Memory | Scenario Sim | Forecasting | Classification | GNN | Time Series | Anomaly | Recommendations | Dashboards |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **GDELT Events** | 10 | 10 | 6 | 6 | 5 | 4 | 5 | 2 | 4 | 7 | 6 | 7 | 8 | 8 | 7 | 10 | 10 | 8 | 9 | 9 | 9 | 9 | 10 | 9 | 8 | 10 | 7 | 5 | 9 |
| **GDELT GKG** | 9 | 8 | 7 | 6 | 5 | 4 | 5 | 2 | 4 | 5 | 4 | 5 | 7 | 8 | 7 | 9 | 10 | 7 | 10 | 10 | 9 | 9 | 9 | 8 | 8 | 9 | 7 | 5 | 8 |
| **GDELT Mentions** | 7 | 7 | 5 | 5 | 4 | 3 | 5 | 1 | 3 | 6 | 5 | 6 | 7 | 6 | 5 | 7 | 7 | 6 | 8 | 8 | 7 | 7 | 8 | 7 | 6 | 8 | 6 | 4 | 7 |
| **OFAC** | 5 | 3 | 7 | 7 | 4 | 4 | 8 | 5 | 3 | 2 | 1 | 2 | 7 | 4 | 3 | 8 | 6 | 10 | 6 | 7 | 7 | 6 | 3 | 5 | 2 | 2 | 3 | 4 | 5 |
| **Ports** | 3 | 2 | 7 | 8 | 6 | 3 | 6 | 1 | 5 | 9 | 10 | 8 | 8 | 5 | 4 | 4 | 3 | 2 | 4 | 5 | 4 | 5 | 3 | 3 | 3 | 3 | 3 | 3 | 5 |
| **GEM Coal Tracker** | 3 | 2 | 8 | 1 | 1 | 5 | 6 | 1 | 6 | 2 | 1 | 1 | 5 | 3 | 6 | 3 | 4 | 1 | 5 | 6 | 5 | 7 | 3 | 3 | 3 | 3 | 4 | 2 | 4 |
| **GEM Oil&Gas Extraction** | 5 | 4 | 10 | 10 | 8 | 2 | 7 | 3 | 8 | 3 | 2 | 3 | 8 | 7 | 9 | 5 | 6 | 4 | 6 | 7 | 6 | 8 | 5 | 4 | 4 | 5 | 5 | 4 | 6 |
| **GEM Solar/Wind/Hydro** | 2 | 1 | 8 | 1 | 1 | 1 | 3 | 1 | 7 | 1 | 1 | 1 | 3 | 5 | 3 | 2 | 5 | 1 | 4 | 5 | 4 | 7 | 3 | 2 | 2 | 3 | 3 | 2 | 4 |
| **GEM Pipelines (Gas)** | 4 | 3 | 10 | 8 | 9 | 1 | 6 | 2 | 8 | 1 | 1 | 1 | 8 | 6 | 8 | 4 | 5 | 3 | 5 | 6 | 5 | 8 | 4 | 3 | 4 | 4 | 4 | 3 | 5 |
| **GEM Pipelines (Oil)** | 4 | 3 | 10 | 10 | 3 | 1 | 7 | 3 | 8 | 1 | 1 | 1 | 9 | 7 | 9 | 4 | 5 | 4 | 5 | 6 | 5 | 8 | 4 | 3 | 4 | 4 | 4 | 3 | 5 |
| **GEM LNG Terminals** | 3 | 2 | 9 | 3 | 10 | 1 | 5 | 3 | 7 | 3 | 2 | 3 | 8 | 7 | 9 | 3 | 4 | 3 | 4 | 5 | 4 | 7 | 4 | 3 | 3 | 4 | 4 | 3 | 5 |
| **GEM LNG Carriers** | 2 | 1 | 8 | 2 | 10 | 1 | 4 | 2 | 6 | 5 | 3 | 5 | 7 | 6 | 8 | 2 | 3 | 2 | 3 | 4 | 3 | 6 | 3 | 2 | 2 | 3 | 3 | 2 | 4 |
| **GEM Nuclear Tracker** | 2 | 1 | 7 | 1 | 1 | 1 | 2 | 1 | 5 | 1 | 1 | 1 | 2 | 3 | 2 | 2 | 4 | 1 | 3 | 4 | 3 | 6 | 2 | 2 | 2 | 2 | 2 | 1 | 3 |
| **GEM Steel/Iron** | 2 | 1 | 4 | 1 | 1 | 9 | 7 | 1 | 3 | 1 | 1 | 1 | 6 | 4 | 5 | 2 | 3 | 2 | 3 | 4 | 3 | 4 | 2 | 2 | 2 | 2 | 2 | 1 | 3 |
| **GEM Cement/Concrete** | 1 | 1 | 3 | 1 | 1 | 5 | 6 | 1 | 2 | 1 | 1 | 1 | 5 | 3 | 3 | 1 | 2 | 1 | 2 | 3 | 2 | 3 | 1 | 1 | 1 | 1 | 2 | 1 | 2 |
| **GEM Chemicals** | 2 | 1 | 5 | 3 | 2 | 4 | 8 | 1 | 4 | 1 | 1 | 1 | 6 | 4 | 4 | 2 | 3 | 3 | 3 | 4 | 3 | 4 | 2 | 2 | 2 | 2 | 3 | 2 | 3 |
| **Global Energy Pricing** | 2 | 1 | 5 | 5 | 4 | 1 | 4 | 2 | 2 | 1 | 1 | 1 | 3 | 4 | 6 | 2 | 2 | 1 | 2 | 3 | 2 | 3 | 2 | 2 | 1 | 2 | 2 | 1 | 3 |
| **AEO 2023/2025/2026** | 2 | 1 | 8 | 8 | 7 | 2 | 5 | 7 | 5 | 2 | 1 | 2 | 5 | 8 | 8 | 3 | 5 | 2 | 4 | 5 | 4 | 9 | 6 | 3 | 2 | 6 | 3 | 3 | 6 |
| **ACLED (summary)** | 4 | 3 | 2 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 1 | 3 | 3 | 1 | 3 | 3 | 2 | 2 | 2 | 2 | 1 | 2 | 1 | 1 | 3 |
| **Coal Mine Boundaries** | 1 | 1 | 4 | 1 | 1 | 3 | 3 | 1 | 2 | 1 | 1 | 1 | 2 | 1 | 2 | 1 | 1 | 1 | 2 | 2 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 2 |
| **Oil Pipeline GIS** | 3 | 2 | 9 | 9 | 3 | 1 | 5 | 2 | 7 | 1 | 1 | 1 | 7 | 5 | 7 | 3 | 3 | 2 | 4 | 4 | 3 | 6 | 3 | 2 | 3 | 3 | 3 | 2 | 4 |
| **Gas Pipeline GIS** | 3 | 2 | 9 | 2 | 9 | 1 | 5 | 2 | 7 | 1 | 1 | 1 | 7 | 5 | 7 | 3 | 3 | 2 | 4 | 4 | 3 | 6 | 3 | 2 | 3 | 3 | 3 | 2 | 4 |

---

## 3. Final Evaluation Matrix

| Dataset | Coverage (0-10) | Quality (0-10) | Freshness (0-10) | ML Value (0-10) | Business Value (0-10) | Research Value (0-10) | Engineering Cost (0-10, lower=cheaper) | **Overall Score** | **Recommendation** |
|---|---|---|---|---|---|---|---|---|---|
| GDELT Events | 9 | 8 | 7 | 9 | 9 | 10 | 3 (cheap) | **8.6** | **KEEP — expand column usage** |
| GDELT GKG | 3 | 6 | 7 | 8 | 8 | 9 | 6 | **6.4** | **INTEGRATE — highest priority** |
| GDELT Mentions | 3 | 7 | 7 | 7 | 7 | 8 | 4 | **6.3** | **INTEGRATE — high priority** |
| OFAC | 5 | 5 | 5 | 3 | 6 | 5 | 2 | **4.7** | **KEEP — add program type parsing** |
| Ports | 7 | 6 | 5 | 3 | 7 | 5 | 2 | **5.1** | **KEEP — expand feature extraction** |
| GEM (all trackers) | 8 | 7 | 8 | 7 | 9 | 8 | 7 | **7.5** | **KEEP — rework loader for capacity** |
| Global Energy Pricing | 1 | 3 | 4 | 1 | 4 | 2 | 1 | **2.4** | **DROP for v1** |
| AEO (all years) | 5 | 8 | 8 | 7 | 8 | 7 | 6 | **6.8** | **INTEGRATE — US energy focus** |
| ACLED (summary) | 2 | 4 | 3 | 2 | 6 | 4 | 1 | **3.1** | **REPLACE with full ACLED API** |
| Coal Mine Boundaries | 3 | 7 | 7 | 2 | 3 | 3 | 8 | **3.8** | **LOW PRIORITY** |
| Oil Pipeline GIS | 6 | 8 | 8 | 3 | 9 | 6 | 7 | **6.1** | **INTEGRATE — high value for energy** |
| LNG Terminal GIS | 5 | 7 | 7 | 3 | 8 | 5 | 6 | **5.5** | **INTEGRATE — LNG use case** |

**Overall Score formula**: (Coverage + Quality + Freshness)/3 × 0.25 + (ML Value + Business Value + Research Value)/3 × 0.50 + (10 - Engineering Cost) × 0.25. This weights ML/Business value at 50%, engineering cost at 25%, and data quality at 25%.

---

## 4. Top 10 Highest Value Datasets

These datasets deserve maximum engineering effort:

| Rank | Dataset | Rationale |
|------|---------|-----------|
| **1** | **GDELT Events (expanded)** | Already integrated but using only 21% of available columns. Expand to include EventRootCode, EventBaseCode hierarchies (CAMEO taxonomy — 300 event types), NumMentions/NumSources/NumArticles per event type, full actor code taxonomy (type1/type2/type3 for both actors). This alone would double feature richness. |
| **2** | **GDELT GKG** | The single biggest missed opportunity. Theme extraction (CRISISLEX, ECE_ECON_ECONRISK, TAX_FNCACT, etc.) provides qualitative signal that event counts cannot capture. Allows topic modeling, emotion tracking, and narrative analysis. Already on disk. |
| **3** | **GDELT Mentions** | Source diversity metrics. Which outlets are covering which events? A story covered by 100 global outlets is more significant than one covered by 1 local paper. Source prominence scoring enables media influence weighting. Partially on disk. |
| **4** | **GEM Oil & Gas Extraction** | Capacity-weighted features (not binary presence flags). Track oil/gas field production, reserves, operator, status. Directly feeds energy security, oil supply, and commodity price models. Already on disk. |
| **5** | **GEM Pipelines (Oil + Gas GIS)** | GeoJSON pipeline data enables chokepoint proximity scoring, supply route dependency analysis, and pipeline density mapping. Essential for energy security and digital twin. Already on disk. |
| **6** | **Full ACLED (API)** | The yearly summaries on disk are useless. The full ACLED API provides daily event-level conflict data with event type (battles, explosions, protests, riots, strategic developments), location, and actors. Independent validation source for GDELT-based predictions. Not on disk — requires API integration. |
| **7** | **AEO 2023/2025/2026** | US energy projections across multiple scenarios. Enables scenario simulation, backtesting, price forecasting. Already on disk (630 MB extracted). |
| **8** | **Ports (expanded)** | Current single-feature (`port_count`) discards 21 of 22 columns. Add: port type (container, bulk, liquid, dry), vessel capacity, industry classification, lat/lng for chokepoint scoring. Already on disk. |
| **9** | **OFAC (expanded)** | Add sanction program type (Iran, Russia, terrorism, narcotics, etc.), entity type (individual, organization, vessel), and temporal dimension (imposition date) if available. Country-level aggregation destroys most signal. Already on disk. |
| **10** | **GEM LNG Terminals + Carriers** | LNG-specific features for LNG intelligence use case. Terminal capacity, carrier fleet age and capacity, import/export orientation. Already on disk. |

---

## 5. Low Value Datasets

These datasets should NOT receive engineering effort in the current phase:

| Dataset | Reason |
|---------|--------|
| **Global Energy Pricing 2025/2026** | 96% null. Temporal misalignment (2025/2026 data in 2024 research period). Only 11 countries. Constant columns. Useless for any current model. |
| **ACLED Country-Year Summaries** | Yearly aggregation is useless for weekly prediction. Copy of a small subset of ACLED. Must replace with full ACLED API. |
| **Coal Mine Boundaries (GIS)** | 500 mine polygons. Methane-specific. Too niche for current objectives. |
| **Global Energy Pricing (metadata columns)** | Cols like lat, lon, geo_id, ISO3 are not fuel prices. They should have been dropped in the builder. |
| **Empty staging directories** | `commodity/`, `energy/eia/`, `energy/fred/`, `energy/opec/`, `kaggle/`, `ports/`, `sanctions/`, `shipping/ais/`, `un_comtrade/`, `world_bank/` — all empty. No engineering effort needed until data is acquired. |

---

## 6. Missing Datasets

These datasets are **absolutely required** for the project's mission and are NOT currently present:

### CRITICAL (blocking major use cases)

| Dataset | Use Case | Why It's Missing | Acquisition Cost |
|---------|----------|-----------------|-----------------|
| **Full ACLED** (daily events via API) | Conflict validation, independent signal, model evaluation | Only yearly summaries downloaded. Full API available at acleddata.com | Free (academic license). ~$500/yr commercial. |
| **AIS Vessel Tracking** (real-time or daily) | Maritime intelligence, port congestion, shipping route optimization, supply chain disruption | Empty `shipping/ais/` directory. Requires commercial provider (Spire, MarineTraffic, exactEarth) | $500-$5,000/month for API access |
| **Commodity Spot/Futures Prices** (daily) | Commodity price forecasting, economic modeling, SPR optimization | Empty `commodity/` directory. Free sources: EIA, IMF, World Bank. | Free (EIA, IMF) to $1,000/mo (Refinitiv, Bloomberg) |
| **EIA Weekly Petroleum Status** | Oil supply intelligence, SPR optimization, energy security | Empty `energy/eia/` directory. Free API from eia.gov. | Free |

### HIGH (materially improve multiple use cases)

| Dataset | Use Case | Why It's Missing | Acquisition Cost |
|---------|----------|-----------------|-----------------|
| **UN Comtrade** (trade flows) | Supply chain disruption, procurement optimization, economic impact | Empty `un_comtrade/`. Free API with rate limits. | Free (basic) to $5,000/yr (full) |
| **World Bank Indicators** | Economic impact, country risk scoring, policy intelligence | Empty `world_bank/`. Free API. | Free |
| **OPEC Monthly Oil Report** | Oil supply intelligence, commodity forecasting | Empty `energy/opec/`. Free download from opec.org. | Free |
| **IMF Primary Commodity Prices** | Commodity forecasting, economic modeling | Available as free CSV download. | Free |

### MEDIUM (useful for specific use cases)

| Dataset | Use Case |
|---------|----------|
| **S&P Global / Platts** (energy price assessments) | LNG, oil, coal price benchmarks |
| **Clarksons Shipping Intelligence** | Vessel tracking, freight rates, port congestion |
| **Refinitiv Eikon / Reuters** | Real-time commodities, news, analytics |
| **IEA Monthly Oil Data Service** | Supply/demand balances, refinery throughput |
| **US Energy Mapping System** (EIA) | Pipeline, refinery, power plant GIS layers |
| **IHS Markit / S&P Global Connectivity** | Pipeline, LNG, refining database |
| **BP Statistical Review of World Energy** | Annual production/consumption by country |
| **UCDP/PRIO Armed Conflict** | Conflict event validation (complement to ACLED) |
| **FAO Food Price Index** | Food-energy nexus |

---

## 7. Current Feature Set Review

### 7.1 GDELT Base Features (14 features)

| Feature | Informative? | Redundant? | Leaking? | Scientific Value | Keep? |
|---------|-------------|------------|----------|-----------------|-------|
| `total_events` | Yes — volume proxy | With `total_mentions`/`total_articles`/`total_sources` (r > 0.99) | No | 7/10 — captures attention | Keep, but note collinearity |
| `goldstein_mean` | Yes — central tone | No | No | 8/10 — validated conflict measure | Keep |
| `goldstein_std` | Yes — tone volatility | No | No | 7/10 — high std = high event diversity | Keep |
| `goldstein_min` | Yes — worst event | No | No | 9/10 — captures extreme negative events | **Keep — top LR feature** |
| `goldstein_max` | Marginal — best event | No | No | 5/10 — positive events less informative | Keep |
| `goldstein_neg_count` | Yes — core conflict proxy | With target (by construction) | **YES — this IS the target** | 9/10 — but **must not be a feature for nowcasting** | **Remove as feature for forecasting** |
| `goldstein_pos_count` | Moderate | No | No | 5/10 — low variance | Keep |
| `quadclass_verbal_conflict` | Yes — leading indicator | No | No | 8/10 — verbal conflict precedes material | Keep |
| `quadclass_material_conflict` | Yes — direct conflict | With goldstein_neg_count | No | 8/10 — direct conflict measure | Keep |
| `total_mentions` | Marginal — media amplification | With total_articles (r > 0.99) | No | 4/10 — redundant with `total_articles` | **Drop or merge with articles** |
| `total_sources` | Moderate — source diversity | With total_events (r > 0.99) | No | 5/10 — useful but collinear | Keep but note collinearity |
| `total_articles` | Marginal — same as mentions | With total_mentions (r > 0.99) | No | 4/10 — redundant | **Drop or merge with mentions** |
| `avg_tone` | Yes — media sentiment | No | No | 7/10 — media tone is a leading indicator | Keep |
| `unique_actors1` | Yes — internationalization | No | No | 8/10 — Top 3 LR coefficient (3.04) | Keep |
| `unique_actors2` | Yes — internationalization | With actors1 (r ~0.7) | No | 8/10 — Top 1 LR coefficient (4.26) | Keep |
| `conflict_event_ratio` | Yes — normalized conflict | Derived from quadclass | No | 7/10 — better than raw counts for comparison | Keep |

**Key finding**: `total_mentions` and `total_articles` are near-perfectly correlated (r > 0.999). One should be dropped. Similarly, `goldstein_neg_count` must be removed as a feature in forecasting mode since it directly defines the target.

### 7.2 Engineered Temporal Features (26 features)

| Feature Group | Informative? | Redundant? | Leaking? | Scientific Value | Keep? |
|--------------|-------------|------------|----------|-----------------|-------|
| `{x}_lag1` (6 features) | Yes — autoregressive | With base features (r > 0.9) | No | 7/10 — standard time-series feature | Keep |
| `{x}_lag4` (6 features) | Moderate — month-ago comparison | With lag1 (r varies) | No | 6/10 — useful for trend detection | Keep |
| `{x}_rolling4_mean` (6 features) | Yes — smoothed trend | With base features (r > 0.99) | No | 6/10 — very high collinearity with base | **Drop or replace with lagged rolling** |
| `{x}_change_wow` (6 features) | Yes — velocity/acceleration | With base features (r > 0.99 for some) | No | 8/10 — WoW change is information-dense | Keep |
| `week_sin` / `week_cos` | Very low (14 weeks data) | No | No | 2/10 — 14 weeks is insufficient for seasonality | Keep (minimal cost) |

**Key finding**: All rolling4_mean features have r > 0.999 with their base features when only 1-2 weeks of data exist per country. This is because `min_periods=1` means the rolling mean IS the current value for early weeks. This artificially inflates correlation. Either increase min_periods or drop rolling features until more data exists.

### 7.3 Static Features (~42 features)

| Feature | Informative? | Redundant? | Leaking? | Scientific Value | Keep? |
|---------|-------------|------------|----------|-----------------|-------|
| `sanction_count` | Moderate | No | **HIGH** — country identity | 3/10 | Keep (log-transformed). Monitor. |
| `port_count` | Low — geography proxy | No | **MEDIUM** — landlocked indicator | 2/10 | Keep (binary `has_port`). Monitor. |
| `energy_2025_*` (7 features) | None — 96% null | Yes — identical values | **HIGH** — missingness pattern | 0/10 | **DROP** |
| `energy_2026_*` (7 features) | None — 96% null | Yes — identical values | **HIGH** — missingness pattern | 0/10 | **DROP** |
| GEM tracker-sheet flags (~28) | Low — binary country presence | Some | **HIGH** — country fingerprint | 2/10 | **Replace** with capacity-weighted features |

---

## 8. Current Target Critique

### 8.1 `risk_flag` (Existing Target)

**Definition**: `1 if goldstein_neg_count > median(dataset)`

**Scientific problems**:

1. **NOWCAST, not forecast**: Features and target are from the same week. The model learns "what is happening now," not "what will happen next." This is a description, not a prediction.

2. **Dataset-dependent threshold**: The median is computed from the training period. A model trained during a peaceful period uses a different threshold than one trained during a conflictual period. Not portable across time periods.

3. **Relative, not absolute**: A country can be flagged as "at risk" during a mildly negative week if the global median is low. The model cannot distinguish "routine low-level conflict" from "emerging crisis."

4. **Goldstein_neg_count IS the target**: Since `risk_flag` is derived from `goldstein_neg_count`, and `goldstein_neg_count` is used as a feature, the model has access to the exact variable defining the target. This explains RF/XGBoost perfect 1.0 AUC — they found a split on `goldstein_neg_count` that perfectly separates the median.

**Verdict**: **SCIENTIFICALLY INVALID** for classification. Not a forecasting target. The perfect tree-model scores are a consequence of target-feature overlap, not genuine predictive power. The LR's 0.9675 AUC is inflated for the same reason, mitigated only by LR's smooth decision boundary.

### 8.2 `escalation_flag_t1` (Proposed Target)

**Definition**: `1 if goldstein_neg_count_{t+1} > 1.5 * goldstein_neg_count_t`

**Scientific assessment**:

1. **TRUE FORECAST**: Predicts next week from this week's features. No target-feature overlap. Correct temporal direction.

2. **OBJECTIVE threshold**: 50% week-over-week increase. Not dataset-dependent. Portable. Not relative.

3. **BUSINESS-ALIGNED**: "Is the situation getting significantly worse?" This is what decision-makers need to know.

4. **PER-COUNTRY normalization**: Each country evaluated against its own prior week. A small spike in a peaceful country is treated as seriously as a large spike in a conflict zone.

**Concerns**:
- ~15-25% positive rate (imbalanced)
- 1.5x threshold is arbitrary (but based on variance analysis)
- Last week per country has NaN (expected and manageable)

**Verdict**: **SCIENTIFICALLY SOUND**. The strongest supervised learning target available. Requires class imbalance handling (class weights, resampling) and temporal walk-forward validation.

### 8.3 Recommended Target Strategy

```
PRIMARY TARGET:     escalation_flag_t1 (binary forecasting)
SECONDARY TARGET:   risk_flag (binary nowcasting — keep for comparison only)
FUTURE TARGET v3:   Multi-class escalation (unchanged / elevated / critical)
                    OR regression: goldstein_neg_count_{t+1} (continuous)
```

---

## 9. Strategic Recommendations

### 9.1 If you had to build this project from scratch, would you use these datasets?

**Partially.** The dataset selection is defensible but the engineering focus is misplaced.

**What I would keep:**
- GDELT Events (core temporal signal)
- GDELT GKG (thematic signal — would integrate immediately)
- GEM (but with capacity-weighted features from day one)
- AEO (US energy projections)
- Ports (but with full schema from day one)
- OFAC (but with program-type parsing)

**What I would delay:**
- Global Energy Pricing (until better coverage or temporal alignment)
- Coal mine boundaries (niche)

**What I would acquire before writing a single line of model code:**
- Full ACLED (daily events, not yearly summaries)
- AIS vessel tracking (maritime intelligence is impossible without it)
- EIA weekly petroleum data (free, immediate energy security signal)
- Commodity futures prices (free from EIA, IMF)

### 9.2 What datasets deserve the biggest investment?

| Dataset | Investment Type | Expected ROI |
|---------|----------------|-------------|
| **GDELT GKG** | Engineering (parse 27 columns, theme extraction) | **Highest ROI in project**. Theme features alone could double model performance. Data already on disk. |
| **GDELT Events (expand columns)** | Engineering (add 12 more columns) | High ROI. CAMEO event type hierarchy adds 300-category classification signal. |
| **GEM (capacity-weighted)** | Engineering (rework loader for capacity/status) | High ROI. GW of solar, MW of coal, pipeline km are vastly more informative than binary presence flags. |
| **AEO integration** | Engineering (JSONL parser, scenario selector) | Medium ROI. Unlocks scenario simulation and US energy forecasting. |

### 9.3 Where is the biggest weakness in our data?

**Ranked by severity:**

1. **Temporal coverage**: 14 weeks is scientifically insufficient for time-series ML. Need 3+ years (156+ weeks) for credible seasonality, trend estimation, and evaluation.

2. **Missing GKG/Mentions**: 27-column GKG data and 16-column Mentions data sit on disk unused. This is the single largest underutilized asset.

3. **Static feature contamination**: 42 static features create country fingerprints. Current models may be learning country identity, not risk patterns.

4. **No independent validation signal**: No ACLED, UCDP, or other conflict dataset to validate GDELT-based predictions against.

5. **No maritime data**: Empty `shipping/ais/` directory means maritime intelligence, port congestion, and shipping route optimization are data-free use cases.

6. **Energy pricing unusable**: 96% null, temporal mismatch, constant columns.

7. **Target-feature overlap**: `goldstein_neg_count` is both a feature and the sole determinant of the target. This is a fundamental scientific error that invalidates current model scores.

### 9.4 Where is the biggest strength?

1. **GDELT data volume**: 21.6M events is a world-class dataset. The raw material is excellent.

2. **GEM infrastructure coverage**: 25+ trackers covering every energy type, globally. The breadth is unmatched by any single commercial dataset.

3. **AEO projections**: 630 MB of EIA scenario data enables sophisticated energy modeling that most projects lack.

4. **Documentation quality**: The existing reports (DATASET_CARD, FEATURE_CATALOG, TARGET_DESIGN_REVIEW, STATIC_FEATURE_REVIEW) are thorough and honest about limitations. This scientific self-awareness is rare and valuable.

5. **Pipeline reproducibility**: The builder is deterministic and well-structured. Reproducibility is excellent.

### 9.5 What should be the next research milestone before touching model optimization?

**Do NOT optimize models. Do NOT tune hyperparameters. Do NOT try different architectures.**

The next milestone is:

## **Phase 2: Data Integrity & Feature Expansion**

### Must-haves (sequential, not parallel):

1. **Fix target-feature overlap** ✅ (DONE — escalation_flag_t1 added in Phase 1)

2. **Remove goldstein_neg_count as a feature** in forecasting mode (it defines the target for nowcasting; for forecasting it's moderately useful as a lag feature but must not be used at t+0 for the escalation target)

3. **Integrate GDELT GKG**: Extract top 50 themes as binary/weekly-count features. This alone could transform model performance.

4. **Integrate GDELT Mentions**: Add source diversity metrics (unique sources per event, source prominence weighting).

5. **Expand GDELT Events columns**: Add EventRootCode hierarchy (300 CAMEO event types → ~30 root category counts), NumMentions/NumSources/NumArticles per event type.

6. **Rework GEM loader**: Replace binary country-presence flags with capacity-weighted features (MW, km, tonnes).

7. **Kill energy pricing features**: Remove the 14 useless fuel price columns.

### Should-haves:

8. **Expand temporal coverage**: Download GDELT for 2023-Q1 through 2024-Q2 (at minimum 18 months).

9. **Add ACLED validation**: Download full ACLED (free academic API). Use for `escalation_flag_t1` validation.

10. **Walk-forward validation framework**: Implement proper temporal cross-validation (expanding window, not random split).

### Model training (ONLY after 1-7 are complete):

11. **Retrain Logistic Regression** with corrected features (no target-feature overlap). This establishes the honest baseline.

12. **If LR beats 0.75 ROC AUC**: Proceed to RF and XGBoost with walk-forward CV.

13. **If LR is below 0.65 ROC AUC**: The data is not yet predictive. Revisit feature engineering before training complex models.

---

## Appendix: Data Sources by Status

| Status | Count | Sources |
|--------|-------|---------|
| ✅ Integrated (well) | 2 | GDELT Events (partial), Ports (partial) |
| ⚠️ Integrated (poorly) | 3 | OFAC, GEM, Global Energy Pricing |
| 📦 On disk, not integrated | 12+ | GDELT GKG, GDELT Mentions, AEO 2023/2025/2026, ACLED summaries, Pipeline GIS, LNG GIS, Coal Mines GIS, Iron/Steel, Cement, Chemicals |
| 🗺️ Empty directory | 10 | commodity/, eia/, fred/, opec/, kaggle/, ports/, sanctions/, ais/, un_comtrade/, world_bank/ |
| 📡 Not acquired | 5+ | Full ACLED API, AIS real-time, UN Comtrade, World Bank, EIA weekly |

---

*End of report. 43 datasets reviewed. 8,800+ files examined. 21.6M GDELT events analyzed.*
