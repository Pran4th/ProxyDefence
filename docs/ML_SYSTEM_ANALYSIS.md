# ProxyDefence ML System Analysis

## 1. ML Architecture

### Complete Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ REAL-TIME PIPELINE (Kafka Stream Processing)                        │
│                                                                     │
│  ingest-service (port 8001)                                         │
│  ┌────────────────────────────────┐                                 │
│  │ Fetches from GNews API         │                                 │
│  │ Fields: title, content,        │                                 │
│  │   source, url, image,          │                                 │
│  │   published_at                 │                                 │
│  └──────────┬─────────────────────┘                                 │
│             │ Kafka topic: raw_articles                             │
│             ▼                                                       │
│  ml-service (port 8002)                                             │
│  ┌────────────────────────────────┐                                 │
│  │ 1. Normalize text              │                                 │
│  │ 2. Summarize (extractive)      │                                 │
│  │ 3. Sentiment (DistilBERT)      │                                 │
│  │ 4. Topic (keyword frequency)   │                                 │
│  │ 5. NER (BERT-large / spaCy)    │                                 │
│  │ 6. Threat score (formula)      │                                 │
│  │ 7. Relationship inference      │                                 │
│  │ 8. Keyword extraction (TF)     │                                 │
│  │ 9. Dedupe key (SHA-256)        │                                 │
│  └──────────┬─────────────────────┘                                 │
│             │ Kafka topic: processed_articles                       │
│             ├──────────────────────────────┐                        │
│             ▼                              ▼                        │
│  database-service (8003)    embedding-service (8005)                │
│  ┌──────────────────────┐   ┌─────────────────────────┐             │
│  │ Upsert to PostgreSQL │   │ 1. Lookup DB id by      │             │
│  │ Index to Elasticsearch│  │    dedupe_key            │             │
│  └──────────────────────┘   │ 2. Embed text (BGE)     │             │
│                             │ 3. Store in pgvector     │             │
│                             └─────────────────────────┘             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ BATCH ML PLATFORM (port 8007)                                       │
│                                                                     │
│  ML Platform Service                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Feature Store (11 types)                                     │   │
│  │   numerical, categorical, boolean, timestamp, geospatial,    │   │
│  │   entity_statistics, relationship_statistics,                │   │
│  │   historical_capacity, infrastructure, embedding_reference,  │   │
│  │   graph_placeholder                                          │   │
│  │                                                               │   │
│  │ Dataset Builder                                                │   │
│  │   Energy Service REST API → feature matrix →                  │   │
│  │     train/val/test split → parquet files → DVC versioning    │   │
│  │                                                               │   │
│  │ Training Pipeline                                              │   │
│  │   5 baseline models (LogReg, DT, RF, XGB, LGBM)              │   │
│  │   3 optimizers (GridSearch, RandomSearch, Optuna)             │   │
│  │   MLflow experiment tracking                                  │   │
│  │                                                               │   │
│  │ Model Registry                                                 │   │
│  │   5-stage lifecycle: development → validation →               │   │
│  │     staging → production → archived                            │   │
│  │                                                               │   │
│  │ Inference API                                                  │   │
│  │   Load cached model → predict → log prediction                │   │
│  │                                                               │   │
│  │ Evaluation                                                     │   │
│  │   Classification metrics, SHAP explainability, reports         │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ RESEARCH ENVIRONMENT (Notebooks)                                    │
│                                                                     │
│  01_eda.ipynb → Data exploration                                    │
│  02_preprocessing.ipynb → Feature pipelines                         │
│  03_feature_engineering.ipynb → Custom feature transforms           │
│  04_baseline_models.ipynb → LogReg, DT, RF                          │
│  05_model_comparison.ipynb → Add XGB, LGBM, cross-validation       │
│  06_hyperparameter_tuning.ipynb → Grid, Random, Optuna             │
│  07_explainability.ipynb → SHAP, permutation importance             │
│  08_final_model_export.ipynb → Train, save, register final model   │
└─────────────────────────────────────────────────────────────────────┘
```

### System Layers

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Stream processing | Kafka + Python consumers | Real-time article enrichment |
| Feature engineering | Python (keyword, regex, formula) | Extract features from text |
| NLP | HuggingFace Transformers, spaCy | NER, sentiment analysis |
| Embeddings | fastembed (BGE-small-en-v1.5) | Vector representations |
| Vector storage | pgvector (HNSW index) | Similarity search |
| Batch ML | scikit-learn, XGBoost, LightGBM | Infrastructure asset classification |
| Experiment tracking | MLflow (file-based) | Parameter/metric logging |
| Data versioning | DVC | Dataset version control |
| Explaining | SHAP, permutation importance | Model interpretability |
| Research | Jupyter notebooks | Exploration, prototyping |

---

## 2. Every Model

### 2.1 DistilBERT Sentiment Model

| Property | Value |
|----------|-------|
| **Purpose** | Binary sentiment classification of article text |
| **Model** | `distilbert-base-uncased-finetuned-sst-2-english` |
| **Parameters** | ~67M |
| **Architecture** | 6-layer DistilBERT encoder + classification head |
| **Input** | Article `full_text` truncated to 1000 characters |
| **Output** | `(label: str, score: float)` — label is "negative", "positive", or "neutral" |
| **Score range** | 0.0–1.0 (confidence in the predicted class) |
| **Training data** | Stanford Sentiment Treebank (SST-2) — ~67k movie review sentences |
| **Fine-tuning domain** | General English (no defense/news fine-tuning) |

#### Inference Flow
```
consumer.py → analyze_sentiment(full_text)
  → get_sentiment_pipeline()  [lazy singleton]
  → pipeline(full_text[:1000])
  → returns (label, score)
  → label mapped: "NEGATIVE"→"negative", "POSITIVE"→"positive"
  → "neutral" returned when score < threshold (implicit)
