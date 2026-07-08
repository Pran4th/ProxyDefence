import json
from typing import Any

from backend.api.common.schema import record_to_dict


class ReportRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

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

    async def get_report(self, report_id: int, created_by: int | None = None) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            report = await conn.fetchrow(
                """
                SELECT * FROM reports
                WHERE id = $1 AND ($2::int IS NULL OR created_by = $2)
                """,
                report_id,
                created_by,
            )
        return record_to_dict(report) if report else None

    async def list_reports(self, limit: int, offset: int, created_by: int | None = None) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM reports
                WHERE ($3::int IS NULL OR created_by = $3)
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
                created_by,
            )
        return [record_to_dict(row) for row in rows]

    async def get_report_context(
        self, topic: str | None, entity: str | None, event_id: int | None, limit: int
    ) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            if event_id:
                articles = await conn.fetch(
                    """
                    SELECT pa.* FROM event_articles ea
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
                    SELECT DISTINCT pa.* FROM extracted_entities ee
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
                    SELECT * FROM processed_articles
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
                    SELECT * FROM processed_articles
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
                SELECT * FROM events
                ORDER BY risk_score DESC NULLS LAST, last_seen DESC NULLS LAST
                LIMIT 10
                """
            )

        return {
            "articles": [record_to_dict(row) for row in articles],
            "actors": [record_to_dict(row) for row in actors],
            "events": [record_to_dict(row) for row in events],
        }

    async def load_case_report_data(self, case_id: int) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            case = await conn.fetchrow("SELECT * FROM cases WHERE id = $1", case_id)
            if case is None:
                raise ValueError(f"Case {case_id} not found")

            items = await conn.fetch(
                "SELECT item_type, item_id FROM case_items WHERE case_id = $1",
                case_id,
            )

            event_ids = [item["item_id"] for item in items if item["item_type"] == "event"]
            alert_ids = [item["item_id"] for item in items if item["item_type"] == "alert"]

            events = []
            if event_ids:
                events = await conn.fetch(
                    """
                    SELECT id, title, risk_score, risk_level, confidence
                    FROM events WHERE id = ANY($1::integer[])
                    ORDER BY risk_score DESC NULLS LAST
                    """,
                    event_ids,
                )

            alerts = []
            if alert_ids:
                alerts = await conn.fetch(
                    """
                    SELECT id, entity_text, risk_score, alert_type
                    FROM alerts WHERE id = ANY($1::integer[])
                    ORDER BY risk_score DESC NULLS LAST
                    """,
                    alert_ids,
                )

            entities = []
            if event_ids:
                entities = await conn.fetch(
                    """
                    SELECT DISTINCT entity_text, entity_type, mention_count
                    FROM event_entities WHERE event_id = ANY($1::integer[])
                    ORDER BY mention_count DESC
                    LIMIT 10
                    """,
                    event_ids,
                )

            articles = []
            if event_ids:
                articles = await conn.fetch(
                    """
                    SELECT DISTINCT pa.id, pa.title, pa.threat_score, pa.topic
                    FROM processed_articles pa
                    JOIN event_articles ea ON ea.article_id = pa.id
                    WHERE ea.event_id = ANY($1::integer[])
                    ORDER BY pa.threat_score DESC NULLS LAST
                    LIMIT 20
                    """,
                    event_ids,
                )

        return {
            "case": case,
            "items": items,
            "events": events,
            "alerts": alerts,
            "entities": entities,
            "articles": articles,
        }
