import uuid
from datetime import datetime, timezone


def build_article(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    article = {
        "title": "Test Article Title",
        "content": "Test article content for testing purposes.",
        "source": "TestSource",
        "author": "Test Author",
        "url": f"https://example.com/article/{uuid.uuid4().hex[:8]}",
        "published_at": now,
        "sentiment": "neutral",
        "confidence": 0.75,
        "threat_score": 5.0,
        "risk_level": "medium",
        "topic": "geopolitics",
        "ml_processed": False,
    }
    article.update(overrides)
    return article


def build_raw_kafka_message(**overrides) -> dict:
    msg = {
        "title": "Kafka Test Article",
        "content": "Article content from Kafka pipeline test.",
        "source": "GNews",
        "author": "Pipeline Tester",
        "url": f"https://example.com/kafka/{uuid.uuid4().hex[:8]}",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    msg.update(overrides)
    return msg


def build_processed_kafka_message(**overrides) -> dict:
    msg = build_raw_kafka_message()
    msg.update({
        "sentiment": "negative",
        "confidence": 0.85,
        "threat_score": 7.0,
        "risk_level": "high",
        "topic": "cyber warfare",
        "ml_processed": True,
    })
    msg.update(overrides)
    return msg