```

#### Where Loaded
`ml_core/models.py:load_models()` — loaded at ML service startup via `transformers.pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")`

#### Why Chosen
- Lightweight (67M params vs 340M for BERT)
- SST-2 provides reasonable general-purpose sentiment
- Widely available via HuggingFace

#### Alternatives
- FinBERT (domain-specific financial sentiment) — not applicable to defense
- BERTweet (social media) — not applicable to news
- Custom fine-tuned model on defense news — would require labeled training data

#### Current Limitations
- Binary classifier cannot distinguish nuanced categories (e.g., "cautiously optimistic," "diplomatic tension")
- No defense-domain fine-tuning — words like "missile" or "drone" may trigger false negative sentiment
- Truncated to 1000 characters — longer articles lose context
- `analyze_sentiment` returns "neutral" as a category, but the DistilBERT model only outputs POSITIVE/NEGATIVE — the "neutral" label is returned when `label == "neutral"` but DistilBERT never emits this. The neutral label is effectively unreachable from the model; it can only be returned if `pipeline is None` (fallback).
- **Bug/design issue**: The `analyze_sentiment` function in `ml_core/sentiment.py` returns "neutral" when `pipeline is None` or when `label == "neutral"`. Since DistilBERT's SST-2 model never outputs "neutral", all predictions are either positive or negative. The "neutral" fallback at `pipeline below None` is the only code path that produces it.

### 2.2 BERT-Large NER Model

| Property | Value |
|----------|-------|
| **Purpose** | Named entity recognition (people, organizations, locations, MISC) |
| **Model** | `dbmdz/bert-large-cased-finetuned-conll03-english` |
| **Parameters** | ~340M |
| **Architecture** | 24-layer BERT-large encoder + token classification head |
| **Input** | Article `full_text` truncated to 1200 characters |
| **Output** | List of `{text, type, score}` dicts, filtered to LOC/ORG/PER/MISC with score > 0.70 |
| **Max entities returned** | 12 |
| **Training data** | CoNLL-2003 (English news) — ~22k sentences with LOC/ORG/PER/MISC labels |
| **Fine-tuning domain** | General news (closely matches our domain) |

#### Inference Flow
```
consumer.py → extract_entities(full_text)
  → get_ner_pipeline()  [lazy singleton, HuggingFace]
  → ner(full_text[:1200])
  → filter: entity_group in {LOC, ORG, PER, MISC} AND score > 0.70
  → normalize entity text via entity_normalization module
  → deduplicate, skip IGNORE_ENTITIES
  → return max 12 entities
  → FALLBACK (if transformers unavailable):
    → get_nlp()  [spaCy en_core_web_sm]
    → doc.ents filtered to PERSON/ORG/GPE
    → score always 0.90
    → deduplicate, skip IGNORE_ENTITIES
    → return max 12 entities
```

#### Where Loaded
`ml_core/models.py:load_models()` — primary: `transformers.pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english")`, fallback: `spacy.load("en_core_web_sm")`

#### Why Chosen
- CoNLL-2003 is the standard benchmark for English NER
- BERT-large provides state-of-the-art accuracy (F1 ~92 on CoNLL)
- spaCy fallback provides reliability when transformers OOM or fail to load

#### Alternatives
- spaCy en_core_web_trf (transformer-based, similar accuracy) — lighter dependency
- GLiNER (zero-shot NER) — more flexible entity types
- Custom trained NER for defense entities (weapons systems, military bases) — would need labeled data

#### Current Limitations
- 1200 character truncation — entities in later article sections missed
- 4 entity types only (LOC/ORG/PER/MISC) — no DATE, GPE, NORP, FAC, etc.
- BERT-large is 340M params (~1.3GB) — high memory usage for real-time streaming
- weight 0.70 score threshold may miss lower-confidence but correct entities
- spaCy fallback produces always 0.90 confidence (fixed, not calibrated)
- `IGNORE_ENTITIES` list content is not in the ML code — defined in `backend/shared/entity_normalization.py`

