import hashlib
import json
import logging
import os
import re
import threading
from collections import Counter
from datetime import datetime
from itertools import combinations

from confluent_kafka import Consumer, Producer
from fastapi import FastAPI
from transformers import pipeline
import spacy
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ML Service")

consumer = None
producer = None

sentiment_pipeline = None
ner_pipeline = None

nlp = None
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

TOPIC_KEYWORDS = {
    "war": ["war", "missile", "strike", "attack", "military", "troops", "drone", "airstrike"],
    "diplomacy": ["ceasefire", "summit", "negotiation", "talks", "diplomatic", "alliance", "peace"],
    "economics": ["oil", "trade", "sanction", "economy", "inflation", "market", "currency", "energy"],
    "cyber": ["cyber", "ransomware", "malware", "hacker", "breach", "espionage", "infrastructure"],
}
THREAT_KEYWORDS = {
    "critical": ["nuclear", "chemical", "biological", "missile", "genocide", "airstrike"],
    "high": ["attack", "war", "sanction", "retaliation", "crisis", "terror"],
    "medium": ["tension", "warning", "surge", "pressure", "alert", "military"],
}
RELATIONSHIP_KEYWORDS = {
    "attack": [
        "attack",
        "strike",
        "bomb",
        "target",
        "retaliation",
        "airstrike",
        "missile",
    ],

    "alliance": [
        "alliance",
        "cooperation",
        "support",
        "backing",
        "joint",
        "partnership",
    ],

    "sanction": [
        "sanction",
        "restriction",
        "embargo",
        "penalty",
    ],

    "diplomacy": [
        "talks",
        "summit",
        "ceasefire",
        "agreement",
        "negotiation",
        "dialogue",
    ],
}
ENTITY_ALIASES = {
    "us": "United States",
    "u.s.": "United States",
    "u.s": "United States",
    "usa": "United States",

    "uk": "United Kingdom",
    "u.k.": "United Kingdom",

    "russia's": "Russia",
    "china's": "China",
    "iran's": "Iran",
}

IGNORE_ENTITIES = {
    "earthquakes",
    "band of brothers",
}
STOPWORDS = {
    "the", "and", "for", "that", "with", "from", "this", "have", "will", "into", "amid", "their",
    "about", "after", "before", "while", "under", "over", "they", "them", "were", "been", "said",
}


def load_models():
    global sentiment_pipeline, ner_pipeline, nlp

    logger.info("Loading NLP models...")

    # spaCy always loads first
    try:
        nlp = spacy.load("en_core_web_sm")
        logger.info("spaCy model loaded successfully")
    except Exception as exc:
        nlp = None
        logger.exception("Failed to load spaCy model: %s", exc)

    # Transformers are optional
    try:
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
        )

        ner_pipeline = pipeline(
            "ner",
            model="dbmdz/bert-large-cased-finetuned-conll03-english",
            aggregation_strategy="simple",
        )

        logger.info("Transformer models loaded successfully")

    except Exception as exc:
        sentiment_pipeline = None
        ner_pipeline = None

        logger.warning(
            "Transformer models unavailable. Falling back to spaCy."
        )

        logger.exception(exc)

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def build_full_text(article: dict) -> str:
    title = normalize_text(article.get("title", ""))
    content = normalize_text(article.get("content", ""))
    return f"{title}. {content}".strip()


