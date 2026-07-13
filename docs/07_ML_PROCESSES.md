# ML Processes in ProxyDefence

This doc explains every place machine learning actually touches this codebase — what's
genuinely trained/ML-driven, what's a deterministic simulation or rule-based formula that
looks ML-ish but isn't, and how the pieces connect. Written from the code as it stands, not
from aspirational docs.

## The mental model

```
News article arrives (Kafka: raw_articles)
        │
        ▼
Article enrichment consumer  ← REAL ML (sentiment, NER, topic, blended threat score)
        │
        ▼
processed_articles (Postgres) + Elasticsearch
        │
        ▼
ArticleSignalIngestor → energy.disruption_signals  ← rule-based, consumes ML's threat_score
        │
        ▼
corridor_risk.py (composite index, NOT a trained model)
        │
        ▼
digital_twin/ (deterministic network-flow simulation, NOT ML)
        │
        ▼
procurement/optimizer.py (multi-objective formula + Pareto, NOT ML — the trained ranker exists but isn't called here)
```

Two things are genuinely "ML" in the classic trained-model sense: the **article enrichment
consumer** (runs on every ingested article, in real time) and the **five models trained
offline** in ml-platform (one of which — the disruption classifier — feeds back into the
live pipeline; the other four are trained and benchmarked but not currently wired into a
live decision path).

---

## 1. Article enrichment consumer (real-time ML)

`services/ml-platform/consumer/article_enrichment.py` + `consumer/ml_core/` — runs on every
article as it comes off the `raw_articles` Kafka topic.

- **Sentiment**: HuggingFace `distilbert-base-uncased-finetuned-sst-2-english`
  (`ml_core/models.py`), run over the first 1000 chars of the article. Falls back to a
  neutral default if the pipeline can't load.
- **Named entity recognition**: `dbmdz/bert-large-cased-finetuned-conll03-english`, falling
  back to spaCy's `en_core_web_sm` if transformers isn't available. Filtered to
  LOC/ORG/PER/MISC entities with confidence > 0.70, capped at 12 unique entities per article.
- **Topic classification**: a trained XGBoost classifier (5 classes: war, diplomacy,
  economics, cyber, general) over a 400-feature TF-IDF vectorizer (unigrams+bigrams).
  Replaced an older pure-keyword-counting approach that had a real bug — topic-neutral
  articles silently defaulted to "war". Trained on GDELT GKG data, proxy-labeled by mapping
  GDELT's own theme taxonomy into the 5 categories (`scripts/train_topic_classifier.py`).
  One caveat baked into the code as a comment: the vectorizer was fit on GDELT's URL-slug
  text, but inference runs on real article prose — a known domain-shift, not a silent bug.
- **Threat scoring**: blends two sources —
  `threat = 0.6 × keyword_formula_score + 0.4 × ml_platform_disruption_score`
  (`ml_core/threat.py`). The keyword formula combines keyword hits, sentiment, topic, and
  entity count. The ML component calls the ML Platform's `/api/v1/risk/disruption-score`
  endpoint (the trained GDELT classifier, see below) — if that call fails, threat scoring
  falls back to keyword-only rather than erroring.

This is the only ML that runs **inline, per-article, in production** on the live news feed.

---

## 2. The five trained models (ml-platform, offline training + registry)

All live in `ml.model_versions` (`ml.dataset_catalog` tracks the ~330k-record source data),
trained via scripts in `services/ml-platform/scripts/`, tuned via `tune_and_promote.py`
(Optuna, 50 trials as of this pass, early stopping on all XGBoost loops).

### `gdelt-disruption-risk-classifier` — the one that matters live
- **Feeds**: `risk_engine.py`'s multi-dimension risk scoring (via `ml_bridge.py`) and the
  article-enrichment consumer's threat score above.
- **Target**: `escalation_flag = (quad_class == 4) OR (goldstein_scale <= -5)` — GDELT's own
  coded conflict severity, used as a proxy label (no independent ground-truth disruption
  database exists to train against).
