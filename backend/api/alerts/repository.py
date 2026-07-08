from typing import Any

from backend.api.common.schema import record_to_dict


class AlertRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def list_alerts(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM alerts
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    status,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM alerts
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )
        return [record_to_dict(row) for row in rows]

    async def get_alert(self, alert_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            alert = await conn.fetchrow(
                """
                SELECT a.*, w.name AS watchlist_name, e.title AS event_title
                FROM alerts a
                LEFT JOIN watchlists w ON w.id = a.watchlist_id
                LEFT JOIN events e ON e.id = a.event_id
                WHERE a.id = $1
                """,
                alert_id,
            )
        return record_to_dict(alert) if alert else None

    async def update_alert_status(self, alert_id: int, status: str) -> dict[str, Any] | None:
        allowed_statuses = {"open", "investigating", "escalated", "closed"}
        if status not in allowed_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {allowed_statuses}")

        async with self.pool.acquire() as conn:
            alert = await conn.fetchrow(
                "UPDATE alerts SET status = $1 WHERE id = $2 RETURNING *",
                status,
                alert_id,
            )
        return record_to_dict(alert) if alert else None

    async def generate_alerts(self) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            potential_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM watchlist_entities we
                JOIN event_entities ee ON LOWER(we.entity_text) = LOWER(ee.entity_text)
                JOIN events e ON e.id = ee.event_id
                """
            )

            created_rows = await conn.fetch(
                """
                INSERT INTO alerts (watchlist_id, entity_text, event_id, alert_type, message, risk_score)
                SELECT
                    we.watchlist_id, ee.entity_text, ee.event_id,
                    'entity_match',
                    'Watchlist match detected for ' || ee.entity_text,
                    e.risk_score
                FROM watchlist_entities we
                JOIN event_entities ee ON LOWER(we.entity_text) = LOWER(ee.entity_text)
                JOIN events e ON e.id = ee.event_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM alerts a
                    WHERE a.watchlist_id = we.watchlist_id
                        AND a.event_id = ee.event_id
                        AND LOWER(a.entity_text) = LOWER(ee.entity_text)
                )
                RETURNING *
                """
            )

        alerts_created = len(created_rows)
        alerts_skipped = (potential_count or 0) - alerts_created
        return {"alerts_created": alerts_created, "alerts_skipped": alerts_skipped}