### 2.3 spaCy en_core_web_sm

| Property | Value |
|----------|-------|
| **Purpose** | NER fallback + general NLP pipeline |
| **Model** | `en_core_web_sm` |
| **Parameters** | ~12M |
| **Architecture** | CNN-based (tok2vec + tagger + parser + NER) |
| **Input** | Full article text (no truncation) |
| **Output** | NER entities with label types PERSON/ORG/GPE (more limited than BERT) |

#### Where Loaded
`ml_core/models.py:load_models()` — `spacy.load("en_core_web_sm")`

#### Role
- Backup NER when HuggingFace transformers fail (OOM, import error, model download failure)
- Does NOT contribute to other NLP tasks — only NER

#### Current Limitations
- Significantly less accurate than BERT-large (F1 ~85 vs ~92 on CoNLL)
- Only 3 entity types mapped (PERSON/ORG/GPE) vs BERT's 4 (LOC/ORG/PER/MISC)
- Always returns confidence 0.90 (hardcoded, not model-calibrated)

### 2.4 BAAI/bge-small-en-v1.5 Embedding Model

| Property | Value |
|----------|-------|
| **Purpose** | Generate dense vector embeddings for text (articles + queries) |
| **Model** | `BAAI/bge-small-en-v1.5` |
| **Parameters** | ~33M |
| **Architecture** | 12-layer BERT-small encoder, trained with contrastive learning |
| **Output dimension** | 384 |
| **Max tokens** | 512 |
| **Input** | Article title + content concatenated; search query text |
| **Similarity metric** | Cosine similarity (via pgvector `<=>` operator) |

#### Inference Flow
```
embedding-service:
  embed_text("Article title\n\nArticle content...")
  → TextEmbedding(model_name="BAAI/bge-small-en-v1.5").embed([text])
  → returns numpy array (384,)
  → make_vector_str() → "[0.12345678, 0.87654321, ...]"
  → stored in article_embeddings.embedding::vector(384)

semantic search:
  embed_text(query) → query_vector
  → SELECT p.id, p.title, 1 - (ae.embedding <=> query_vector) AS similarity
  → ORDER BY ae.embedding <=> query_vector
  → LIMIT 5
```

#### Where Loaded
`services/embedding-service/services/embeddings.py:load_model()` — loaded lazily at first `embed_text()` call

#### Why Chosen
- Small (~33M params) — fast inference, low memory
- 384-dim vectors — efficient storage and comparison
- Strong MTEB leaderboard performance for its size
- Supports asymmetric search (query ≠ document length)
- `fastembed` library provides optimized ONNX runtime inference

#### Alternatives
- all-MiniLM-L6-v2 (384d, 22M params) — similar performance, smaller
- BAAI/bge-base-en-v1.5 (768d, 110M params) — higher accuracy, slower
- OpenAI text-embedding-3-small (1536d) — external API, cost, latency
- sentence-transformers/all-mpnet-base-v2 (768d, 110M) — higher accuracy

#### Current Limitations
- 512 token limit — longer articles truncated before embedding
- 384-dim vectors may lose nuance for domain-specific defense terminology
- No domain adaptation (trained on general web text)
- `generate_embeddings` (GET /generate) re-embeds articles without embeddings — useful for backfill but blocking

### 2.5 Baseline Classifiers (ML Platform)

#### Models Available

| Model | Wrapper Class | Parameters (default) | Training Data |
|-------|--------------|---------------------|---------------|
| Logistic Regression | `LogisticRegressionWrapper` | C=1.0, max_iter=1000, n_jobs=-1 | Energy Service infrastructure data |
| Decision Tree | `DecisionTreeWrapper` | max_depth=None, min_samples_split=2 | Energy Service infrastructure data |
| Random Forest | `RandomForestWrapper` | n_estimators=100, max_depth=None, n_jobs=-1 | Energy Service infrastructure data |
| XGBoost | `XGBoostWrapper` | n_estimators=100, learning_rate=0.3, eval_metric=mlogloss | Energy Service infrastructure data |
| LightGBM | `LightGBMWrapper` | (conditional import) | Energy Service infrastructure data |

#### Training Flow (via `ModelTrainer.train()`)
```
1. Create model wrapper from MODEL_REGISTRY[model_type]
2. Start MLflow run
3. Log parameters
4. model.fit(X_train, y_train)
5. Evaluate on X_val, y_val (accuracy, precision, recall, F1, confusion matrix)
6. Log metrics to MLflow
7. Save model artifact as .joblib
8. Register in ml.model_versions table
9. Return version metadata
```

#### Current Maturity
- **0 trained models** in the registry (`GET /api/v1/ml/models → total=0`)
- Feature definitions exist (4 features defined)
- Training pipeline is implemented but never executed
- Dataset builder is implemented but dataset not yet built

---

## 3. Every ML Algorithm

