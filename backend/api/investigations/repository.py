import json
from typing import Any

from backend.api.common.db_helpers import fetch_all, fetch_one
from backend.api.common.schema import record_to_dict


class InvestigationRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    # --- Cases ---

    async def create_case(
        self, title: str, description: str | None, owner_id: int | None, priority: str = "medium"
    ) -> dict[str, Any]:
        allowed_priorities = {"low", "medium", "high", "critical"}
        if priority not in allowed_priorities:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {allowed_priorities}")

        return await fetch_one(
            self.pool,
            "INSERT INTO cases (title, description, owner_id, priority) VALUES ($1, $2, $3, $4) RETURNING *",
            title, description, owner_id, priority,
        )

    async def get_case(self, case_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            case = await conn.fetchrow("SELECT * FROM cases WHERE id = $1", case_id)
            if case is None:
                return None

            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

            notes = await conn.fetch(
                """
                SELECT * FROM case_notes
                WHERE case_id = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                case_id,
            )

            notes_count = await conn.fetchval(
                "SELECT COUNT(*) FROM case_notes WHERE case_id = $1",
                case_id,
            )

            reports = await conn.fetch(
                "SELECT id, title, created_at FROM reports WHERE source_case_id = $1 ORDER BY created_at DESC",
                case_id,
            )

        payload = record_to_dict(case)
        payload["items"] = [record_to_dict(row) for row in items]
        payload["notes"] = [record_to_dict(row) for row in notes]
        payload["notes_count"] = notes_count
        payload["reports"] = [record_to_dict(row) for row in reports]
        return payload

    async def list_cases(
        self, owner_id: int | None = None, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.*,
                    COUNT(DISTINCT ci.item_id) AS item_count,
                    COUNT(DISTINCT cn.id) AS notes_count,
                    COUNT(DISTINCT r.id) AS report_count
                FROM cases c
                LEFT JOIN case_items ci ON ci.case_id = c.id
                LEFT JOIN case_notes cn ON cn.case_id = c.id
                LEFT JOIN reports r ON r.source_case_id = c.id
                WHERE ($1::int IS NULL OR c.owner_id = $1)
                    AND ($2::varchar IS NULL OR c.status = $2)
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT $3 OFFSET $4
                """,
                owner_id,
                status,
                limit,
                offset,
            )
        return [record_to_dict(row) for row in rows]

    async def add_case_item(self, case_id: int, item_type: str, item_id: int) -> dict[str, Any]:
        allowed_types = {"alert", "event", "article", "entity", "copilot_message"}
        if item_type not in allowed_types:
            raise ValueError(f"Invalid item_type: {item_type}. Must be one of {allowed_types}")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO case_items (case_id, item_type, item_id)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                case_id,
                item_type,
                item_id,
            )
            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

        return {"case_id": case_id, "items": [record_to_dict(row) for row in items]}

    async def remove_case_item(self, case_id: int, item_type: str, item_id: int) -> dict[str, Any]:
        allowed_types = {"alert", "event", "article", "entity", "copilot_message"}
        if item_type not in allowed_types:
            raise ValueError(f"Invalid item_type: {item_type}. Must be one of {allowed_types}")

        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM case_items WHERE case_id = $1 AND item_type = $2 AND item_id = $3",
                case_id,
                item_type,
                item_id,
            )
            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

        return {"case_id": case_id, "items": [record_to_dict(row) for row in items]}

    async def add_case_note(self, case_id: int, note_text: str, created_by: int | None) -> dict[str, Any]:
        return await fetch_one(
            self.pool,
            "INSERT INTO case_notes (case_id, note_text, created_by) VALUES ($1, $2, $3) RETURNING *",
            case_id, note_text, created_by,
        )

    async def list_case_notes(self, case_id: int, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await fetch_all(
            self.pool,
            "SELECT * FROM case_notes WHERE case_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            case_id, limit, offset,
        )

    # --- Reports ---

    async def create_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await fetch_one(
            self.pool,
            """
            INSERT INTO reports (
                title, executive_summary, key_actors, key_events, threat_assessment,
                confidence_score, recommendations, source_article_ids, source_case_id, created_by
            )
            VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7::jsonb, $8, $9, $10)
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
            payload.get("source_case_id"),
            payload.get("created_by"),
        )

    async def get_report(self, report_id: int, created_by: int | None = None) -> dict[str, Any] | None:
        return await fetch_one(
            self.pool,
            "SELECT * FROM reports WHERE id = $1 AND ($2::int IS NULL OR created_by = $2)",
            report_id, created_by,
        )

    async def list_reports(self, limit: int, offset: int, created_by: int | None = None) -> list[dict[str, Any]]:
        return await fetch_all(
            self.pool,
            """
            SELECT * FROM reports
            WHERE ($3::int IS NULL OR created_by = $3)
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset, created_by,
        )

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
