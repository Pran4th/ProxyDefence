"""ML-platform's replacement for ml-service/consumer.py.

Subscribes to raw_articles, enriches with real ML (transformer sentiment/NER,
trained topic classifier, ML-blended threat score) instead of ml-service's
keyword-only topic/threat scoring, and publishes to processed_articles with
the EXACT same schema — database-service needs zero changes.

Run standalone (not via uvicorn — this is a Kafka consumer, not an HTTP app):
    PYTHONPATH="<repo>;<repo>/services/ml-platform" python consumer/article_enrichment.py
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # so `import ml_core` resolves to consumer/ml_core

from backend.shared.kafka import ConsumerRunner, JsonProducer, install_signal_handlers, json_deserializer  # noqa: E402
from backend.shared.logging_config import setup_structlog, get_logger  # noqa: E402
from ml_core import (  # noqa: E402
    build_dedupe_key, build_full_text, extract_keywords, summarize_text,
    classify_topic, analyze_sentiment, extract_entities,
    score_threat, infer_relationships,
    load_models,
)

setup_structlog("ml-platform-consumer")
logger = get_logger(__name__)

output_producer = JsonProducer()

# Parallel-run validation (Phase 3 step 5) passed against real Kafka traffic —
# see CLAUDE.md's pipeline section for the side-by-side comparison. Real
# output topic now that cutover is complete.
OUTPUT_TOPIC = "processed_articles"


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
        "processed_by": "ml-platform",
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
        topic_confidence=enriched.get("topic_confidence"),
        threat_score=enriched.get("threat_score"),
        risk_level=enriched.get("risk_level"),
        entity_count=len(enriched.get("entities", [])),
    )
    output_producer.produce(OUTPUT_TOPIC, enriched)


if __name__ == "__main__":
    logger.info("loading_models")
    load_models()
    logger.info("models_loaded")

    runner = ConsumerRunner("ml-platform-consumer-group", "raw_articles", handle_message)
    install_signal_handlers(runner)
    runner.run()
    output_producer.flush()
    logger.info("consumer_exited")
    sys.exit(0)
