import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Optional

import psycopg2
from confluent_kafka import Consumer
from elasticsearch import Elasticsearch
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from psycopg2 import OperationalError as Psycopg2OpError
from psycopg2 import pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Database Service")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "defenseintel")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
if not POSTGRES_USER or not POSTGRES_PASSWORD:
    raise RuntimeError("Missing required PostgreSQL credentials")
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
if not JWT_SECRET_KEY:
    raise RuntimeError("Missing required JWT secret")

consumer = Consumer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": "db-service-group",
        "auto.offset.reset": "earliest",
        "session.timeout.ms": 6000,
    }
)

bearer_scheme = HTTPBearer(auto_error=False)

db_pool = None
consumer_running = False
consumer_restart_count = 0
last_consumer_error = None

def init_db_pool(min_size: int = 5, max_size: int = 20) -> None:
    global db_pool
    try:
        db_pool = pool.SimpleConnectionPool(
            min_size,
            max_size,
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            connect_timeout=5,
        )
        logger.info("Database connection pool initialized: min=%d, max=%d", min_size, max_size)
    except Exception as exc:
        logger.exception("Failed to initialize connection pool: %s", exc)
        raise


def get_postgres_connection():
    if db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return db_pool.getconn()


def return_postgres_connection(conn) -> None:
    if db_pool is not None:
        db_pool.putconn(conn)


def get_elasticsearch_client(max_retries: int = 10, delay: int = 3) -> Optional[Elasticsearch]:
    for attempt in range(max_retries):
        try:
            client = Elasticsearch(f"http://{ELASTICSEARCH_HOST}:9200", request_timeout=10)
            if client.ping():
                return client
        except Exception as exc:
            logger.warning("Elasticsearch connection attempt %s/%s failed: %s", attempt + 1, max_retries, exc)
        if attempt < max_retries - 1:
            time.sleep(delay)
    return None


def parse_datetime(value: Optional[str]):
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def get_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, username, role FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            user = {
                "id": row[0],
                "email": row[1],
                "username": row[2],
                "role": row[3],
            }
            if user["role"] != "admin":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
            return user
    finally:
        return_postgres_connection(conn)


def validate_rebuild_prerequisites(cur) -> None:
    required_tables = ["processed_articles", "events", "event_articles", "event_entities"]
    missing_tables = []

    for table_name in required_tables:
        cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        if cur.fetchone()[0] is None:
            missing_tables.append(table_name)

    if missing_tables:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Missing required tables: {', '.join(missing_tables)}",
        )


def get_pool_stats() -> dict[str, int]:
    if db_pool is None:
        return {"initialized": False, "available": 0, "total": 0}
    return {
        "initialized": True,
        "available": db_pool._pool.__len__() if hasattr(db_pool, "_pool") else 0,
        "total": db_pool._maxconn if hasattr(db_pool, "_maxconn") else 0,
    }