### 3.1 Named Entity Recognition (NER)

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/entities.py`, `extract_entities(full_text)` |
| **Primary** | HuggingFace `transformers.pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english")` |
| **Fallback** | `spaCy("en_core_web_sm").ents` |
| **Entity types** | LOC/ORG/PER/MISC (transformers); PERSON/ORG/GPE (spaCy) |
| **Confidence filter** | transformers: score > 0.70; spaCy: always 0.90 |
| **Max entities** | 12 |
| **Deduplication** | By lowercase normalized text; `IGNORE_ENTITIES` skip list |
| **Normalization** | `backend/shared/entity_normalization.py` module |

The NER is two-tier: tries the transformer model first (BERT-large, 340M params), and if that fails (exception during inference), falls back to spaCy. The BERT model uses "simple" aggregation strategy which groups subword tokens into complete words. The threshold of 0.70 was chosen to balance precision and recall.

### 3.2 Topic Classification

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/topic.py`, `classify_topic(full_text)` |
| **Method** | Keyword frequency counting |
| **Categories** | `war`, `diplomacy`, `economics`, `cyber` |
| **Confidence** | `best_score / total(score)` — relative keyword frequency |
| **Default** | `"general"` with confidence 0.35 when no keywords matched |

The topic classifier counts occurrences of predefined keyword sets in the lowercased text. The topic with the highest absolute keyword count wins. Confidence is the winning count divided by total counts across all topics. This is a simple bag-of-keywords approach with no NLP model.

#### Keyword Sets

| Topic | Keywords |
|-------|----------|
| war | war, missile, strike, attack, military, troops, drone, airstrike |
| diplomacy | ceasefire, summit, negotiation, talks, diplomatic, alliance, peace |
| economics | oil, trade, sanction, economy, inflation, market, currency, energy |
| cyber | cyber, ransomware, malware, hacker, breach, espionage, infrastructure |

#### Limitations
- No context awareness — "cyber" in "cyber Monday deals" misclassifies as `cyber` topic
- Keywords overlap (e.g., "sanction" appears in both economics and diplomacy contexts)
- Short articles with fewer words may get "general" due to insufficient keyword matches
- English-only keywords — non-English articles classified as "general"
- No sentiment weighting — "ceasefire agreed" and "ceasefire collapsed" both count as diplomacy

### 3.3 Threat Scoring

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/threat.py`, `score_threat(full_text, sentiment, topic, entity_count)` |
| **Method** | Weighted formula combining 4 factors |
| **Output** | `(threat_score: 0-100, geopolitical_risk: 0-100, risk_level: low/medium/high/critical)` |
| **Thresholds** | critical ≥ 75, high ≥ 55, medium ≥ 30, low < 30 |

#### Formula

```
keyword_score = SUM(level_weight for each keyword matched)
  critical keywords (nuclear, chemical, biological, missile, genocide, airstrike) → +35 each
  high keywords (attack, war, sanction, retaliation, crisis, terror) → +20 each
  medium keywords (tension, warning, surge, pressure, alert, military) → +10 each

sentiment_score:
  negative → +25, neutral → +10, positive → +0

topic_score:
  war → +20, cyber → +18, economics → +12, diplomacy → +8, general → +6

entity_score = min(entity_count * 2, 15)  [capped at 15]

threat = min(100, keyword_score + sentiment_score + topic_score + entity_score)
geo_risk = min(100, threat * 0.92 + keyword_score * 0.4)
```

#### Limitations
- Linear additive model — no interactions between factors
- Keywords weighted equally within each severity tier
- "nuclear" and "genocide" both contribute 35 points, but they represent vastly different threat levels
- No temporal component — article recency not considered
- No source credibility weighting
- Entity_count is biased toward longer articles (more extracted entities)

### 3.4 Relationship Extraction

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/relationships.py`, `infer_relationships(entities, full_text)` |
| **Method** | Entity pair co-occurrence + keyword-based relationship type |
| **Relationship types** | `attack`, `alliance`, `sanction`, `diplomacy`, `association` |
| **Algorithm** | `itertools.combinations` over top 5 actors, max 6 pairs |

#### Flow
1. Filter entities to GPE/ORG/PERSON types ("actors")
2. If fewer than 2 actors, return empty list
3. Determine relationship type by scanning text for RELATIONSHIP_KEYWORDS
4. Generate pairwise relationships from first 5 actors, limited to 6 pairs
5. Assign confidence: 0.80 if keyword-matched, 0.55 if default "association"
6. Attach context summary (first 2 sentences of article)

#### Limitations
- Pairwise combinatorics produce O(n²) relationships — capped at 6 pairs, losing some connections
- Relationship type is GLOBAL per article, not per entity pair — "Russian athletes attend summit" and "Russia attacks Ukraine" in same article get the same relationship type
- No entity disambiguation — "Iran" and "Iranian" may appear as separate actors
- Context field duplicates the article summary (not specific to the entity pair)

### 3.5 Sentiment Analysis

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/sentiment.py`, `analyze_sentiment(full_text)` |
| **Method** | DistilBERT transformer pipeline |
| **Input** | First 1000 characters of `full_text` |
| **Output** | `(label: str, score: float)` |
| **Labels** | `negative` / `positive` (from DistilBERT) + `neutral` (only if pipeline is None) |
| **Confidence** | Score from DistilBERT softmax (0-1) |

