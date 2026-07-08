# Pipeline Guide

## End-to-End Data Flow

```
                            ┌─────────────────────────────────────────────┐
                            │              GNews API                     │
                            │  (https://gnews.io/api/v4/search)          │
                            └──────────────────┬──────────────────────────┘
                                               │ HTTP GET (keyword search)
                                               v
                            ┌─────────────────────────────────────────────┐
                            │           ingest-service (:8001)            │
                            │  /fetch-real-news → fetch_real_news()      │
                            │  Scheduler runs every hour                  │
                            └──────────────────┬──────────────────────────┘
                                               │ Kafka produce
                                               │ topic: raw_articles
                                               v
                            ┌─────────────────────────────────────────────┐
                            │         raw_articles [topic]                │
                            │  partitions: 3, retention: 7 days          │
                            └──────────────────┬──────────────────────────┘
                                               │ Consumer: ml-service-group
                                               v
                            ┌─────────────────────────────────────────────┐
                            │            ml-service (:8002)               │
                            │  consumer.py (standalone process)           │
                            │  ┌─────────────────────────────────────┐    │
                            │  │ Sentiment Analysis (keyword-based)  │    │
                            │  │ Entity Extraction (spaCy NER)       │    │
                            │  │ Topic Classification                │    │
                            │  │ Threat Scoring                      │    │
                            │  │ Geopolitical Risk Assessment        │    │
                            │  └─────────────────────────────────────┘    │
                            └──────────────────┬──────────────────────────┘
                                               │ Kafka produce
                                               │ topic: processed_articles
                                               v
                            ┌─────────────────────────────────────────────┐
                            │       processed_articles [topic]            │
                            │  partitions: 3, retention: 7 days          │
                            └──────────┬──────────────────┬───────────────┘
                                       │                  │
                     db-service-group  │   embedding-service-group
                                       v                  v
            ┌──────────────────┐  ┌──────────────────────────────┐
            │ database-service │  │   embedding-service (:8005)  │
            │     (:8003)      │  │   consumer.py                │
            │   consumer.py    │  │   └→ pgvector embeddings     │
            │   ┌────────────┐ │  │      (article_embeddings)    │
            │   │ PostgreSQL │ │  └──────────────────────────────┘
            │   │ ES index   │ │
            │   └────────────┘ │
            └────────┬─────────┘
                     │
                     v
            ┌──────────────────┐
            │  modular-api     │
            │     (:8000)      │
            │  API gateway     │
            └────────┬─────────┘
                     │ HTTP (JSON)
                     v
            ┌──────────────────┐
            │   Frontend       │
            │  Vite (:8080)    │
            │  React + TS      │
            └──────────────────┘

Standalone services (not in pipeline):

  Energy Service (:8006) ──→ PostgreSQL (energy schema) ──→ consumed by ML Platform
  ML Platform (:8007) ──→ PostgreSQL (ml schema) ──→ consumes Energy Service data
  Research/ ──→ Jupyter notebooks ──→ exported models ──→ ML Platform
```

## Step-by-Step Flow

### 1. Trigger Ingestion

```bash
curl http://localhost:8001/fetch-real-news
```

The ingest-service:
- Calls GNews API with configured search query
- Parses response into article objects
- Publishes each article to `raw_articles` Kafka topic
- Returns success/failure response

### 2. ML Processing

The ml-service consumer (`ml-service-group`) automatically:
- Polls `raw_articles` topic
- Runs spaCy NER to extract entities
- Runs keyword-based sentiment analysis (negative/positive/neutral)
- Classifies topic domain
- Computes threat score and geopolitical risk
- Publishes enriched result to `processed_articles` topic

### 3. Database Persistence

The database-service consumer (`db-service-group`) automatically:
- Consumes `processed_articles` messages
- Upserts articles into `public.processed_articles` table (deduplicated by `dedupe_key`)
- Inserts entities into `public.extracted_entities`
- Inserts sentiments into `public.article_sentiments`
- Indexes article in Elasticsearch `processed_articles` index

### 4. Embedding Generation

The embedding-service consumer (`embedding-service-group`) automatically:
- Consumes `processed_articles` messages
- Generates vector embeddings using `BAAI/bge-small-en-v1.5`
- Stores in `public.article_embeddings` with pgvector `vector(384)`

### 5. API Serving

The modular-api serves the frontend:
- `GET /api/articles` — list stored articles
- `GET /api/search` — full-text search (via Elasticsearch)
- `POST /api/semantic-search` — vector similarity search (via embedding-service)
- `GET /api/analytics/summary` — aggregate statistics
- `GET /api/events` — correlated event clusters

### 6. Frontend Display

