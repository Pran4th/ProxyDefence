import json
from datetime import datetime
from typing import Any, Optional

from backend.shared.entity_normalization import normalize_entity as shared_normalize_entity, is_blacklisted_entity
from backend.shared.logging_config import get_logger

from db import get_connection, return_connection

logger = get_logger(__name__)


def _risk_level(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _token_similarity(left: str, right: str) -> float:
    left_tokens = {token for token in (left or "").lower().split() if len(token) > 3}
    right_tokens = {token for token in (right or "").lower().split() if len(token) > 3}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)


def replace_related_records(article_db_id: int, data: dict[str, Any]) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM extracted_entities WHERE article_id = %s", (article_db_id,))
            cur.execute("DELETE FROM article_sentiments WHERE article_id = %s", (article_db_id,))
            cur.execute("DELETE FROM relationships WHERE article_id = %s", (article_db_id,))

            for entity in data.get("entities", []):
                cur.execute(
                    "INSERT INTO extracted_entities (article_id, entity_text, entity_type, confidence) VALUES (%s, %s, %s, %s)",
                    (article_db_id, entity.get("text"), entity.get("type"), entity.get("score", 0.0)),
                )

            cur.execute(
                "INSERT INTO article_sentiments (article_id, sentiment_label, sentiment_score) VALUES (%s, %s, %s)",
                (article_db_id, data.get("sentiment", "neutral"), data.get("confidence", 0.0)),
            )

            def _parse_dt(value):
                if not value:
                    return None
                try:
                    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                except ValueError:
                    return None

            for relationship in data.get("relationships", []):
                cur.execute(
                    """
                    INSERT INTO relationships (
                        article_id, source_entity, target_entity, relationship_type,
                        confidence, context, evidence, source_article_ids,
                        observed_at, confidence_history
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP), %s)
                    """,
                    (
                        article_db_id,
                        relationship.get("source"),
                        relationship.get("target"),
                        relationship.get("type", "association"),
                        relationship.get("confidence", 0.0),
                        relationship.get("context"),
                        relationship.get("context"),
                        [article_db_id],
                        _parse_dt(data.get("published_at")),
                        json.dumps([{"confidence": relationship.get("confidence", 0.0), "observed_at": data.get("published_at")}]),
                    ),
                )
        conn.commit()
    finally:
        return_connection(conn)


