# ProxyDefence Pipeline Validation

## Complete Pipeline Diagram

```
GNews API
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ ingest-service (8001)                                       │
│ - Fetches from GNews API (conflict/keyword news)           │
│ - Generates synthetic `id` = SHA-256(url) % 10^8          │
│ - Publishes to raw_articles Kafka topic                    │
└─────────────────────────────────────────────────────────────┘
    │
    │  Kafka topic: raw_articles
    │  Consumer group: ml-service-group
    ▼
┌─────────────────────────────────────────────────────────────┐
│ ml-service (8002)                                           │
│ - Consumes from raw_articles                                │
│ - Runs NLP pipeline:                                        │
│   • Normalize text, build full_text                        │
│   • Summarize (first 2 sentences, max 360 chars)           │
│   • Sentiment analysis (keyword-based: neg/pos/neutral)    │
│   • Topic classification (war/diplomacy/politics/...)      │
│   • Entity extraction (BERT NER model via spaCy)           │
│   • Threat scoring (keyword-based, 0-100)                  │
│   • Relationship inference (co-occurrence based)           │
│   • Keyword extraction (TF frequency)                      │
│   • Content hash (SHA-256) and dedupe_key                  │
│ - Publishes enriched article to processed_articles topic   │
└─────────────────────────────────────────────────────────────┘
    │
    │  Kafka topic: processed_articles
    │  Consumer group: db-service-group
    ├──────────────────────────────────────────────┐
    ▼                                              ▼
┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│ database-service (8003)          │  │ embedding-service (8005)         │
│ - Upserts into PostgreSQL        │  │ - Generates embeddings (384-dim) │
│ • processed_articles (core)      │  │ - Looks up DB id by dedupe_key   │
│ • extracted_entities (NER)       │  │ - Inserts into article_embeddings│
│ • article_sentiments             │  └──────────────────────────────────┘
│ • relationships (co-occurrence)  │
│ • events (intelligence)          │
│ - Indexes into Elasticsearch     │
└──────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ modular-api (8000)                                          │
│ - REST API backed by PostgreSQL + Elasticsearch             │
│ • /articles - CRUD operations                              │
│ • /analytics/summary - aggregate statistics                 │
│ • /search - Elasticsearch full-text search                  │
│ • /semantic-search - embedding-based vector search          │
│ • /copilot/query - multi-stage intelligence assessment      │
│ • /entities, /events, /graph - entity graph                 │
│ • /auth - JWT authentication                               │
│ • /watchlists, /cases, /alerts, /reports - SOC workflows   │
└─────────────────────────────────────────────────────────────┘

Independent services (standalone catalogs):
  energy-service (8006) → energy schema (31 locations, 22 ports, ...)
  ml-platform (8007)    → ml schema (4 feature definitions, 0 trained models)
```

## Kafka Topic Flow

### raw_articles (partition 0)

| Producer | Consumer Group | Messages |
|----------|---------------|----------|
| ingest-service | ml-service-group | 140 total |

Message schema:
```json
{
    "id": 63455923,              // SHA-256(url) % 10^8 — pipeline identifier
    "title": "...",              // Article title from GNews
    "content": "...",            // Article content or description
    "source": "Source Name",     // GNews source.name
    "published_at": "2026-...",  // ISO datetime
    "url": "https://...",        // Original article URL
    "image": "https://..."       // Image URL
}
```

### processed_articles (partition 0)

| Producer | Consumer Groups | Messages |
|----------|----------------|----------|
| ml-service | db-service-group, embedding-service-group | 280 total (includes reprocessed) |

Additional fields added by ML service (beyond those from raw_articles):
```json
{
    "...fields from raw_articles...",
    "ml_processed": true,
    "processed_at": "2026-...",
    "summary": "First 2 sentences (max 360 chars)",
    "topic": "war",
    "topic_confidence": 0.85,
    "sentiment": "negative",
    "confidence": 0.72,
    "threat_score": 79,
    "geopolitical_risk": 16.56,
    "risk_level": "critical",
    "entities": [
        {"name": "Russia", "type": "GPE", "confidence": 0.98},
        {"name": "Ukraine", "type": "GPE", "confidence": 0.97}
    ],
    "relationships": [
        {"source": "Russia", "target": "Ukraine", "type": "conflict", "confidence": 0.85}
    ],
    "keywords": ["war", "conflict", "military"],
    "content_hash": "sha256hex...",
    "dedupe_key": "sha256hex..."   // SHA-256(url|source|first 500 chars of full_text)
}
```