- **Features** (160 columns): `avg_tone`, `num_mentions`, `num_sources`, `num_articles`,
  `is_root_event`, one-hot country dummies (actor1/actor2/action-geo, top-30 + OTHER), and
  (added this pass) one-hot CAMEO actor-role codes (`actor1_code`/`actor2_code`).
  **Deliberately excluded**: `event_code` (GDELT's CAMEO event-type code) — verified live
  that its root category maps 1:1 to `quad_class` (the label's own basis), so including it
  is leakage, not signal. Also excludes `quad_class`/`goldstein_scale` themselves.
- **Class imbalance**: ~19% positive rate, corrected via `scale_pos_weight` (added this pass
  — was computed and printed before but never actually used).
- **Current metric**: val ROC-AUC **0.7458** (v7, up from 0.734 after the feature/imbalance/
  tuning work above — a real, modest, honestly-measured gain).
- Training: `scripts/train_risk_classifier.py`. Tuning: `tune_and_promote.py`.

### `article-topic-classifier`
Same model that powers the live consumer's topic step (see §1). Beats a naive
majority-class baseline by +18pp (script prints the exact delta at train time).

### `procurement-option-ranker` — trained, not currently consulted live
- **Target** (`outcome_score`): a synthetic label built in `build_procurement_dataset.py` —
  starts from the exact composite formula the live optimizer uses (cost 35% / risk 30% /
  lead-time 20% / strategic 15%), then adds execution-noise that scales with sanction
  exposure, GDELT escalation, and port congestion.
- **Features** (~10 + supplier-type dummies): `cost_bbl`, `lead_time_days`,
  `reliability_score`, `on_time_delivery_pct`, `strategic_value`, `country_stability_base`,
  `sanction_count`, `gdelt_escalation_rate`, `port_congestion_index`, `brent_anchor`.
- **Data**: ~3,600 rows, real supplier/sanctions/GDELT/port data fused together.
- **Current metric**: val R² **0.246** (v5) — capped by data volume (few distinct scenario
  `run_id`s), not by tuning.
- **Now wired in live** as a genuine second opinion: `optimizer.py` builds the exact
  12-column feature vector (the 3 raw signals — `sanction_count`/`gdelt_escalation_rate`/
  `port_congestion_index` — are now persisted on `energy.supplier_intelligence` rather than
  discarded after `--enrich`) and calls ml-platform's `POST /api/v1/ml/predict` (already
  production-aware, unlike the risk-classifier's dedicated endpoint). The deterministic
  composite formula stays primary; `ml_predicted_score`/`score_divergence` are added
  alongside it, surfaced in Procurement.tsx's "ML Cross-Check" card. Divergence beyond 0.15
  is flagged as "models disagree" rather than averaged away.

### `fuel-price-forecaster`
- **Target**: next month's % price change per (market, fuel).
- **Features**: `ret_1m`, `ret_2m`, `ret_3m`, `vol_3m`, `month`, one-hot fuel-type dummies.
- **Data**: monthly commodity fuel prices (`datasets/processed/commodity-prices/`).
- **Current metric**: val R² **0.377** — beats a persistence baseline.

### `brent-shock-forecaster`
- **Target**: realized volatility (std of daily log returns) over the next 5 trading days.
- **Features**: `ret`, `ret_1`, `ret_5_sum`, `vol_5`, `vol_21`, `vol_63`, `vol_ratio`,
  `abs_ret`, `max_abs_ret_5`, `price_z_63` — all price-lag/rolling-window derived.
- **Data**: ~10,200 rows of FRED daily Brent spot (1987-present), clean (quality score 0.98).
- **Current metric**: val R² **0.223** — capped by target difficulty (forecasting volatility
  from price history alone, with no order-flow/options/news features), not by data volume.

---

## 3. `risk_engine.py` + `ml_bridge.py` — how the trained classifier gets used live

- `ML_BLEND_WEIGHT = 0.4`: `overall_score = 0.6 × formula_score + 0.4 × ml_platform_score`,
  applied only when the ML call succeeds (no silent corruption on failure).
- `MLBridge.predict_disruption_risk()` calls the ML Platform's `/api/v1/risk/disruption-score`
  endpoint; on any failure, falls back to a separate rule-based formula so risk scoring never
  hard-fails just because the ML service is down.
- `RiskPropagator` (also in `ml_bridge.py`) spreads a source entity's risk score to related
  entities via `energy.entity_relationships`, attenuated by a fixed `0.3` factor per hop —
  graph propagation, not a model.

---

## 4. What is explicitly NOT machine learning (common confusion points)

- **`corridor_risk.py`** — a documented composite index (signal pressure 35% / entity risk
  20% / instability 15% / AIS anomaly 10% / historical anomaly 20%), every weight named and
  justified in the file's own docstring as "deliberately NOT presented as a trained model."
  No `.joblib`, no model call — the newest component (`historical_anomaly`) is a real
  z-score against a genuine 45-day GDELT historical baseline, not a trained model either;
  it's a statistical anomaly score, chosen specifically *because* there's no labeled data
  for rare events like a full corridor closure to train a real classifier on (see §6).
- **`digital_twin/`** — a deterministic network-flow simulation (nodes/edges, capacity
  constraints, tick-based propagation). No ML anywhere in this module.
- **`procurement/optimizer.py` + `orchestrator.py`** — the deterministic multi-objective
  scoring formula plus Pareto-frontier computation stays primary. `procurement-option-ranker`
  **is now called** as a secondary cross-check (see §2) — its prediction is surfaced
  alongside the formula score, not used to override it.

These are legitimate, well-reasoned engineering choices — not a gap to be closed by
"more ML." Calling them "AI-driven" without qualification would overstate what they do;
the disruption classifier, the article-enrichment pipeline, and the procurement ranker's
cross-check are the parts that actually learn from data.

## 5. Why aren't `digital_twin/` and `corridor_risk.py` fully ML-driven?

Asked directly by the user; the honest answer, not "we ran out of time":

- **No historical labels exist for rare events.** A full Hormuz closure has essentially
  never happened. You can't train a supervised classifier on an event class with ~0 real
  positive examples without fabricating labels — which just launders assumptions through a
  black box instead of stating them.
- **Digital twin is simulation, not prediction.** It answers "what happens in a scenario
  that's never occurred" — that's extrapolation. ML is fundamentally an interpolation tool,
  reliable only inside its training distribution. Constraint-based flow simulation is the
  correct tool for genuine counterfactual reasoning here, not a workaround.
- **This matters for judging.** The hackathon explicitly rewards "explicit testable
  assumptions" (E3). A transparent weighted formula ("40% signal pressure + 25% entity
  risk...") is falsifiable by a judge; a neural net that outputs "77%" is not.
- **Where real data *does* support learning something, it's used** — see §2's procurement
  cross-check and §4's GDELT historical-anomaly score, both added specifically because the
  underlying data (real per-supplier signals; real multi-day GDELT timestamps) genuinely
  supports them, unlike AIS (single point-in-time snapshot, no time series to learn from)
  or digital-twin scenarios (no historical occurrences to learn from at all).

---

## 7. Known gap (flagged, not yet fixed)

`ml-platform`'s `/api/v1/risk/disruption-score` serving endpoint loads its model artifact
from a fixed path keyed by `dataset_version` (always `v1/model.joblib`), not dynamically
from whichever row is currently marked `stage='production'` in `ml.model_versions`. In
practice this means "whichever model was trained most recently" is what's actually being
served, regardless of the DB's production flag — the flag is closer to documentation than a
real serving switch today. Worth fixing if multiple model versions ever need to coexist or
be rolled back independently of retraining order.