The React frontend (port 8080) calls modular-api (port 8000) for all data.

---

## Verifying Each Stage

### Ingest Service
```bash
# Check ingest service is running
curl http://localhost:8001/

# Trigger a fetch
curl http://localhost:8001/fetch-real-news

# Check health
curl http://localhost:8001/health
```

### Kafka Topics
```bash
# List topics
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092

# Check messages in raw_articles
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_articles --from-beginning --max-messages 3

# Check messages in processed_articles
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic processed_articles --from-beginning --max-messages 3

# Check consumer lag
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group ml-service-group --describe
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group db-service-group --describe
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group embedding-service-group --describe
```

### ML Service
```bash
# Check ML service health
curl http://localhost:8002/health
```

### Database Service
```bash
# Check database service health
curl http://localhost:8003/health

# List articles
curl http://localhost:8003/api/articles | python -m json.tool

# Get analytics summary
curl http://localhost:8003/api/analytics/summary | python -m json.tool
```

### PostgreSQL Direct
```bash
# Query articles in database
docker exec -it postgres-db psql -U admin -d defenseintel -c "SELECT id, title, source, sentiment, topic, risk_level FROM processed_articles ORDER BY published_at DESC LIMIT 10;"

# Check entity counts
docker exec -it postgres-db psql -U admin -d defenseintel -c "SELECT entity_type, COUNT(*) as count FROM extracted_entities GROUP BY entity_type ORDER BY count DESC;"
```

### Elasticsearch
```bash
# Check ES health
curl http://localhost:9200/_cluster/health

# Check index exists
curl http://localhost:9200/_cat/indices

# Search articles in ES
curl http://localhost:9200/processed_articles/_search?pretty
```

### Embedding Service
```bash
# Check embedding service health
curl http://localhost:8005/health

# Test embedding generation
curl -X POST http://localhost:8005/generate -H "Content-Type: application/json" -d '{"text":"Test article about oil prices"}'
```

### Modular API
```bash
# Check modular-api health
curl http://localhost:8000/

# List articles via API gateway
curl http://localhost:8000/api/articles -H "Authorization: Bearer <token>"

# Analytics summary
curl http://localhost:8000/api/analytics/summary -H "Authorization: Bearer <token>"
```

### Status Script
```bash
# Check all services at once
.\scripts\dev\status.ps1
```

---

## Seeding Demo Data

The project provides several ways to seed demo data:

### Quick pipeline trigger (requires full stack running)
```bash
curl http://localhost:8001/fetch-real-news
```

### Energy service seed data
Set `ENERGY_LOAD_SEED=1` before starting the energy service. This upserts seed data for:
- 20+ countries (locations)
- 22 ports
- 15 refineries
- 15 pipelines
- 15 oil fields
- Strategic chokepoints, shipping routes, SPRs, benchmarks
- Organizations, suppliers, commodities

Seed data is **idempotent** — safe to re-run (upserts on `slug`).

### ML Platform dataset building
```bash
# Build a dataset from Energy Service data
curl -X POST http://localhost:8007/api/v1/datasets/build -H "Content-Type: application/json" -d '{"name": "energy_demo", "target_column": "criticality"}'
```

---

## Resetting the Database

### Full reset (destroy all data)
```bash
docker compose down -v
docker compose up -d
```

This removes volumes (`-v` flag) and reinitializes from `infra/sql/init.sql`.

### Selective table truncation
```bash
docker exec -it postgres-db psql -U admin -d defenseintel -c "
TRUNCATE TABLE processed_articles CASCADE;
TRUNCATE TABLE events CASCADE;
TRUNCATE TABLE entity_profiles CASCADE;
TRUNCATE TABLE article_embeddings CASCADE;
"
```

### Reset Kafka offsets (reprocess all articles)
```bash
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group ml-service-group --topic raw_articles --reset-offsets --to-earliest --execute
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group db-service-group --topic processed_articles --reset-offsets --to-earliest --execute
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group embedding-service-group --topic processed_articles --reset-offsets --to-earliest --execute
```

### Delete Kafka topics
```bash
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic raw_articles
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic processed_articles
```
Topics will be recreated on next message produce (auto-create enabled).

### Reset energy schema (energy-service)
```bash
docker exec -it postgres-db psql -U admin -d defenseintel -c "DROP SCHEMA IF EXISTS energy CASCADE;"
```
Will be recreated on energy-service restart.

### Reset ML schema (ml-platform)
```bash
docker exec -it postgres-db psql -U admin -d defenseintel -c "DROP SCHEMA IF EXISTS ml CASCADE;"
```
Will be recreated on ml-platform restart.