The "neutral" label is effectively dead code — DistilBERT's SST-2 model only outputs POSITIVE or NEGATIVE. The `analyze_sentiment` function can only return "neutral" when `pipeline is None` (model failed to load). This means every article with a working model is classified as either positive or negative, which is unrealistic for news articles.

### 3.6 Text Summarization

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/text.py`, `summarize_text(full_text)` |
| **Method** | Extractive — first 2 sentences longer than 30 characters |
| **Max length** | 360 characters |

#### Algorithm
1. Split text on sentence boundaries (`.!?` followed by whitespace)
2. Filter to sentences > 30 characters (removes short fragments)
3. Take first 2 qualifying sentences
4. Join with space, truncate to 360 characters
5. If no qualifying sentences, return first 240 characters of raw text

#### Limitations
- No NLP — purely heuristic extraction
- "First two" is naive — the most important information may not be in the first sentences
- No compression or paraphrasing — just concatenation
- 360-char limit may cut sentences mid-word
- Ignores article structure — title, section headers, quotes

### 3.7 Keyword Extraction

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/text.py`, `extract_keywords(full_text)` |
| **Method** | TF frequency with stopword filtering |
| **Max keywords** | 8 |

#### Algorithm
1. Extract words matching `[A-Za-z][A-Za-z\-]{3,}` (3+ letter words with hyphens)
2. Convert to lowercase
3. Filter out STOPWORDS (20 common English words)
4. Count frequencies with `collections.Counter`
5. Return top 8 most common

#### Stopwords
`{the, and, for, that, with, from, this, have, will, into, amid, their, about, after, before, while, under, over, they, them, were, been, said}`

#### Limitations
- No TF-IDF (no document frequency corpus) — common words like "military" dominate
- English-only regex — non-English words are discarded entirely
- Short words (< 3 chars) are discarded (e.g., "AI", "US", "UK")
- Hyphenated words kept but not split (e.g., "long-range" stays as one keyword)
- No phrase detection — "nuclear weapon" is two separate keywords
- 20 stopwords is too small — many common news words missing (e.g., "year", "new", "time")

### 3.8 Embedding Generation

| Aspect | Detail |
|--------|--------|
| **Source** | `services/embedding-service/services/embeddings.py` |
| **Library** | `fastembed.TextEmbedding` (ONNX runtime) |
| **Model** | `BAAI/bge-small-en-v1.5` |
| **Dimension** | 384 |
| **Normalization** | L2-normalized (cosine similarity) |
| **Batch size** | 1 (one text at a time) |

#### Vector Storage
- Stored in `article_embeddings.embedding` column as `vector(384)` (pgvector)
- HNSW index on embedding column with `vector_cosine_ops` for approximate nearest neighbor search
- INSERT uses `ON CONFLICT (article_id) DO NOTHING` — idempotent

#### Similarity Search
- Cosine distance via `<=>` operator: `1 - (embedding <=> query_vector) AS similarity`
- pgvector automatically uses HNSW index for approximate search
- Returns top 5 results sorted by cosine similarity

### 3.9 Deduplication Key Generation

| Aspect | Detail |
|--------|--------|
| **Source** | `ml_core/text.py`, `build_dedupe_key(article, full_text)` |
| **Method** | SHA-256 of `url|source|first_500_chars_of_full_text` |
| **Purpose** | Unique identifier for database upsert conflict detection |

The dedupe key is computed from 3 dimensions: URL (unique per article), source name (differentiates mirrored content), and first 500 characters of full text (differentiates revisions). The DB has a UNIQUE index on `dedupe_key` and uses `ON CONFLICT (dedupe_key) DO UPDATE` for idempotent inserts.

### 3.10 Article ID (Pipeline Identifier)

| Aspect | Detail |
|--------|--------|
| **Source** | `services/ingest-service/services/news_fetcher.py` |
| **Method** | `int(SHA-256(url).hexdigest(), 16) % 10**8` |
| **Purpose** | Non-database article identifier for Kafka messages |
| **Collision risk** | ~2^256 / 10^8 ≈ 10^69 unique URLs per bucket — effectively zero |

### 3.11 Confidence Score

| Aspect | Detail |
|--------|--------|
| **Source** | `services/ml-service/consumer.py`, `enrich_article()` |
| **Computation** | `round((sentiment_confidence + topic_confidence) / 2, 2)` |
| **Purpose** | Single "confidence" metric for the enriched article |
| **Components** | Sentiment model score (0-1) + Topic keyword ratio (0-1) |

