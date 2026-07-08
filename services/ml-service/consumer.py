"""ML enrichment consumer.

Subscribes to ``raw_articles``, enriches with ML (sentiment, topic, entities,
threat score), and publishes enriched articles to ``processed_articles``.
"""

import hashlib
import sys
from datetime import datetime

from backend.shared.kafka import ConsumerRunner, JsonProducer, install_signal_handlers, json_deserializer
from backend.shared.logging_config import setup_structlog, get_logger
from ml_core import (
    build_dedupe_key, build_full_text, extract_keywords, summarize_text,
    classify_topic, analyze_sentiment, extract_entities,
    score_threat, infer_relationships,
    load_models,
)

setup_structlog("ml-service-consumer")
logger = get_logger(__name__)

output_producer = JsonProducer()


def enrich_article(article: dict) -> dict:
    full_text = build_full_text(article)
    summary = summarize_text(full_text)
    sentiment, confidence = analyze_sentiment(full_text)
    topic, topic_confidence = classify_topic(full_text)
    entities = extract_entities(full_text)
    threat_score, geopolitical_risk, risk_level = score_threat(full_text, sentiment, topic, len(entities))
    relationships = infer_relationships(entities, full_text)
    keywords = extract_keywords(full_text)

    return {
        **article,
        "ml_processed": True,
        "processed_at": datetime.utcnow().isoformat(),
        "summary": summary,
        "topic": topic,
        "topic_confidence": topic_confidence,
        "sentiment": sentiment,
        "confidence": round((confidence + topic_confidence) / 2, 2),
        "threat_score": threat_score,
        "geopolitical_risk": geopolitical_risk,
        "risk_level": risk_level,
        "entities": entities,
        "relationships": relationships,
        "keywords": keywords,
        "content_hash": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        "dedupe_key": build_dedupe_key(article, full_text),
    }


def handle_message(msg) -> None:
    article = json_deserializer(msg.value())
    enriched = enrich_article(article)
    logger.info(
        "article_processed",
        title=enriched.get("title"),
        topic=enriched.get("topic"),
        threat_score=enriched.get("threat_score"),
        risk_level=enriched.get("risk_level"),
        entity_count=len(enriched.get("entities", [])),
    )
    output_producer.produce("processed_articles", enriched)


if __name__ == "__main__":
    logger.info("loading_models")
    load_models()
    logger.info("models_loaded")

    runner = ConsumerRunner("ml-service-group", "raw_articles", handle_message)
    install_signal_handlers(runner)
    runner.run()
    output_producer.flush()
    logger.info("consumer_exited")
    sys.exit(0)