def update_event_intelligence(article_db_id: int, conn=None) -> None:
    owns_connection = conn is None
    if conn is None:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, summary, content, topic, threat_score, confidence, published_at
                FROM processed_articles WHERE id = %s
                """,
                (article_db_id,),
            )
            article = cur.fetchone()
            if not article:
                return

            columns = [desc[0] for desc in cur.description]
            article_data = dict(zip(columns, article))

            cur.execute(
                "SELECT entity_text, entity_type, confidence FROM extracted_entities WHERE article_id = %s",
                (article_db_id,),
            )
            entities = [
                {"text": row[0], "type": row[1], "confidence": float(row[2] or 0)}
                for row in cur.fetchall()
                if row[0]
            ]
            entity_names = set()

            for entity in entities:
                normalized = shared_normalize_entity(entity["text"]).lower()
                if is_blacklisted_entity(normalized):
                    continue
                entity_names.add(normalized)

            cur.execute(
                """
                SELECT e.id, e.title, e.summary, e.topic, e.risk_score, e.last_seen,
                       ARRAY_REMOVE(ARRAY_AGG(DISTINCT LOWER(ee.entity_text)), NULL) AS entities
                FROM events e
                LEFT JOIN event_entities ee ON ee.event_id = e.id
                WHERE e.last_seen >= COALESCE(%s, NOW()) - INTERVAL '72 hours'
                   OR e.topic = %s
                GROUP BY e.id
                ORDER BY e.last_seen DESC NULLS LAST
                LIMIT 25
                """,
                (article_data["published_at"], article_data["topic"]),
            )

            best_event = None
            best_score = 0.0

            article_text = (
                f"{article_data.get('title') or ''} "
                f"{article_data.get('summary') or article_data.get('content') or ''}"
            )

            for row in cur.fetchall():
                event_entities = set(row[6] or [])
                overlap_count = len(entity_names & event_entities)
                entity_overlap = overlap_count / max(len(entity_names | event_entities), 1)
                if overlap_count < 2:
                    continue

                topic_score = 1.0 if row[3] and row[3] == article_data["topic"] else 0.0
                semantic_score = _token_similarity(article_text, f"{row[1] or ''} {row[2] or ''}")

                time_score = 0.0
                if article_data["published_at"] and row[5]:
                    hours_diff = abs((article_data["published_at"] - row[5]).total_seconds()) / 3600
                    if hours_diff <= 24:
                        time_score = 1.0
                    elif hours_diff <= 72:
                        time_score = 0.5

                score = round(
                    (entity_overlap * 0.60) + (topic_score * 0.15) + (time_score * 0.15) + (semantic_score * 0.10), 3,
                )
                if score > best_score:
                    best_score = score
                    best_event = row[0]

            if best_event and best_score >= 0.60:
                event_id = best_event
                cur.execute(
                    "INSERT INTO event_articles (event_id, article_id, similarity_score) VALUES (%s, %s, %s) ON CONFLICT (event_id, article_id) DO UPDATE SET similarity_score = EXCLUDED.similarity_score",
                    (event_id, article_db_id, best_score),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO events (title, summary, topic, risk_score, risk_level, confidence, first_seen, last_seen, article_count, cluster_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s) RETURNING id
                    """,
                    (
                        article_data["title"] or "Untitled event",
                        article_data["summary"] or article_data["content"],
                        article_data["topic"] or "general",
                        float(article_data["threat_score"] or 0),
                        _risk_level(float(article_data["threat_score"] or 0)),
                        float(article_data["confidence"] or 0),
                        article_data["published_at"],
                        article_data["published_at"],
                        f"{article_data['topic']}:{article_db_id}",
                    ),
                )
                event_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO event_articles (event_id, article_id, similarity_score) VALUES (%s, %s, 1.0)",
                    (event_id, article_db_id),
                )

            for entity in entities:
                cur.execute(
                    """
                    INSERT INTO event_entities (event_id, entity_text, entity_type, mention_count, avg_confidence)
                    VALUES (%s, %s, %s, 1, %s)
                    ON CONFLICT (event_id, entity_text) DO UPDATE SET
                        mention_count = event_entities.mention_count + 1,
                        avg_confidence = (event_entities.avg_confidence + EXCLUDED.avg_confidence) / 2,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (event_id, entity["text"], entity["type"], entity["confidence"]),
                )

            cur.execute(
                """
                UPDATE events e SET
                    article_count = stats.article_count,
                    risk_score = stats.risk_score,
                    risk_level = CASE WHEN stats.risk_score >= 75 THEN 'critical' WHEN stats.risk_score >= 55 THEN 'high' WHEN stats.risk_score >= 30 THEN 'medium' ELSE 'low' END,
                    confidence = stats.confidence,
                    first_seen = stats.first_seen,
                    last_seen = stats.last_seen,
                    updated_at = CURRENT_TIMESTAMP
                FROM (
                    SELECT ea.event_id, COUNT(*) AS article_count, AVG(pa.threat_score) AS risk_score,
                           AVG(pa.confidence) AS confidence, MIN(pa.published_at) AS first_seen,
                           MAX(pa.published_at) AS last_seen
                    FROM event_articles ea JOIN processed_articles pa ON pa.id = ea.article_id
                    WHERE ea.event_id = %s GROUP BY ea.event_id
                ) stats WHERE e.id = stats.event_id
                """,
                (event_id,),
            )

            for entity in entities:
                cur.execute(
                    "SELECT ARRAY_REMOVE(ARRAY_AGG(DISTINCT event_id), NULL) FROM event_entities WHERE LOWER(entity_text) = LOWER(%s)",
                    (entity["text"],),
                )
                associated_events = cur.fetchone()[0] or []
                cur.execute(
                    "SELECT ARRAY_REMOVE(ARRAY_AGG(DISTINCT id), NULL) FROM relationships WHERE LOWER(source_entity) = LOWER(%s) OR LOWER(target_entity) = LOWER(%s)",
                    (entity["text"], entity["text"]),
                )
                associated_relationships = cur.fetchone()[0] or []
                cur.execute(
                    """
                    INSERT INTO entity_profiles (entity_text, entity_type, aliases, mention_frequency, risk_trend, associated_events, associated_relationships, last_seen)
                    VALUES (%s, %s, %s, 1, %s, %s, %s, %s)
                    ON CONFLICT (entity_text) DO UPDATE SET
                        entity_type = COALESCE(entity_profiles.entity_type, EXCLUDED.entity_type),
                        mention_frequency = entity_profiles.mention_frequency + 1,
                        risk_trend = EXCLUDED.risk_trend,
                        associated_events = EXCLUDED.associated_events,
                        associated_relationships = EXCLUDED.associated_relationships,
                        last_seen = GREATEST(entity_profiles.last_seen, EXCLUDED.last_seen),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        entity["text"], entity["type"], [entity["text"]],
                        float(article_data["threat_score"] or 0),
                        associated_events, associated_relationships,
                        article_data["published_at"],
                    ),
                )

                if float(article_data["threat_score"] or 0) >= 55:
                    cur.execute(
                        """
                        INSERT INTO alerts (watchlist_id, entity_text, event_id, alert_type, message, risk_score)
                        SELECT we.watchlist_id, we.entity_text, %s, 'risk_change', %s, %s
                        FROM watchlist_entities we WHERE LOWER(we.entity_text) = LOWER(%s)
                        """,
                        (event_id, f"Risk increased for {entity['text']} in event {event_id}", float(article_data["threat_score"] or 0), entity["text"]),
                    )

        if owns_connection:
            conn.commit()
    except Exception:
        if owns_connection:
            conn.rollback()
        raise
    finally:
        if owns_connection:
            return_connection(conn)


def validate_rebuild_prerequisites(cur) -> None:
    required_tables = ["processed_articles", "events", "event_articles", "event_entities"]
    missing_tables = []
    for table_name in required_tables:
        cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        if cur.fetchone()[0] is None:
            missing_tables.append(table_name)
    if missing_tables:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Missing required tables: {', '.join(missing_tables)}",
        )
