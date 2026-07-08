import hashlib
import json
import os
from datetime import datetime

import structlog
from confluent_kafka import Consumer, Producer
from fastapi import FastAPI

from backend.shared.logging_config import setup_structlog, get_logger
from backend.shared.request_middleware import RequestTrackingMiddleware
from backend.shared.config import SERVICE_VERSION
from prometheus_fastapi_instrumentator import Instrumentator
from ml_core import (
    build_dedupe_key, build_full_text, extract_keywords, summarize_text,
    classify_topic, analyze_sentiment, extract_entities,
    score_threat, infer_relationships,
    load_models, get_model_health,
)

setup_structlog("ml-service")
logger = get_logger(__name__)

app = FastAPI(title="ML Service")
app.add_middleware(RequestTrackingMiddleware)

Instrumentator().instrument(app).expose(app)

consumer = None
producer = None
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")


def _delivery_callback(err, msg):
    if err:
        logger.error("Message delivery failed: %s", err)
    else:
        logger.debug("Message delivered to %s [%s]", msg.topic(), msg.partition())


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


_consumer_running = True


def stop_consumer():
    global _consumer_running
    _consumer_running = False


def start_kafka_consumer():
    global consumer, producer
    logger.info("ML Service Kafka consumer starting...")

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": "ml-service-group",
        "auto.offset.reset": "earliest",
        "session.timeout.ms": 6000,
        "enable.auto.commit": False,
    })
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

    try:
        consumer.subscribe(["raw_articles"])
        logger.info("Subscribed to raw_articles topic")

        while _consumer_running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("Consumer error: %s", msg.error())
                continue

            article = json.loads(msg.value().decode("utf-8"))
            enriched = enrich_article(article)
            logger.info(
                "Processed '%s' -> topic=%s threat=%s risk=%s entities=%s",
                enriched.get("title"), enriched.get("topic"),
                enriched.get("threat_score"), enriched.get("risk_level"),
                len(enriched.get("entities", [])),
            )
            producer.produce(
                "processed_articles",
                value=json.dumps(enriched),
                callback=_delivery_callback,
            )
            producer.poll(0)
            consumer.commit()
    except Exception as exc:
        logger.exception("Kafka consumer crashed: %s", exc)
        raise
    finally:
        if consumer:
            consumer.close()


@app.on_event("startup")
def startup_event():
    load_models()


@app.get("/")
def read_root():
    return {"message": "ML Service is Online (Enhanced Intelligence Mode)"}


@app.get("/health")
def health_check():
    models = get_model_health()
    return {
        "status": "healthy",
        **models,
    }


@app.get("/liveness")
def liveness():
    return {"status": "alive"}


@app.get("/readiness")
def readiness():
    models = get_model_health()
    return {"status": "healthy" if models.get("models_loaded") else "unhealthy", **models}


@app.get("/version")
def version():
    return {"service": "ml-service", "version": SERVICE_VERSION}