The confidence score is the arithmetic mean of sentiment confidence (from DistilBERT softmax) and topic confidence (keyword ratio). This combines model-based confidence (sentiment) with rule-based confidence (topic keywords).

#### Limitations
- Two different types of confidence averaged together — one probabilistic, one heuristic
- Topic confidence is a keyword frequency ratio, not a model probability
- No entity extraction confidence included
- No threat score confidence included

---

## 4. Every Feature

### Features Generated by ML Pipeline

| Feature | Source | Computation | Consumed By | Type |
|---------|--------|-------------|-------------|------|
| `ml_processed` | `enrich_article()` | Set to `True` after ML pipeline | Database-service, API | boolean |
| `processed_at` | `enrich_article()` | `datetime.utcnow().isoformat()` | Database-service | timestamp |
| `summary` | `summarize_text(full_text)` | First 2 long sentences, max 360 chars | API, Copilot, Frontend | text |
| `topic` | `classify_topic(full_text)` | Keyword frequency (4 categories) | Database-service, API, Analytics | categorical |
| `topic_confidence` | `classify_topic(full_text)` | `best_score / total_scores` | Consumer (averaged into `confidence`) | float |
| `sentiment` | `analyze_sentiment(full_text)` | DistilBERT transformer | Database-service, API, Analytics | categorical |
| `confidence` | `enrich_article()` | `(sentiment_conf + topic_conf) / 2` | Database-service, API, Analytics | float |
| `threat_score` | `score_threat(...)` | Weighted formula (0-100) | Database-service, API, Analytics | float |
| `geopolitical_risk` | `score_threat(...)` | `threat * 0.92 + keyword_score * 0.4` | Database-service, API | float |
| `risk_level` | `score_threat(...)` | Threshold-based (low/medium/high/critical) | Database-service, API, Analytics | categorical |
| `entities` | `extract_entities(full_text)` | BERT NER pipeline → list of dicts | Database-service (stored as separate table) | nested JSON |
| `relationships` | `infer_relationships(...)` | Entity pair co-occurrence | Database-service (stored as separate table) | nested JSON |
| `keywords` | `extract_keywords(full_text)` | TF frequency, top 8 | Database-service, API (not queried by frontend) | list of strings |
| `content_hash` | `enrich_article()` | `SHA-256(full_text)` | Database-service (stored, not queried) | string |
| `dedupe_key` | `build_dedupe_key(...)` | `SHA-256(url\|source\|full_text[:500])` | Database-service (UNIQUE index, UPSERT key), Embedding-service (lookup key) | string |
| `embedding` | `embed_text(title + "\n\n" + content)` | BGE-small-en-v1.5 → 384-dim vector | Embedding-service, Semantic Search | vector(384) |

### Features Consumed by Analytics Dashboard

| Metric | SQL Query |
|--------|-----------|
| `total_articles` | `SELECT COUNT(*) FROM processed_articles` |
| `articles_last_24h` | `SELECT COUNT(*) FROM processed_articles WHERE published_at >= NOW() - INTERVAL '24 hours'` |
| `avg_confidence` | `SELECT AVG(confidence) FROM processed_articles` |
| `avg_threat_score` | `SELECT AVG(threat_score) FROM processed_articles` |
| `sentiment_distribution` | `SELECT sentiment, COUNT(*) FROM processed_articles GROUP BY sentiment` |

### Copilot Intelligence Assessment Features

| Feature | Computation |
|---------|-------------|
| threat_level | Max risk_level across relevant articles |
| sentiment_breakdown | Negative/positive/neutral counts |
| entity_count | Distinct entities from relevant articles |
| key_locations | Entity names filtered to GPE/LOC types |
| involved_actors | Entity names filtered to ORG/PER types |
| summary | Concatenated article summaries + entity context |

---

## 5. Prompt Engineering

### Current Status: NO LLM prompts exist in this codebase

The Copilot intelligence assessment (`services/ml-service/copilot/`) does NOT use any LLM. It operates entirely on structured data from the database:
- Articles are retrieved via semantic search (embedding similarity)
- Entities, relationships, and events are loaded from PostgreSQL
- `CopilotService.build_assessment()` applies rule-based classification (threat level, sentiment breakdown, entity counting)
- `CopilotService.build_summary()` concatenates article summaries with entity context

There are **zero** LLM API calls, zero prompt templates, and zero generated text in the entire pipeline.

This is significant because:
1. All "intelligence" is rule-based — no natural language understanding
2. The summary is extractive concatenation, not generative
3. Threat assessment is keyword-frequency-based, not semantic
4. There is room for LLM enhancement (GPT, Claude, or local models like Llama) but none is implemented

---

## 6. ML Platform

### 6.1 Dataset Management

