# Kafka Guide

## Overview

ProxyDefence uses Kafka as the central event bus for its data pipeline. Two topics carry articles through the processing pipeline: raw (unprocessed) and processed (ML-enriched).

---

## Topics

| Topic | Partitions | Replication | Retention | Producer | Consumer(s) |
|-------|-----------|-------------|-----------|----------|-------------|
| `raw_articles` | 3 | 1 | 7 days | ingest-service | ml-service (`ml-service-group`) |
| `processed_articles` | 3 | 1 | 7 days | ml-service | database-service (`db-service-group`), embedding-service (`embedding-service-group`) |

Topics are auto-created by Kafka (`KAFKA_AUTO_CREATE_TOPICS_ENABLE=true`). Their definitions are in `backend/shared/kafka/topics.py`:

```python
TOPICS = {
    "raw_articles": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "604800000"},
    },
    "processed_articles": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "604800000"},
    },
}
```

---

## Consumer Groups

| Group ID | Topic | Purpose | Commit Strategy |
|----------|-------|---------|-----------------|
| `ml-service-group` | `raw_articles` | NLP enrichment (sentiment, entities, topics, threats) | Manual commit after processing |
| `db-service-group` | `processed_articles` | Persist to PostgreSQL + Elasticsearch | Manual commit after processing |
| `embedding-service-group` | `processed_articles` | Generate vector embeddings for semantic search | Manual commit after processing |

All consumers share these settings:
- `auto.offset.reset=earliest` — start from beginning if no offset committed
- `enable.auto.commit=False` — manual commit after successful processing
- `session.timeout.ms=6000`

---

## Message Schemas

### Raw Article (produced by ingest-service to `raw_articles`)

```json
{
  "title": "Russia launches new oil pipeline to China",
  "content": "Full article text here...",
  "source": "GNews",
  "publishedAt": "2026-07-03T10:30:00Z",
  "url": "https://gnews.io/article/...",
  "image": "https://gnews.io/image/..."
}
```

### Processed Article (produced by ml-service to `processed_articles`)

```json
{
  "title": "Russia launches new oil pipeline to China",
  "content": "Full article text here...",
  "source": "GNews",
  "publishedAt": "2026-07-03T10:30:00Z",
  "url": "https://gnews.io/article/...",
  "sentiment": {
    "label": "negative",
    "score": -0.45
  },
  "entities": [
    {"text": "Russia", "type": "GPE", "confidence": 0.98},
    {"text": "China", "type": "GPE", "confidence": 0.97}
  ],
  "topic": "energy",
  "threat_score": 0.6,
  "geopolitical_risk": 0.7,
  "risk_level": "medium"
}
```

---

## Consumer Pattern

Every consumer uses the shared `ConsumerRunner` class from `backend.shared.kafka.consumer`:

```python
from backend.shared.kafka import ConsumerRunner
from backend.shared.kafka.serialization import json_deserializer

def handle_message(msg):
    data = json_deserializer(msg.value())
    # ... business logic ...

runner = ConsumerRunner("ml-service-group", "raw_articles", handle_message)
runner.run()  # blocks until SIGINT/SIGTERM
```

Consumers run as **standalone processes** (`python consumer.py`), not inside the FastAPI process. Signal handlers (SIGTERM/SIGINT) enable graceful shutdown.

---

## Serialization

All messages use plain JSON serialization (no Schema Registry):

```python
# Serializer (backend/shared/kafka/serialization.py)
def json_serializer(data: dict) -> bytes:
    return json.dumps(data, default=str).encode("utf-8")

def json_deserializer(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))
```

---

## Debugging Commands

### List topics
```bash
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Describe topic details
```bash
docker exec -it kafka kafka-topics --describe --topic raw_articles --bootstrap-server localhost:9092
docker exec -it kafka kafka-topics --describe --topic processed_articles --bootstrap-server localhost:9092
```

### Check consumer group status and lag
```bash
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group ml-service-group --describe
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group db-service-group --describe
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group embedding-service-group --describe
```

### View messages on a topic (from beginning)
```bash
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_articles --from-beginning --max-messages 5
```

### View messages with JSON formatting
```bash
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic processed_articles --from-beginning --max-messages 3 2>/dev/null | python -m json.tool
```

### Check topic message count
```bash
docker exec -it kafka kafka-run-class kafka.tools.GetOffsetShell --bootstrap-server localhost:9092 --topic raw_articles --time -1
```

### Reset consumer offsets to earliest (reprocess all messages)
```bash
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group ml-service-group --topic raw_articles --reset-offsets --to-earliest --execute
```

### Reset consumer offsets to latest (skip existing messages)
```bash
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group db-service-group --topic processed_articles --reset-offsets --to-latest --execute
```

### Check Kafka broker health
```bash
docker exec -it kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

---

## Error Handling

- **Malformed messages:** Logged with `logger.error("consumer_handler_failed", ...)` and skipped — consumer commits offset and continues
- **Connection failures:** Consumer polls with 1-second timeout; if broker unreachable, `poll()` returns errors that are logged but do not crash
- **Manual commits:** `consumer.commit()` in the `finally` block ensures offsets advance even on handler failures (at-most-once semantics on error)

---

## Architecture Diagram

```
ingest-service           ml-service              database-service
     |                       |                        |
     |  produce              |  produce               |  consume
     v                       v                        v
  raw_articles          processed_articles        + PostgreSQL
  [topic:3p]            [topic:3p]                + Elasticsearch
     |                       |
     |  consume              |  consume
     v                       v
  ml-service              embedding-service
  (ml-service-group)      (embedding-service-group)
                              |
                              v
                          pgvector
                          (article_embeddings)
```