## Database Write Flow

### processed_articles table

| Column | Source | Notes |
|--------|--------|-------|
| id | PostgreSQL SERIAL | Primary key, auto-assigned |
| article_id | Kafka message `id` | Pipeline identifier (SHA-256 hash) |
| title | Kafka message `title` | |
| content | Kafka message `content` | |
| source | Kafka message `source` | |
| published_at | Kafka message `published_at` | Parsed via `parse_datetime()` |
| ml_processed | ML-enriched `ml_processed` | |
| confidence | ML-enriched `confidence` | Avg of sentiment + topic confidence |
| sentiment | ML-enriched `sentiment` | negative/positive/neutral |
| url | Kafka message `url` | |
| image_url | Kafka message `image` | Field name mismatch: GNews API uses `image`, DB column is `image_url` |
| summary | ML-enriched `summary` | |
| topic | ML-enriched `topic` | |
| threat_score | ML-enriched `threat_score` | |
| geopolitical_risk | ML-enriched `geopolitical_risk` | |
| risk_level | ML-enriched `risk_level` | low/medium/high/critical |
| content_hash | ML-enriched `content_hash` | SHA-256 of full_text |
| dedupe_key | ML-enriched `dedupe_key` | SHA-256(url\|source\|full_text[:500]), UNIQUE |
| created_at | PostgreSQL DEFAULT | CURRENT_TIMESTAMP |

### Deduplication Strategy

`ON CONFLICT (dedupe_key) DO UPDATE` — if an article with the same dedupe_key exists, the existing row is UPDATED with new values (article-level upsert). The `RETURNING id` clause returns the existing row's DB id, not a new one.

### Entity Lifecycle

1. ML service extracts entities via BERT NER model (`dbmdz/bert-large-cased-finetuned-conll03-english`)
2. Entities are published in the `processed_articles` Kafka message
3. Database consumer calls `replace_related_records(article_db_id, data)`:
   - Deletes existing entities for that article
   - Inserts new entities from message
4. Stored in `extracted_entities` table (child of `processed_articles.id`)

### Relationship Lifecycle

1. ML service infers relationships via keyword-based co-occurrence
2. Relationships published in `processed_articles` Kafka message
3. Database consumer writes to `relationships` table via `replace_related_records()`

### Event Intelligence Lifecycle

1. Database consumer calls `update_event_intelligence(article_db_id)`
2. Processes entities and relationships to form events
3. Stored in `events` and `event_articles` tables

## Embedding Lifecycle

### Before Fix (BUG)
1. Embedding consumer reads Kafka message from `processed_articles`
2. Extracts `article.get("id")` — this is the SHA-256 hash
3. Tries to INSERT into `article_embeddings.article_id`
4. FK constraint `article_embeddings.article_id → processed_articles.id` VIOLATED
5. The hash (e.g., `63455923`) does not match any DB serial id (e.g., `1`)
6. Result: `ForeignKeyViolationError` — all embeddings fail

### After Fix
1. Embedding consumer reads Kafka message from `processed_articles`
2. Extracts `article.get("dedupe_key")`
3. Queries `processed_articles` by dedupe_key to find DB serial `id`
4. Uses the correct DB serial `id` for FK insert
5. INSERT succeeds — FK constraint satisfied

### Verification
```
Embeddings count: 46
Orphan FK violations: 0
All embeddings correctly reference processed_articles.id
```

## Search Lifecycle

### Full-Text Search (Elasticsearch)
1. Database consumer calls `index_article(data)` after upsert
2. Document indexed to `processed_articles` index with `_id = dedupe_key`
3. ES document fields: article_id, title, content, source, sentiment, topic, threat_score, risk_level, url, published_at
4. API endpoint: `/search/?q=<query>` — token-based search across title and content

