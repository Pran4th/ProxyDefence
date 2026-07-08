from datetime import datetime
from typing import Any, Optional

from backend.shared.logging_config import get_logger

from db import get_connection, return_connection

logger = get_logger(__name__)


def parse_datetime(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def serialize_rows(columns, rows):
    results = []
    for row in rows:
        item = dict(zip(columns, row))
        for key in ("published_at", "created_at"):
            if item.get(key):
                item[key] = item[key].isoformat()
        results.append(item)
    return results


def upsert_article(data: dict[str, Any]) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO processed_articles (
                    article_id, title, content, source, published_at, ml_processed,
                    confidence, sentiment, url, image_url, summary, topic,
                    threat_score, geopolitical_risk, risk_level, content_hash, dedupe_key
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dedupe_key) DO UPDATE SET
                    title = EXCLUDED.title, content = EXCLUDED.content, source = EXCLUDED.source,
                    published_at = EXCLUDED.published_at, ml_processed = EXCLUDED.ml_processed,
                    confidence = EXCLUDED.confidence, sentiment = EXCLUDED.sentiment,
                    url = EXCLUDED.url, image_url = EXCLUDED.image_url, summary = EXCLUDED.summary,
                    topic = EXCLUDED.topic, threat_score = EXCLUDED.threat_score,
                    geopolitical_risk = EXCLUDED.geopolitical_risk, risk_level = EXCLUDED.risk_level,
                    content_hash = EXCLUDED.content_hash
                RETURNING id
                """,
                (
                    data.get("id"), data.get("title"), data.get("content"),
                    data.get("source"), parse_datetime(data.get("published_at")),
                    data.get("ml_processed", False), data.get("confidence", 0.0),
                    data.get("sentiment", "neutral"), data.get("url"), data.get("image"),
                    data.get("summary"), data.get("topic"), data.get("threat_score", 0.0),
                    data.get("geopolitical_risk", 0.0), data.get("risk_level", "low"),
                    data.get("content_hash"), data.get("dedupe_key"),
                ),
            )
            article_db_id = cur.fetchone()[0]
        conn.commit()
        return article_db_id
    finally:
        return_connection(conn)


def fetch_articles(limit: int = 20, offset: int = 0, sentiment: Optional[str] = None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if sentiment:
                cur.execute(
                    "SELECT * FROM processed_articles WHERE sentiment = %s ORDER BY published_at DESC NULLS LAST, created_at DESC LIMIT %s OFFSET %s",
                    (sentiment, limit, offset),
                )
            else:
                cur.execute(
                    "SELECT * FROM processed_articles ORDER BY published_at DESC NULLS LAST, created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return serialize_rows(columns, rows)
    finally:
        return_connection(conn)


def get_article_by_id(article_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM processed_articles WHERE id = %s", (article_id,))
            row = cur.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cur.description]
        return serialize_rows(columns, [row])[0]
    finally:
        return_connection(conn)


def get_analytics_summary():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM processed_articles")
            total_articles = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM processed_articles WHERE published_at >= NOW() - INTERVAL '24 hours'")
            last_24h = cur.fetchone()[0] or 0
            cur.execute("SELECT AVG(confidence), AVG(threat_score) FROM processed_articles")
            avg_confidence, avg_threat_score = cur.fetchone()
            cur.execute("SELECT sentiment, COUNT(*) FROM processed_articles GROUP BY sentiment")
            sentiment_distribution = {row[0]: row[1] for row in cur.fetchall()}
        return {
            "total_articles": total_articles,
            "articles_last_24h": last_24h,
            "avg_confidence": float(avg_confidence or 0),
            "avg_threat_score": float(avg_threat_score or 0),
            "sentiment_distribution": sentiment_distribution,
        }
    finally:
        return_connection(conn)