def create_tables() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'analyst',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS processed_articles (
            id SERIAL PRIMARY KEY,
            article_id INTEGER,
            title TEXT,
            content TEXT,
            source TEXT,
            published_at TIMESTAMP,
            ml_processed BOOLEAN,
            confidence FLOAT,
            sentiment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS url TEXT",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS image_url TEXT",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS summary TEXT",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS topic VARCHAR(50)",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS threat_score FLOAT DEFAULT 0",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS geopolitical_risk FLOAT DEFAULT 0",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT 'low'",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)",
        "ALTER TABLE processed_articles ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(64)",
        """
        CREATE TABLE IF NOT EXISTS extracted_entities (
            id SERIAL PRIMARY KEY,
            article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
            entity_text TEXT,
            entity_type VARCHAR(50),
            confidence FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS article_sentiments (
            id SERIAL PRIMARY KEY,
            article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
            sentiment_label VARCHAR(20),
            sentiment_score FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS relationships (
            id SERIAL PRIMARY KEY,
            article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
            source_entity TEXT NOT NULL,
            target_entity TEXT NOT NULL,
            relationship_type VARCHAR(50) NOT NULL,
            confidence FLOAT,
            context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS evidence TEXT",
        "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS source_article_ids INTEGER[] DEFAULT ARRAY[]::INTEGER[]",
        "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS confidence_history JSONB DEFAULT '[]'::jsonb",
        """
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            summary TEXT,
            topic VARCHAR(50),
            risk_score FLOAT DEFAULT 0,
            risk_level VARCHAR(20) DEFAULT 'low',
            confidence FLOAT DEFAULT 0,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            article_count INTEGER DEFAULT 0,
            cluster_key VARCHAR(128),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS event_articles (
            event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
            article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
            similarity_score FLOAT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_id, article_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS event_entities (
            event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
            entity_text TEXT NOT NULL,
            entity_type VARCHAR(50),
            mention_count INTEGER DEFAULT 1,
            avg_confidence FLOAT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_id, entity_text)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS entity_profiles (
            entity_text TEXT PRIMARY KEY,
            entity_type VARCHAR(50),
            aliases TEXT[] DEFAULT ARRAY[]::TEXT[],
            mention_frequency INTEGER DEFAULT 0,
            risk_trend FLOAT DEFAULT 0,
            associated_events INTEGER[] DEFAULT ARRAY[]::INTEGER[],
            associated_relationships INTEGER[] DEFAULT ARRAY[]::INTEGER[],
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            executive_summary TEXT,
            key_actors JSONB DEFAULT '[]'::jsonb,
            key_events JSONB DEFAULT '[]'::jsonb,
            threat_assessment TEXT,
            confidence_score FLOAT DEFAULT 0,
            recommendations JSONB DEFAULT '[]'::jsonb,
            source_article_ids INTEGER[] DEFAULT ARRAY[]::INTEGER[],
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS watchlists (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS watchlist_entities (
            watchlist_id INTEGER REFERENCES watchlists(id) ON DELETE CASCADE,
            entity_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (watchlist_id, entity_text)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            watchlist_id INTEGER REFERENCES watchlists(id) ON DELETE CASCADE,
            entity_text TEXT,
            event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
            alert_type VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            risk_score FLOAT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            resource TEXT,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_articles_dedupe_key ON processed_articles(dedupe_key)",
        "CREATE INDEX IF NOT EXISTS idx_processed_articles_published_at ON processed_articles(published_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_processed_articles_topic ON processed_articles(topic)",
        "CREATE INDEX IF NOT EXISTS idx_processed_articles_risk_level ON processed_articles(risk_level)",
        "CREATE INDEX IF NOT EXISTS idx_extracted_entities_article ON extracted_entities(article_id)",
        "CREATE INDEX IF NOT EXISTS idx_relationships_article_id ON relationships(article_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic)",
        "CREATE INDEX IF NOT EXISTS idx_events_risk_score ON events(risk_score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_events_last_seen ON events(last_seen DESC)",
        "CREATE INDEX IF NOT EXISTS idx_event_articles_article_id ON event_articles(article_id)",
        "CREATE INDEX IF NOT EXISTS idx_event_entities_entity_text ON event_entities(entity_text)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)",
    ]

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()
        logger.info("Database schema verified")
    finally:
        return_postgres_connection(conn)


def upsert_article(data: dict[str, Any]) -> int:
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO processed_articles (
                    article_id,
                    title,
                    content,
                    source,
                    published_at,
                    ml_processed,
                    confidence,
                    sentiment,
                    url,
                    image_url,
                    summary,
                    topic,
                    threat_score,
                    geopolitical_risk,
                    risk_level,
                    content_hash,
                    dedupe_key
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dedupe_key) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    source = EXCLUDED.source,
                    published_at = EXCLUDED.published_at,
                    ml_processed = EXCLUDED.ml_processed,
                    confidence = EXCLUDED.confidence,
                    sentiment = EXCLUDED.sentiment,
                    url = EXCLUDED.url,
                    image_url = EXCLUDED.image_url,
                    summary = EXCLUDED.summary,
                    topic = EXCLUDED.topic,
                    threat_score = EXCLUDED.threat_score,
                    geopolitical_risk = EXCLUDED.geopolitical_risk,
                    risk_level = EXCLUDED.risk_level,
                    content_hash = EXCLUDED.content_hash
                RETURNING id
                """,
                (
                    data.get("id"),
                    data.get("title"),
                    data.get("content"),
                    data.get("source"),
                    parse_datetime(data.get("published_at")),
                    data.get("ml_processed", False),
                    data.get("confidence", 0.0),
                    data.get("sentiment", "neutral"),
                    data.get("url"),
                    data.get("image"),
                    data.get("summary"),
                    data.get("topic"),
                    data.get("threat_score", 0.0),
                    data.get("geopolitical_risk", 0.0),
                    data.get("risk_level", "low"),
                    data.get("content_hash"),
                    data.get("dedupe_key"),
                ),
            )
            article_db_id = cur.fetchone()[0]
        conn.commit()
        return article_db_id
    finally:
        return_postgres_connection(conn)


def replace_related_records(article_db_id: int, data: dict[str, Any]) -> None:
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM extracted_entities WHERE article_id = %s", (article_db_id,))
            cur.execute("DELETE FROM article_sentiments WHERE article_id = %s", (article_db_id,))
            cur.execute("DELETE FROM relationships WHERE article_id = %s", (article_db_id,))

            for entity in data.get("entities", []):
                cur.execute(
                    """
                    INSERT INTO extracted_entities (article_id, entity_text, entity_type, confidence)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        article_db_id,
                        entity.get("text"),
                        entity.get("type"),
                        entity.get("score", 0.0),
                    ),
                )

            cur.execute(
                """
                INSERT INTO article_sentiments (article_id, sentiment_label, sentiment_score)
                VALUES (%s, %s, %s)
                """,
                (article_db_id, data.get("sentiment", "neutral"), data.get("confidence", 0.0)),
            )

            for relationship in data.get("relationships", []):
                cur.execute(
                    """
                    INSERT INTO relationships (
                        article_id,
                        source_entity,
                        target_entity,
                        relationship_type,
                        confidence,
                        context,
                        evidence,
                        source_article_ids,
                        observed_at,
                        confidence_history
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP), %s)
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
                        parse_datetime(data.get("published_at")),
                        json.dumps([{"confidence": relationship.get("confidence", 0.0), "observed_at": data.get("published_at")}]),
                    ),
                )
        conn.commit()
    finally:
        return_postgres_connection(conn)


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


def update_event_intelligence(article_db_id: int, conn=None) -> None:
    owns_connection = conn is None
    if conn is None:
        conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, summary, content, topic, threat_score, confidence, published_at
                FROM processed_articles
                WHERE id = %s
                """,
                (article_db_id,),
            )
            article = cur.fetchone()
            if not article:
                return

            columns = [desc[0] for desc in cur.description]
            article_data = dict(zip(columns, article))

            cur.execute(
                """
                SELECT entity_text, entity_type, confidence
                FROM extracted_entities
                WHERE article_id = %s
                """,
                (article_db_id,),
            )
            entities = [
                {"text": row[0], "type": row[1], "confidence": float(row[2] or 0)}
                for row in cur.fetchall()
                if row[0]
            ]
            entity_aliases = {
           "us": "united states",
           "u.s.": "united states",
           "the united states": "united states",
           "trump": "donald trump",
           "central command": "us central command"
           }
            EVENT_ENTITY_BLACKLIST = {
    "reuters",
    "ap",
    "associated press",
    "fox news",
    "cnn",
    "bbc",
    "new york times",
    "ai generated image",
    "brink of war"
}

            entity_names = set()

            for entity in entities:

                normalized = entity["text"].lower()

                normalized = entity_aliases.get(
                    normalized,
                    normalized
                )

                if normalized in EVENT_ENTITY_BLACKLIST:
                    continue

                entity_names.add(normalized)

            cur.execute(
                """
                SELECT
                    e.id,
                    e.title,
                    e.summary,
                    e.topic,
                    e.risk_score,
                    e.last_seen,
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

                overlap_count = len(
                    entity_names & event_entities
                )

                entity_overlap = overlap_count / max(
                    len(entity_names | event_entities),
                    1
                    )

                # Require at least 2 common entities
                if overlap_count < 2:
                 continue

                topic_score = (
                    1.0
                    if row[3] and row[3] == article_data["topic"]
                    else 0.0
                )

                semantic_score = _token_similarity(
                    article_text,
                    f"{row[1] or ''} {row[2] or ''}"
                )

                # Time proximity score
                time_score = 0.0

                if article_data["published_at"] and row[5]:

                    hours_diff = abs(
                        (
                            article_data["published_at"]
                            - row[5]
                        ).total_seconds()
                    ) / 3600

                    if hours_diff <= 24:
                        time_score = 1.0

                    elif hours_diff <= 72:
                        time_score = 0.5

                    else:
                        time_score = 0.0

                score = round(
                    (entity_overlap * 0.60)
                    + (topic_score * 0.15)
                    + (time_score * 0.15)
                    + (semantic_score * 0.10),
                    3,
                )

                if score > best_score:
                    best_score = score
                    best_event = row[0]

            if best_event and best_score >= 0.60:
                event_id = best_event
                cur.execute(
                    """
                    INSERT INTO event_articles (event_id, article_id, similarity_score)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (event_id, article_id) DO UPDATE
                    SET similarity_score = EXCLUDED.similarity_score
                    """,
                    (event_id, article_db_id, best_score),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO events (
                        title, summary, topic, risk_score, risk_level, confidence,
                        first_seen, last_seen, article_count, cluster_key
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
                    RETURNING id
                    """,
                   (
    article_data["title"] or "Untitled event",
    article_data["summary"] or article_data["content"],
    article_data["topic"] or "general",
    float(article_data["threat_score"] or 0),
    _risk_level(
        float(article_data["threat_score"] or 0)
    ),
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
                UPDATE events e
                SET
                    article_count = stats.article_count,
                    risk_score = stats.risk_score,
                    risk_level = 
CASE
    WHEN stats.risk_score >= 75 THEN 'critical'
    WHEN stats.risk_score >= 55 THEN 'high'
    WHEN stats.risk_score >= 30 THEN 'medium'
    ELSE 'low'
END,
                    confidence = stats.confidence,
                    first_seen = stats.first_seen,
                    last_seen = stats.last_seen,
                    updated_at = CURRENT_TIMESTAMP
                FROM (
                    SELECT
                        ea.event_id,
                        COUNT(*) AS article_count,
                        AVG(pa.threat_score) AS risk_score,
                        AVG(pa.confidence) AS confidence,
                        MIN(pa.published_at) AS first_seen,
                        MAX(pa.published_at) AS last_seen
                    FROM event_articles ea
                    JOIN processed_articles pa ON pa.id = ea.article_id
                    WHERE ea.event_id = %s
                    GROUP BY ea.event_id
                ) stats
                WHERE e.id = stats.event_id
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
                    """
                    SELECT ARRAY_REMOVE(ARRAY_AGG(DISTINCT id), NULL)
                    FROM relationships
                    WHERE LOWER(source_entity) = LOWER(%s) OR LOWER(target_entity) = LOWER(%s)
                    """,
                    (entity["text"], entity["text"]),
                )
                associated_relationships = cur.fetchone()[0] or []
                cur.execute(
                    """
                    INSERT INTO entity_profiles (
                        entity_text, entity_type, aliases, mention_frequency, risk_trend,
                        associated_events, associated_relationships, last_seen
                    )
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
                        entity["text"],
                        entity["type"],
                        [entity["text"]],
                        float(article_data["threat_score"] or 0),
                        associated_events,
                        associated_relationships,
                        article_data["published_at"],
                    ),
                )

                if float(article_data["threat_score"] or 0) >= 55:
                    cur.execute(
                        """
                        INSERT INTO alerts (watchlist_id, entity_text, event_id, alert_type, message, risk_score)
                        SELECT
                            we.watchlist_id,
                            we.entity_text,
                            %s,
                            'risk_change',
                            %s,
                            %s
                        FROM watchlist_entities we
                        WHERE LOWER(we.entity_text) = LOWER(%s)
                        """,
                        (
                            event_id,
                            f"Risk increased for {entity['text']} in event {event_id}",
                            float(article_data["threat_score"] or 0),
                            entity["text"],
                        ),
                    )

        if owns_connection:
            conn.commit()
    except Exception:
        if owns_connection:
            conn.rollback()
        raise
    finally:
        if owns_connection:
            return_postgres_connection(conn)


def index_article(data: dict[str, Any]) -> None:
    client = get_elasticsearch_client()
    if client is None:
        logger.warning("Skipping Elasticsearch indexing because the cluster is unavailable")
        return

    document = {
        "article_id": data.get("id"),
        "title": data.get("title"),
        "content": data.get("content"),
        "source": data.get("source"),
        "published_at": data.get("published_at"),
        "ml_processed": data.get("ml_processed", False),
        "confidence": data.get("confidence", 0.0),
        "sentiment": data.get("sentiment", "neutral"),
        "summary": data.get("summary"),
        "topic": data.get("topic"),
        "threat_score": data.get("threat_score", 0.0),
        "geopolitical_risk": data.get("geopolitical_risk", 0.0),
        "risk_level": data.get("risk_level", "low"),
        "entities": [entity.get("text") for entity in data.get("entities", [])],
    }
    client.index(
        index="processed_articles",
        id=data.get("dedupe_key") or data.get("id"),
        document=document,
    )


def process_message(data: dict[str, Any]) -> None:
 try:
    article_db_id = upsert_article(data)

    replace_related_records(
        article_db_id,
        data
    )

    update_event_intelligence(
        article_db_id
    )

    index_article(data)

 except Exception as e:
    logger.exception(
        f"Failed processing article: {e}"
    )

def start_kafka_consumer() -> None:
    global consumer_running, last_consumer_error

    consumer_running = True

    logger.info("Database Service Kafka consumer starting...")

    try:
        consumer.subscribe(["processed_articles"])
        logger.info("Subscribed to processed_articles topic")

        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():
                logger.error("Consumer error: %s", msg.error())
                continue

            payload = json.loads(
                msg.value().decode("utf-8")
            )

            process_message(payload)

    except Exception as exc:
        consumer_running = False
        last_consumer_error = str(exc)

        logger.exception(
            "Kafka consumer crashed: %s",
            exc
        )

        raise

    finally:
        consumer.close()


def run_consumer_supervisor() -> None:
    global consumer_restart_count
    global consumer_running
    global last_consumer_error

    while True:
        try:
            start_kafka_consumer()

        except Exception as exc:
            consumer_restart_count += 1
            consumer_running = False
            last_consumer_error = str(exc)

            logger.error(
                "Consumer restart #%s in 5 seconds",
                consumer_restart_count
            )

            time.sleep(5)


def fetch_articles(limit: int = 20, offset: int = 0, sentiment: Optional[str] = None):
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            if sentiment:
                cur.execute(
                    """
                    SELECT * FROM processed_articles
                    WHERE sentiment = %s
                    ORDER BY published_at DESC NULLS LAST, created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (sentiment, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM processed_articles
                    ORDER BY published_at DESC NULLS LAST, created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return serialize_rows(columns, rows)
    finally:
        return_postgres_connection(conn)


def serialize_rows(columns, rows):
    results = []
    for row in rows:
        item = dict(zip(columns, row))
        for key in ("published_at", "created_at"):
            if item.get(key):
                item[key] = item[key].isoformat()
        results.append(item)
    return results


@app.on_event("startup")
def startup_event():
    init_db_pool()
    create_tables()
    threading.Thread(
    target=run_consumer_supervisor,
    daemon=True
).start()


@app.get("/")
def read_root():
    return {"message": "Database Service is online"}


@app.get("/health")
def health_check():
    try:
        conn = get_postgres_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return_postgres_connection(conn)
        es = get_elasticsearch_client()
        if es is None:
            raise RuntimeError("Elasticsearch unavailable")
        es.info()
        pool_stats = get_pool_stats()
        return {
            "status": "healthy",
            "postgres": "connected",
            "elasticsearch": "connected",
            "kafka": {
    "running": consumer_running,
    "restart_count": consumer_restart_count,
    "last_error": last_consumer_error,
},
            "pool": pool_stats,
        }
    except Exception as exc:
        pool_stats = get_pool_stats()
        return {
            "status": "unhealthy",
            "error": str(exc),
            "pool": pool_stats,
            "kafka": {
    "running": consumer_running,
    "restart_count": consumer_restart_count,
    "last_error": last_consumer_error,
},
        }


@app.get("/api/articles")
def get_articles(limit: int = 20, offset: int = 0, sentiment: Optional[str] = None):
    try:
        return fetch_articles(limit=limit, offset=offset, sentiment=sentiment)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

@app.post("/rebuild-events")
async def rebuild_events(current_user: dict[str, Any] = Depends(get_admin_user)):

    conn = get_postgres_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                validate_rebuild_prerequisites(cur)

                cur.execute("DELETE FROM event_entities")
                cur.execute("DELETE FROM event_articles")
                cur.execute("DELETE FROM events")

                cur.execute("""
                    SELECT id
                    FROM processed_articles
                    ORDER BY id
                """)

                article_ids = [
                    row[0]
                    for row in cur.fetchall()
                ]

            rebuilt = 0

            for article_id in article_ids:
                update_event_intelligence(
                    article_id,
                    conn=conn,
                )
                rebuilt += 1

        return {
            "status": "success",
            "articles_processed": rebuilt,
        }

    finally:
        return_postgres_connection(conn)
@app.get("/api/analytics/summary")
def get_analytics_summary():
    conn = get_postgres_connection()
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
        return_postgres_connection(conn)


@app.get("/api/search")
def search_articles(q: str = Query(..., min_length=2)):
    client = get_elasticsearch_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Search backend unavailable")

    response = client.search(
        index="processed_articles",
        body={
            "size": 20,
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": ["title^3", "summary^2", "content", "source", "topic"],
                    "fuzziness": "AUTO",
                }
            },
        },
    )

    return {
        "query": q,
        "total_results": response["hits"]["total"]["value"],
        "results": [hit["_source"] for hit in response["hits"]["hits"]],
    }


@app.get("/api/articles/{article_id}")
def get_article(article_id: int):
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM processed_articles WHERE id = %s", (article_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Article not found")
            columns = [desc[0] for desc in cur.description]
        return serialize_rows(columns, [row])[0]
    finally:
        return_postgres_connection(conn)