### Semantic Search (Vector Embedding)
1. Embedding consumer generates 384-dim vector from article title + content
2. Vector stored in `article_embeddings.embedding` column (pgvector)
3. HNSW index on embedding column for fast cosine similarity search
4. API endpoint: `/semantic-search?q=<query>`:
   - Generates embedding for query text
   - Performs `SELECT ... ORDER BY embedding <=> $1::vector LIMIT 10`
   - Returns matching articles with similarity scores

## Copilot Lifecycle

1. POST `/copilot/query` with `{question: "..."}`
2. Token-based embedding of question → semantic search finds relevant articles
3. For each relevant article:
   - Load entities, relationships, events from DB
4. CopilotService.build_assessment():
   - Classifies threat level (critical/high/medium/low) based on aggregate scores
   - Computes sentiment distribution across relevant articles
   - Counts unique entities, key locations, involved actors
5. CopilotService.build_summary():
   - Concatenates article summaries with entity context
   - Returns combined intelligence summary
6. Returns: threat_level, articles[], entities[], events[], summary, recommendations[]

## Failure Modes and Recovery

### GNews API Failure
- **Symptom**: `fetch-real-news` returns HTTP 500 or empty articles
- **Recovery**: Next scheduled poll retries; no data loss (articles already in Kafka are preserved)
- **Logs**: `error_fetching_news` in ingest-service

### Kafka Broker Down
- **Symptom**: Producer/consumer operations hang or throw `KafkaException`
- **Recovery**: Producers buffer messages; consumers block on poll(); auto-reconnect on broker restart
- **Logs**: `kafka_produce_error` or `consumer_error` in respective services

### PostgreSQL Down
- **Symptom**: database-service health check fails; upsert operations throw psycopg2 errors
- **Recovery**: SimpleConnectionPool.getconn() with SELECT 1 validation; pool recreated on stale connection
- **Logs**: psycopg2 exceptions captured in database-service

### Elasticsearch Down
- **Symptom**: index_article() throws connection error
- **Recovery**: Exception caught in handle_message, consumer continues and commits offset
- **Logs**: Elasticsearch HTTP error logged by database-service consumer

### Model Loading Failure (ML Service)
- **Symptom**: ML consumer fails on startup with model import error
- **Recovery**: Consumer exits; Docker restart policy restarts container; models downloaded on next startup
- **Logs**: Model loading errors in ml-consumer stderr

### Embedding Generation Failure
- **Symptom**: Embedding consumer logs `embedding_processing_failed`
- **Recovery**: Exception caught, consumer commits offset and continues; missing embeddings served as None
- **Logs**: Full exception traceback in embedding-consumer logs

## Database Schema Foreign Key Constraints

| Child Table | FK Column | Parent Table | Parent Column | Delete Rule |
|-------------|-----------|--------------|---------------|-------------|
| extracted_entities | article_id | processed_articles | id | CASCADE |
| article_sentiments | article_id | processed_articles | id | CASCADE |
| relationships | article_id | processed_articles | id | CASCADE |
| event_articles | article_id | processed_articles | id | CASCADE |
| article_embeddings | article_id | processed_articles | id | CASCADE |

All FK constraints verified: **0 orphans** across all child tables.

## Service Dependencies

| Service | Depends On | Database | Kafka Topics | External APIs |
|---------|------------|----------|--------------|---------------|
| ingest-service | Kafka | — | raw_articles (P) | GNews API |
| ml-service | Kafka | — | raw_articles (C), processed_articles (P) | HuggingFace (NLP models) |
| database-service | Kafka, PostgreSQL, ES | public schema | processed_articles (C) | — |
| embedding-service | Kafka, PostgreSQL | public schema | processed_articles (C) | HuggingFace (sentence-transformers) |
| modular-api | PostgreSQL, Elasticsearch | public schema | — | — |
| energy-service | PostgreSQL | energy schema | — | — |
| ml-platform | PostgreSQL | ml schema | — | energy-service (REST) |

Legend: P = Producer, C = Consumer