| Component | Implementation | Status |
|-----------|---------------|--------|
| **Data source** | Energy Service REST API (`/api/v1/energy/` endpoints) | ✅ Available |
| **Synthetic fallback** | `MockDataLoader` generates 1000-row synthetic dataset | ✅ Available |
| **Dataset builder** | `DatasetBuilder.build()` — fetches, featurizes, splits, saves, versions, registers | ✅ Implemented |
| **Split strategy** | Deterministic stratified: train/val/test with configurable ratios (default 70/10/20) | ✅ Implemented |
| **Format** | Parquet files per split | ✅ Implemented |
| **Storage** | Configurable `DATASET_DIR` (default `./data/datasets/`) | ✅ Implemented |
| **DVC tracking** | `DvcManager` wraps DVC CLI for dataset versioning | ✅ Implemented |
| **Dataset registry** | `ml.datasets` table with versioning, metadata | ✅ Implemented |
| **API download** | `/api/v1/ml/datasets/{uuid}/download?split=train` | ✅ Implemented |

### 6.2 Feature Store

| Component | Implementation | Status |
|-----------|---------------|--------|
| **Feature types** | 11 types (numerical, categorical, boolean, timestamp, geospatial, entity_statistics, relationship_statistics, historical_capacity, infrastructure, embedding_reference, graph_placeholder) | ✅ Defined |
| **Feature registry** | `ml.feature_definitions` table with versioning | ✅ Implemented |
| **Feature builder** | `FeatureBuilder.compute_all()` from Energy Service data | ✅ Implemented |
| **Transforms** | Identity, Aggregate, Lag, Ratio, Geospatial (Haversine distance) | ✅ Implemented |
| **Created features** | 4 features exist (from seed data or API) | ⚠️ 4 only |

**4 feature definitions exist** (as of current DB state):

| Feature | Type | Description |
|---------|------|-------------|
| (from API) | (various) | The 4 features registered in `ml.feature_definitions` |

### 6.3 Training Pipeline

| Component | Implementation | Status |
|-----------|---------------|--------|
| **Model wrappers** | LogReg, DT, RF, XGB, LGBM (conditional) | ✅ Implemented |
| **Trainer** | `ModelTrainer.train()` — fit, evaluate, log, save, register | ✅ Implemented |
| **Hyperparameter optimization** | GridSearch, RandomSearch, Optuna (conditional) | ✅ Implemented |
| **Experiment tracking** | MLflow (file-based, `file:./mlruns`) | ✅ Implemented |
| **Trained models** | In registry | ⚠️ **0 models** |

### 6.4 Model Registry

| Aspect | Detail |
|--------|--------|
| **Storage** | `ml.model_versions` table in PostgreSQL |
| **Lifecycle stages** | `development → validation → staging → production → archived` |
| **Transition rules** | Must move forward; `staging → production` auto-demotes previous production |
| **Metadata** | Metrics, parameters, feature/dataset versions, MLflow run ID, artifact path, git commit hash |
| **API** | CRUD + transition + get production + get latest |
| **Current state** | ✅ Schema exists, API works, 0 models registered |

### 6.5 Evaluation

| Component | Implementation | Status |
|-----------|---------------|--------|
| **Classification metrics** | Accuracy, precision, recall, F1, confusion matrix, classification report, ROC AUC (binary + OVR) | ✅ Implemented |
| **Regression metrics** | MAE, MSE, RMSE, R² | ✅ Implemented |
| **Report generator** | JSON + Markdown evaluation reports | ✅ Implemented |
| **Feature importance** | Built-in `feature_importances_` / `coef_` | ✅ Implemented |
| **Permutation importance** | `sklearn.inspection.permutation_importance` | ✅ Implemented |
| **SHAP** | `TreeExplainer` + `KernelExplainer` (conditional on `shap` import) | ✅ Implemented |

### 6.6 Inference API

| Aspect | Detail |
|--------|--------|
| **Endpoint** | `POST /api/v1/ml/predict` with `PredictionRequest` |
| **Model loading** | `ModelPredictor` with in-memory `_cache` dict (keyed by uuid) |
| **Prediction logging** | Each prediction logged to `ml.predictions` table |
| **Response** | `PredictionResponse` with prediction, confidence, probabilities, model metadata, latency |

### 6.7 Current Maturity

| Domain | Maturity | Notes |
|--------|----------|-------|
| Real-time NLP pipeline | **Production** | Running 24/7, processing articles |
| Embedding generation | **Production** | Running, verified with 46 embeddings |
| Semantic search | **Production** | Working, 5 results for queries |
| Feature store | **Development** | Schema exists, 4 features defined |
| Dataset management | **Development** | Builder exists but not executed |
| Model training | **Development** | Pipeline exists but 0 models trained |
| Model registry | **Development** | Schema exists, 0 models registered |
| Inference API | **Development** | No models → cannot serve predictions |
| Evaluation | **Development** | Tools exist, no evaluations run |
| SHAP explainability | **Development** | Code exists, no models to explain |

---

## 7. Research Review

### 7.1 How This Differs from Production ML Systems