def build_dedupe_key(article: dict, full_text: str) -> str:
    source = article.get("source", "")
    url = article.get("url", "")
    base = normalize_text(f"{url}|{source}|{full_text[:500]}")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def summarize_text(full_text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", full_text)
    clean_sentences = [sentence.strip() for sentence in sentences if len(sentence.strip()) > 30]
    if not clean_sentences:
        return full_text[:240]
    summary = " ".join(clean_sentences[:2])
    return summary[:360]


def classify_topic(full_text: str) -> tuple[str, float]:
    text = full_text.lower()
    scores = {
        topic: sum(text.count(keyword) for keyword in keywords)
        for topic, keywords in TOPIC_KEYWORDS.items()
    }
    best_topic, best_score = max(scores.items(), key=lambda item: item[1], default=("war", 0))
    total = sum(scores.values()) or 1
    confidence = round(best_score / total, 2) if best_score else 0.35
    return (best_topic if best_score else "general", confidence)


def extract_entities(full_text: str):

    # Preferred path: Transformer NER
    if ner_pipeline is not None:
        try:
            ner_results = ner_pipeline(full_text[:1200])

            relevant = [
                {
                    "text": entity["word"],
                    "type": entity["entity_group"],
                    "score": float(entity["score"]),
                }
                for entity in ner_results
                if (
                    entity["entity_group"]
                    in {"LOC", "ORG", "PER", "MISC"}
                    and entity["score"] > 0.70
                )
            ]

            unique = []
            seen = set()

            for entity in relevant:

                entity["text"] = normalize_entity_name(entity["text"])

                key = entity["text"].lower()

                if key in IGNORE_ENTITIES:
                   continue

                if key and key not in seen:
                   unique.append(entity)
                   seen.add(key)

            return unique[:12]

        except Exception as exc:
            logger.warning(
                "Transformer NER extraction failed: %s",
                exc,
            )

    # Fallback path: spaCy
    if nlp is not None:
        try:
            doc = nlp(full_text)

            entities = []

            for ent in doc.ents:

                if ent.label_ in {
                    "PERSON",
                    "ORG",
                    "GPE",
                }:

                    entity_name = normalize_entity_name(ent.text)
                    if entity_name.lower() in IGNORE_ENTITIES:
                      continue

                    entities.append(
                        {
                            "text": ent.text,
                            "type": ent.label_,
                            "score": 0.90,
                        }
                    )

            unique = []
            seen = set()

            for entity in entities:

                key = entity["text"].strip().lower()

                if key and key not in seen:
                    unique.append(entity)
                    seen.add(key)

            return unique[:12]

        except Exception as exc:
            logger.warning(
                "spaCy extraction failed: %s",
                exc,
            )

    return []


def analyze_sentiment(full_text: str) -> tuple[str, float]:
    if sentiment_pipeline is None:
        return "neutral", 0.4

    result = sentiment_pipeline(full_text[:1000])[0]
    label = result["label"].lower()
    score = float(result["score"])
    if label == "negative":
        return "negative", score
    if label == "positive":
        return "positive", score
    return "neutral", score


def score_threat(full_text: str, sentiment: str, topic: str, entity_count: int) -> tuple[float, float, str]:
    text = full_text.lower()
    keyword_score = 0
    for level, keywords in THREAT_KEYWORDS.items():
        level_weight = {"critical": 35, "high": 20, "medium": 10}[level]
        if any(keyword in text for keyword in keywords):
            keyword_score += level_weight

    sentiment_score = {"negative": 25, "neutral": 10, "positive": 0}.get(sentiment, 5)
    topic_score = {"war": 20, "cyber": 18, "economics": 12, "diplomacy": 8, "general": 6}.get(topic, 6)
    entity_score = min(entity_count * 2, 15)

    threat_score = min(100.0, keyword_score + sentiment_score + topic_score + entity_score)
    geopolitical_risk = round(min(100.0, threat_score * 0.92 + keyword_score * 0.4), 2)

    if threat_score >= 75:
        risk_level = "critical"
    elif threat_score >= 55:
        risk_level = "high"
    elif threat_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    return round(threat_score, 2), geopolitical_risk, risk_level


def infer_relationship_type(full_text: str) -> str:
    text = full_text.lower()
    for relationship_type, keywords in RELATIONSHIP_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return relationship_type
    return "association"


def infer_relationships(entities, full_text: str):

    actors = [
        entity
        for entity in entities
        if entity["type"] in {"GPE", "ORG", "PERSON"}
    ]

    if len(actors) < 2:
        return []

    relationship_type = infer_relationship_type(full_text)

    relationships = []

    for source, target in list(combinations(actors[:5], 2))[:6]:

        confidence = 0.55

        if relationship_type != "association":
            confidence = 0.80

        relationships.append(
            {
                "source": source["text"],
                "target": target["text"],
                "type": relationship_type,
                "confidence": confidence,
                "context": summarize_text(full_text),
            }
        )

    return relationships


def extract_keywords(full_text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", full_text.lower())
    filtered = [word for word in words if word not in STOPWORDS]
    return [word for word, _ in Counter(filtered).most_common(8)]

def normalize_entity_name(name: str) -> str:
    key = name.strip().lower()

    if key in ENTITY_ALIASES:
        return ENTITY_ALIASES[key]

    return name.strip()

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
        "fake_confidence": round((confidence + topic_confidence) / 2, 2),
        "threat_score": threat_score,
        "geopolitical_risk": geopolitical_risk,
        "risk_level": risk_level,
        "entities": entities,
        "relationships": relationships,
        "keywords": keywords,
        "content_hash": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        "dedupe_key": build_dedupe_key(article, full_text),
    }


def start_kafka_consumer():
    global consumer, producer
    logger.info("ML Service Kafka consumer starting...")

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "ml-service-group",
            "auto.offset.reset": "earliest",
            "session.timeout.ms": 6000,
        }
    )
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

    try:
        consumer.subscribe(["raw_articles"])
        logger.info("Subscribed to raw_articles topic")

        while True:
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
                enriched.get("title"),
                enriched.get("topic"),
                enriched.get("threat_score"),
                enriched.get("risk_level"),
                len(enriched.get("entities", [])),
            )
            producer.produce("processed_articles", value=json.dumps(enriched))
            producer.flush()
    except Exception as exc:
        logger.exception("Kafka consumer crashed: %s", exc)
    finally:
        if consumer:
            consumer.close()


@app.on_event("startup")
def startup_event():
    load_models()
    threading.Thread(target=start_kafka_consumer, daemon=True).start()


@app.get("/")
def read_root():
    return {"message": "ML Service is Online (Enhanced Intelligence Mode)"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "model_loaded": sentiment_pipeline is not None, "ner_loaded": ner_pipeline is not None}
