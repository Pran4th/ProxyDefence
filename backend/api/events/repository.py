from typing import Any

from backend.api.common.schema import record_to_dict


class EventRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

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
                SELECT pa.id, pa.title, pa.topic, pa.threat_score, ea.similarity_score
                FROM event_articles ea
                JOIN processed_articles pa ON pa.id = ea.article_id
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