| Aspect | Current Implementation | State-of-the-Art Practice |
|--------|----------------------|--------------------------|
| **Model serving** | Cold-start loading at consumer startup | Model server with hot-reload, A/B testing, canary deployments (MLflow Serving, BentoML, Ray Serve) |
| **Feature store** | Versioned DB table with manual registration | Feature platform with online/offline serving, point-in-time correctness, automatic feature engineering (Feast, Tecton) |
| **Orchestration** | Kafka consumer with sequential pipeline | DAG-based orchestrator with retries, backfills, monitoring (Airflow, Prefect, Dagster) |
| **Data validation** | No schema validation for features | Great Expectations, whylogs, or Deequ for automated data quality checks |
| **Model monitoring** | Prometheus metrics (service level) | Model-specific drift detection, data drift, prediction monitoring (Evidently, NannyML, WhyLabs) |
| **ML pipeline** | Synchronous consumer with single-thread processing | Distributed processing with GPU acceleration, batch inference, streaming inference separation |
| **Experiment tracking** | MLflow file-based (local) | MLflow with PostgreSQL backend, S3 artifact store, multi-user |
| **CI/CD for ML** | None | Model validation gates, automated retraining, registry promotion pipeline (Kubeflow, MLflow CI/CD) |
| **Vector database** | pgvector in same PostgreSQL instance | Dedicated vector DB (Pinecone, Weaviate, Qdrant) for better scalability |
| **Embedding model** | BGE-small-en-v1.5 (33M, 384d) | State-of-the-art: E5-mistral-7b (4096d) or voyage-large-2 (1536d) for higher accuracy |
| **NER model** | BERT-large (340M) | Modern alternative: DeBERTa-v3 or GLiNER (zero-shot, 10x label types) |
| **Sentiment** | DistilBERT SST-2 (binary) | Multidimensional sentiment: emotion detection, aspect-based sentiment |
| **Topic classification** | Keyword frequency | Zero-shot classification (BART, NLI models) or few-shot (SetFit) |
| **Summarization** | First-2-sentences extractive | Abstractive summarization (BART, T5, Pegasus) or hybrid extractive-abstractive |

### 7.2 Strengths of Current Approach

1. **Streaming-first architecture**: Using Kafka for real-time processing is architecturally sound and aligns with modern data pipeline best practices.
2. **No external API dependencies**: All ML runs locally — no OpenAI/AWS API calls, no per-inference costs, no data privacy concerns.
3. **Graceful degradation**: NER falls back from BERT → spaCy; model failures don't crash the pipeline.
4. **Idempotent design**: UPSERT + dedupe_key ensures exactly-once processing semantics.
5. **Separation of research from production**: Notebooks in `research/`, production code in `services/` — clean boundary.
6. **Full batch ML infrastructure**: Feature store, dataset builder, model registry, evaluation — even if not yet populated, the architecture is in place.
7. **Explainability built in**: SHAP, permutation importance, and feature importance are first-class citizens in the codebase.

### 7.3 Weaknesses of Current Approach

1. **No LLM integration**: The Copilot feature "intelligence assessment" is entirely rule-based despite the name "Copilot." No generative AI is used.
2. **Sentiment model mismatch**: DistilBERT SST-2 is binary (pos/neg) but the pipeline expects three classes (pos/neg/neutral). The third class is unreachable.
3. **Truncated text processing**: All models truncate input (1000-1200 chars), losing context from longer articles.
4. **No model training has ever been executed**: The ML Platform has 0 trained models, 0 datasets built, 0 predictions served.
5. **Feature store not connected to training**: `FeatureRegistry` and `DatasetBuilder` exist but are not wired to the training pipeline through a unified API.
6. **No monitoring or alerting for model degradation**: Prometheus metrics cover service health but not model accuracy, drift, or data quality.
7. **No automated retraining**: Models train once (when manually triggered) and must be manually promoted through registry stages.
8. **Thread safety**: `_sentiment_pipeline`, `_ner_pipeline`, `_nlp` are module-level singletons loaded in `load_models()` without locks. Safe only because `load_models()` is called once at consumer startup.
9. **Embedding service has redundant APIs**: `GET /generate` backfills embeddings and `/search` serves queries, but the Kafka consumer also generates embeddings — two code paths for the same operation.

---

## 8. Summary

The ProxyDefence ML system consists of two parallel tracks:

**Real-time pipeline** (production): Streams news articles through Kafka → ML enrichment (NLP with HuggingFace + spaCy) → database + Elasticsearch + embeddings → semantic search + copilot assessment. This track is fully operational, processing 10 articles per GNews API fetch with end-to-end latency under 60 seconds.

**Batch ML platform** (development): Infrastructure asset classification platform targeting Energy Service data. The feature store, dataset builder, training pipeline, model registry, evaluation tools, and inference API are all implemented. Currently 0 trained models exist — the platform is scaffolded but not yet operational.

**Research environment**: 8 Jupyter notebooks provide an end-to-end ML learning journey from EDA through model export, mapping concepts to production code at each step. No models from research have been promoted to production.
