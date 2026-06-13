import json
from typing import Any


def record_to_dict(record: Any) -> dict[str, Any]:
    item = dict(record)
    for key, value in list(item.items()):
        if hasattr(value, "isoformat"):
            item[key] = value.isoformat()
    return item


class IntelligenceRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def get_dashboard_stats(self) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM processed_articles)::int AS articles,
                    (SELECT COUNT(*) FROM events)::int AS events,
                    (SELECT COUNT(*) FROM entity_profiles)::int AS entities,
                    (SELECT COUNT(*) FROM relationships)::int AS relationships
                """
            )
        return dict(row)

    async def get_threat_analytics(self) -> dict[str, list[dict[str, Any]]]:
        async with self.pool.acquire() as conn:
            risk_distribution = await conn.fetch(
                """
                SELECT risk_level, COUNT(*)
                FROM events
                GROUP BY risk_level
                """
            )
            topic_distribution = await conn.fetch(
                """
                SELECT topic, COUNT(*)
                FROM events
                GROUP BY topic
                """
            )
        return {
            "risk_distribution": [record_to_dict(row) for row in risk_distribution],
            "topic_distribution": [record_to_dict(row) for row in topic_distribution],
        }

    async def list_events(self, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM events
                ORDER BY risk_score DESC NULLS LAST, last_seen DESC NULLS LAST, updated_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
        return [record_to_dict(row) for row in rows]

    async def get_event(self, event_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            event = await conn.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
            if event is None:
                return None
            entities = await conn.fetch(
                """
                SELECT entity_text, entity_type, mention_count, avg_confidence
                FROM event_entities
                WHERE event_id = $1
                ORDER BY mention_count DESC, avg_confidence DESC
                """,
                event_id,
            )
            articles = await conn.fetch(
                """
                SELECT
                    pa.id,
                    pa.title,
                    pa.topic,
                    pa.threat_score,
                    ea.similarity_score
                FROM event_articles ea
                JOIN processed_articles pa
                    ON pa.id = ea.article_id
                WHERE ea.event_id = $1
                ORDER BY pa.threat_score DESC
                LIMIT 20
                """,
                event_id,
            )
        payload = record_to_dict(event)
        payload["entities"] = [record_to_dict(row) for row in entities]
        payload["articles"] = [record_to_dict(row) for row in articles]
        return payload

    async def get_event_articles(self, event_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT pa.*, ea.similarity_score
                FROM event_articles ea
                JOIN processed_articles pa ON pa.id = ea.article_id
                WHERE ea.event_id = $1
                ORDER BY pa.published_at DESC NULLS LAST, pa.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                event_id,
                limit,
                offset,
            )
        return [record_to_dict(row) for row in rows]

    async def get_entity_profile(self, entity: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            profile = await conn.fetchrow(
                "SELECT * FROM entity_profiles WHERE LOWER(entity_text) = LOWER($1)",
                entity,
            )
            if profile is None:
                profile = await conn.fetchrow(
                    """
                    SELECT
                        $1::text AS entity_text,
                        MAX(entity_type) AS entity_type,
                        ARRAY[$1::text] AS aliases,
                        COUNT(*)::int AS mention_frequency,
                        AVG(pa.threat_score) AS risk_trend,
                        ARRAY_REMOVE(ARRAY_AGG(DISTINCT ea.event_id), NULL) AS associated_events,
                        ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.id), NULL) AS associated_relationships,
                        MAX(pa.published_at) AS last_seen,
                        NOW() AS created_at,
                        NOW() AS updated_at
                    FROM extracted_entities ee
                    LEFT JOIN processed_articles pa ON pa.id = ee.article_id
                    LEFT JOIN event_articles ea ON ea.article_id = pa.id
                    LEFT JOIN relationships r
                        ON LOWER(r.source_entity) = LOWER(ee.entity_text)
                        OR LOWER(r.target_entity) = LOWER(ee.entity_text)
                    WHERE LOWER(ee.entity_text) = LOWER($1)
                    HAVING COUNT(*) > 0
                    LIMIT 1
                    """,
                    entity,
                )
            if profile is None:
                return None
            events = await conn.fetch(
                """
                SELECT DISTINCT e.*
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                WHERE LOWER(ee.entity_text) = LOWER($1)
                ORDER BY e.last_seen DESC NULLS LAST
                LIMIT 20
                """,
                entity,
            )
            relationships = await conn.fetch(
                """
                SELECT *
                FROM relationships
                WHERE LOWER(source_entity) = LOWER($1) OR LOWER(target_entity) = LOWER($1)
                ORDER BY confidence DESC NULLS LAST, created_at DESC
                LIMIT 20
                """,
                entity,
            )
        payload = record_to_dict(profile)
        payload["associated_events_detail"] = [record_to_dict(row) for row in events]
        payload["associated_relationships_detail"] = [record_to_dict(row) for row in relationships]
        return payload

    async def get_entity_timeline(self, entity: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    TO_CHAR(DATE_TRUNC('day', pa.published_at), 'YYYY-MM-DD') AS bucket,
                    COUNT(*) AS mentions,
                    AVG(pa.threat_score) AS avg_risk,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT pa.topic), NULL) AS topics
                FROM extracted_entities ee
                JOIN processed_articles pa ON pa.id = ee.article_id
                WHERE LOWER(ee.entity_text) = LOWER($1)
                GROUP BY DATE_TRUNC('day', pa.published_at)
                ORDER BY DATE_TRUNC('day', pa.published_at)
                """,
                entity,
            )
        return [record_to_dict(row) for row in rows]

    async def create_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO reports (
                    title, executive_summary, key_actors, key_events, threat_assessment,
                    confidence_score, recommendations, source_article_ids, created_by
                )
                VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7::jsonb, $8, $9)
                RETURNING *
                """,
                payload["title"],
                payload["executive_summary"],
                json.dumps(payload["key_actors"]),
                json.dumps(payload["key_events"]),
                payload["threat_assessment"],
                payload["confidence_score"],
                json.dumps(payload["recommendations"]),
                payload["source_article_ids"],
                payload.get("created_by"),
            )
        return record_to_dict(row)

    async def get_report_context(
        self,
        topic: str | None,
        entity: str | None,
        event_id: int | None,
        limit: int,
    ) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            if event_id:
                articles = await conn.fetch(
                    """
                    SELECT pa.*
                    FROM event_articles ea
                    JOIN processed_articles pa ON pa.id = ea.article_id
                    WHERE ea.event_id = $1
                    ORDER BY pa.threat_score DESC NULLS LAST
                    LIMIT $2
                    """,
                    event_id,
                    limit,
                )
            elif entity:
                articles = await conn.fetch(
                    """
                    SELECT DISTINCT pa.*
                    FROM extracted_entities ee
                    JOIN processed_articles pa ON pa.id = ee.article_id
                    WHERE LOWER(ee.entity_text) = LOWER($1)
                    ORDER BY pa.threat_score DESC NULLS LAST
                    LIMIT $2
                    """,
                    entity,
                    limit,
                )
            elif topic:
                articles = await conn.fetch(
                    """
                    SELECT *
                    FROM processed_articles
                    WHERE topic = $1
                    ORDER BY threat_score DESC NULLS LAST, published_at DESC NULLS LAST
                    LIMIT $2
                    """,
                    topic,
                    limit,
                )
            else:
                articles = await conn.fetch(
                    """
                    SELECT *
                    FROM processed_articles
                    ORDER BY threat_score DESC NULLS LAST, published_at DESC NULLS LAST
                    LIMIT $1
                    """,
                    limit,
                )
            actors = await conn.fetch(
                """
                SELECT entity_text, entity_type, COUNT(*) AS mentions, AVG(confidence) AS confidence
                FROM extracted_entities
                GROUP BY entity_text, entity_type
                ORDER BY mentions DESC
                LIMIT 10
                """
            )
            events = await conn.fetch(
                """
                SELECT *
                FROM events
                ORDER BY risk_score DESC NULLS LAST, last_seen DESC NULLS LAST
                LIMIT 10
                """
            )
        return {
            "articles": [record_to_dict(row) for row in articles],
            "actors": [record_to_dict(row) for row in actors],
            "events": [record_to_dict(row) for row in events],
        }

    async def create_watchlist(
        self,
        name: str,
        description: str | None,
        owner_id: int | None,
        entities: list[str],
    ) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                watchlist = await conn.fetchrow(
                    """
                    INSERT INTO watchlists (name, description, owner_id)
                    VALUES ($1, $2, $3)
                    RETURNING *
                    """,
                    name,
                    description,
                    owner_id,
                )
                for entity in entities:
                    await conn.execute(
                        """
                        INSERT INTO watchlist_entities (watchlist_id, entity_text)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        watchlist["id"],
                        entity.strip(),
                    )
                rows = await conn.fetch(
                    "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                    watchlist["id"],
                )
        payload = record_to_dict(watchlist)
        payload["entities"] = [row["entity_text"] for row in rows]
        return payload

    async def list_watchlists(self, owner_id: int | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT w.*, ARRAY_REMOVE(ARRAY_AGG(we.entity_text ORDER BY we.entity_text), NULL) AS entities
                FROM watchlists w
                LEFT JOIN watchlist_entities we ON we.watchlist_id = w.id
                WHERE ($1::int IS NULL OR w.owner_id = $1)
                GROUP BY w.id
                ORDER BY w.updated_at DESC
                LIMIT $2 OFFSET $3
                """,
                owner_id,
                limit,
                offset,
            )
        return [record_to_dict(row) for row in rows]

    async def create_alert(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO alerts (watchlist_id, entity_text, event_id, alert_type, message, risk_score)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                payload.get("watchlist_id"),
                payload.get("entity_text"),
                payload.get("event_id"),
                payload["alert_type"],
                payload["message"],
                payload["risk_score"],
            )
        return record_to_dict(row)

    async def get_timeline(
        self,
        entity: str | None,
        event_id: int | None,
        timeline_type: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            if timeline_type == "entity" and entity:
                rows = await conn.fetch(
                    """
                    SELECT pa.published_at AS timestamp, 'entity_mention' AS type, pa.title, pa.threat_score AS risk_score, pa.article_id
                    FROM extracted_entities ee
                    JOIN processed_articles pa ON pa.id = ee.article_id
                    WHERE LOWER(ee.entity_text) = LOWER($1)
                    ORDER BY pa.published_at DESC NULLS LAST
                    LIMIT $2
                    """,
                    entity,
                    limit,
                )
            elif timeline_type == "event" and event_id:
                rows = await conn.fetch(
                    """
                    SELECT pa.published_at AS timestamp, 'event_article' AS type, pa.title, pa.threat_score AS risk_score, pa.article_id
                    FROM event_articles ea
                    JOIN processed_articles pa ON pa.id = ea.article_id
                    WHERE ea.event_id = $1
                    ORDER BY pa.published_at DESC NULLS LAST
                    LIMIT $2
                    """,
                    event_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT COALESCE(last_seen, updated_at) AS timestamp, 'risk_evolution' AS type, title, risk_score, id AS event_id
                    FROM events
                    ORDER BY COALESCE(last_seen, updated_at) DESC
                    LIMIT $1
                    """,
                    limit,
                )
        return [record_to_dict(row) for row in rows]

    async def search_context(self, es_client, question: str, limit: int) -> list[dict[str, Any]]:
        response = await es_client.search(
            index="processed_articles",
            body={
                "size": limit,
                "query": {
                    "multi_match": {
                        "query": question,
                        "fields": ["title^3", "summary^2", "content", "source", "topic", "entities"],
                        "fuzziness": "AUTO",
                    }
                },
            },
        )
        return [hit["_source"] for hit in response["hits"]["hits"]]

    async def expand_graph(self, entity: str, depth: int, limit: int) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM relationships
                WHERE confidence >= 0.70
                    AND (LOWER(source_entity) = LOWER($1) OR LOWER(target_entity) = LOWER($1))
                ORDER BY confidence DESC NULLS LAST, created_at DESC
                LIMIT $2
                """,
                entity,
                limit * max(depth, 1),
            )
        nodes = {entity: {"id": entity, "label": entity}}
        edges = []
        for row in rows:
            source = row["source_entity"]
            target = row["target_entity"]
            nodes.setdefault(source, {"id": source, "label": source})
            nodes.setdefault(target, {"id": target, "label": target})
            edges.append(record_to_dict(row))
        return {"nodes": list(nodes.values()), "edges": edges}

    async def audit(self, user_id: int | None, action: str, resource: str, metadata: dict[str, Any]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (user_id, action, resource, metadata)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                user_id,
                action,
                resource,
                json.dumps(metadata),
            )
