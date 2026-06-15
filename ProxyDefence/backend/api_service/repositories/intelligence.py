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

    async def get_event(
        self,
        event_id: int
    ) -> dict[str, Any] | None:

        async with self.pool.acquire() as conn:

            event = await conn.fetchrow(
                "SELECT * FROM events WHERE id = $1",
                event_id
            )

            if event is None:
                return None

            entities = await conn.fetch(
                """
                SELECT
                    entity_text,
                    entity_type,
                    mention_count,
                    avg_confidence
                FROM event_entities
                WHERE event_id = $1
                ORDER BY mention_count DESC,
                         avg_confidence DESC
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

        payload["entities"] = [
            record_to_dict(row)
            for row in entities
        ]

        payload["articles"] = [
            record_to_dict(row)
            for row in articles
        ]

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

    async def get_watchlist(
        self,
        watchlist_id: int
    ) -> dict[str, Any] | None:

        async with self.pool.acquire() as conn:

            watchlist = await conn.fetchrow(
                "SELECT * FROM watchlists WHERE id = $1",
                watchlist_id
            )

            if watchlist is None:
                return None

            entities = await conn.fetch(
                "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                watchlist_id,
            )

        payload = record_to_dict(watchlist)

        payload["entities"] = [
            row["entity_text"]
            for row in entities
        ]

        return payload

    async def delete_watchlist(
        self,
        watchlist_id: int
    ) -> dict[str, Any]:

        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "DELETE FROM watchlists WHERE id = $1 RETURNING id",
                watchlist_id,
            )

        deleted = result is not None

        return {
            "deleted": deleted,
            "watchlist_id": watchlist_id,
        }

    async def add_watchlist_entity(
        self,
        watchlist_id: int,
        entity_text: str
    ) -> list[str]:

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO watchlist_entities (watchlist_id, entity_text)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                watchlist_id,
                entity_text.strip(),
            )

            rows = await conn.fetch(
                "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                watchlist_id,
            )

        return [row["entity_text"] for row in rows]

    async def remove_watchlist_entity(
        self,
        watchlist_id: int,
        entity_text: str
    ) -> list[str]:

        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM watchlist_entities WHERE watchlist_id = $1 AND entity_text = $2",
                watchlist_id,
                entity_text.strip(),
            )

            rows = await conn.fetch(
                "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                watchlist_id,
            )

        return [row["entity_text"] for row in rows]

    async def list_alerts(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict[str, Any]]:

        async with self.pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT *
                    FROM alerts
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
                    SELECT *
                    FROM alerts
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )

        return [record_to_dict(row) for row in rows]

    async def get_alert(
        self,
        alert_id: int
    ) -> dict[str, Any] | None:

        async with self.pool.acquire() as conn:
            alert = await conn.fetchrow(
                """
                SELECT
                    a.*,
                    w.name AS watchlist_name,
                    e.title AS event_title
                FROM alerts a
                LEFT JOIN watchlists w ON w.id = a.watchlist_id
                LEFT JOIN events e ON e.id = a.event_id
                WHERE a.id = $1
                """,
                alert_id,
            )

        if alert is None:
            return None

        return record_to_dict(alert)

    async def update_alert_status(
        self,
        alert_id: int,
        status: str
    ) -> dict[str, Any] | None:

        allowed_statuses = {"open", "investigating", "escalated", "closed"}

        if status not in allowed_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {allowed_statuses}")

        async with self.pool.acquire() as conn:
            alert = await conn.fetchrow(
                "UPDATE alerts SET status = $1 WHERE id = $2 RETURNING *",
                status,
                alert_id,
            )

        if alert is None:
            return None

        return record_to_dict(alert)

    async def generate_alerts(self) -> dict[str, int]:
        """
        Automatically generate alerts by matching watchlist entities with event entities.
        
        Uses set-based SQL to avoid N+1 query pattern:
        1. Count all potential matches in one query
        2. Insert new non-duplicate alerts in a single INSERT...SELECT statement
        3. Calculate skipped as difference between potential and created
        
        Returns:
            {
                "alerts_created": count of newly created alerts,
                "alerts_skipped": count of duplicate matches encountered
            }
        """
        async with self.pool.acquire() as conn:
            
            # Count all potential matches
            potential_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM watchlist_entities we
                JOIN event_entities ee ON LOWER(we.entity_text) = LOWER(ee.entity_text)
                JOIN events e ON e.id = ee.event_id
                """
            )
            
            # Insert new alerts (excluding duplicates) in a single statement
            created_rows = await conn.fetch(
                """
                INSERT INTO alerts (watchlist_id, entity_text, event_id, alert_type, message, risk_score)
                SELECT
                    we.watchlist_id,
                    ee.entity_text,
                    ee.event_id,
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
        
        return {
            "alerts_created": alerts_created,
            "alerts_skipped": alerts_skipped
        }

    async def create_case(
        self,
        title: str,
        description: str | None,
        owner_id: int | None,
        priority: str = "medium"
    ) -> dict[str, Any]:

        allowed_priorities = {"low", "medium", "high", "critical"}
        
        if priority not in allowed_priorities:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {allowed_priorities}")

        async with self.pool.acquire() as conn:
            case = await conn.fetchrow(
                """
                INSERT INTO cases (title, description, owner_id, priority)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                title,
                description,
                owner_id,
                priority,
            )

        return record_to_dict(case)

    async def get_case(
        self,
        case_id: int
    ) -> dict[str, Any] | None:

        async with self.pool.acquire() as conn:
            case = await conn.fetchrow(
                "SELECT * FROM cases WHERE id = $1",
                case_id
            )

            if case is None:
                return None

            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items
                WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

            notes = await conn.fetch(
                """
                SELECT *
                FROM case_notes
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

        payload = record_to_dict(case)
        payload["items"] = [record_to_dict(row) for row in items]
        payload["notes"] = [record_to_dict(row) for row in notes]
        payload["notes_count"] = notes_count

        return payload

    async def list_cases(
        self,
        owner_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict[str, Any]]:

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    c.*,
                    COUNT(DISTINCT ci.item_id) AS item_count,
                    COUNT(DISTINCT cn.id) AS notes_count
                FROM cases c
                LEFT JOIN case_items ci ON ci.case_id = c.id
                LEFT JOIN case_notes cn ON cn.case_id = c.id
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

    async def add_case_item(
        self,
        case_id: int,
        item_type: str,
        item_id: int
    ) -> dict[str, Any]:

        allowed_types = {"alert", "event", "article", "entity"}

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
                FROM case_items
                WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

        return {
            "case_id": case_id,
            "items": [record_to_dict(row) for row in items]
        }

    async def remove_case_item(
        self,
        case_id: int,
        item_type: str,
        item_id: int
    ) -> dict[str, Any]:

        allowed_types = {"alert", "event", "article", "entity"}

        if item_type not in allowed_types:
            raise ValueError(f"Invalid item_type: {item_type}. Must be one of {allowed_types}")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM case_items
                WHERE case_id = $1 AND item_type = $2 AND item_id = $3
                """,
                case_id,
                item_type,
                item_id,
            )

            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items
                WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

        return {
            "case_id": case_id,
            "items": [record_to_dict(row) for row in items]
        }

    async def add_case_note(
        self,
        case_id: int,
        note_text: str,
        created_by: int | None
    ) -> dict[str, Any]:

        async with self.pool.acquire() as conn:
            note = await conn.fetchrow(
                """
                INSERT INTO case_notes (case_id, note_text, created_by)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                case_id,
                note_text,
                created_by,
            )

        return record_to_dict(note)

    async def list_case_notes(
        self,
        case_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict[str, Any]]:

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM case_notes
                WHERE case_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                case_id,
                limit,
                offset,
            )

        return [record_to_dict(row) for row in rows]

    async def generate_case_report(
        self,
        case_id: int,
        created_by: int | None = None
    ) -> dict[str, Any]:
        """
        Generate an intelligence brief from a case.

        Workflow:
        1. Load case and case items
        2. Extract linked alerts, events, entities, articles
        3. Build deterministic report components
        4. Store in reports table
        5. Return created report

        Returns:
        Full report record as dict
        """
        async with self.pool.acquire() as conn:
            case = await conn.fetchrow(
                "SELECT * FROM cases WHERE id = $1",
                case_id
            )
            if case is None:
                raise ValueError(f"Case {case_id} not found")

            items = await conn.fetch(
                """
                SELECT item_type, item_id
                FROM case_items
                WHERE case_id = $1
                """,
                case_id
            )

            event_ids = [item["item_id"] for item in items if item["item_type"] == "event"]
            alert_ids = [item["item_id"] for item in items if item["item_type"] == "alert"]
            
            events = []
            if event_ids:
                events = await conn.fetch(
                    """
                    SELECT id, title, risk_score, risk_level, confidence
                    FROM events
                    WHERE id = ANY($1::integer[])
                    ORDER BY risk_score DESC NULLS LAST
                    """,
                    event_ids
                )

            alerts = []
            if alert_ids:
                alerts = await conn.fetch(
                    """
                    SELECT id, entity_text, risk_score, alert_type
                    FROM alerts
                    WHERE id = ANY($1::integer[])
                    ORDER BY risk_score DESC NULLS LAST
                    """,
                    alert_ids
                )

            entities = []
            if event_ids:
                entities = await conn.fetch(
                    """
                    SELECT DISTINCT entity_text, entity_type, mention_count
                    FROM event_entities
                    WHERE event_id = ANY($1::integer[])
                    ORDER BY mention_count DESC
                    LIMIT 10
                    """,
                    event_ids
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
                    event_ids
                )

            executive_summary = self._build_executive_summary(
                case,
                events,
                alerts,
                entities
            )

            key_actors = self._build_key_actors(
                entities,
                alerts
            )

            key_events = self._build_key_events(events)

            threat_assessment = self._build_threat_assessment(
                events,
                alerts
            )

            recommendations = self._build_recommendations()

            confidence_score = self._build_confidence_score(events)
            
            source_article_ids = [article["id"] for article in articles]
            report = await conn.fetchrow(
                    """
                    INSERT INTO reports (
                        title,
                        executive_summary,
                        key_actors,
                        key_events,
                        threat_assessment,
                        confidence_score,
                        recommendations,
                        source_article_ids,
                        created_by
                    )
                    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7::jsonb, $8, $9)
                    RETURNING *
                    """,
                    f"Intelligence Brief - {case['title']}",
                    executive_summary,
                    json.dumps(key_actors),
                    json.dumps(key_events),
                    threat_assessment,
                    confidence_score,
                    json.dumps(recommendations),
                    source_article_ids,
                    created_by,
                )
            
            return record_to_dict(report)

    async def get_report(
        self,
        report_id: int
    ) -> dict[str, Any] | None:
        """Get a specific report."""
        async with self.pool.acquire() as conn:
            report = await conn.fetchrow(
                "SELECT * FROM reports WHERE id = $1",
                report_id
            )
            
            if report is None:
                return None

        return record_to_dict(report)

    async def list_reports(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict[str, Any]]:
        """List all reports ordered by creation date."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM reports
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

        return [record_to_dict(row) for row in rows]

    def _build_executive_summary(
        self,
        case: Any,
        events: list[dict],
        alerts: list[dict],
        entities: list[dict]
    ) -> str:
        """Generate executive summary from case data."""
        event_count = len(events)
        alert_count = len(alerts)
        entity_list = ", ".join([e["entity_text"] for e in entities[:3]])

        summary = f"Investigation '{case['title']}' contains {alert_count} alerts across {event_count} events"

        if entity_list:
            summary += f" involving {entity_list}"

        summary += "."

        return summary

    def _build_key_actors(
        self,
        entities: list[dict],
        alerts: list[dict]
    ) -> list[dict]:
        """Extract key actors (entities) from case."""
        key_actors = []

        for entity in entities[:5]:
            key_actors.append({
                "name": entity["entity_text"],
                "type": entity["entity_type"],
                "mentions": entity["mention_count"]
            })

        return key_actors

    def _build_key_events(
        self,
        events: list[dict]
    ) -> list[dict]:
        """Extract key events from case."""
        key_events = []

        for event in events:
            key_events.append({
                "id": event["id"],
                "title": event["title"],
                "risk_score": float(event["risk_score"] or 0),
                "risk_level": event["risk_level"]
            })

        return key_events

    def _build_threat_assessment(
        self,
        events: list[dict],
        alerts: list[dict]
    ) -> str:
        """Generate threat assessment based on risk scores."""
        if not events and not alerts:
            return "Insufficient data for threat assessment."

        max_risk = 0
        if events:
            max_risk = max([e["risk_score"] or 0 for e in events])
        if alerts:
            alert_risks = [a["risk_score"] or 0 for a in alerts]
            if alert_risks:
                max_risk = max(max_risk, max(alert_risks))

        if max_risk >= 75:
            return "Critical threat activity detected."
        elif max_risk >= 50:
            return "Elevated threat activity detected."
        else:
            return "Low to moderate threat activity."

    def _build_recommendations(self) -> list[str]:
        """Generate investigation recommendations."""
        return [
            "Continue monitoring watchlists for related entities",
            "Review all associated events for patterns",
            "Escalate if risk score increases",
            "Cross-reference with related investigations"
        ]

    def _build_confidence_score(
        self,
        events: list[dict]
    ) -> float:
        if not events:
            return 50.0
        
        confidences = [
            e["confidence"]
            for e in events
            if e["confidence"] is not None
        ]
        
        if not confidences:
            return 50.0
            
        return float(sum(confidences) / len(confidences))
    
    async def get_dashboard_stats(self) -> dict[str, Any]:
        """
        Dashboard statistics for frontend overview cards.
        """
        async with self.pool.acquire() as conn:
          events_count = await conn.fetchval(
            "SELECT COUNT(*) FROM events"
        )

          alerts_count = await conn.fetchval(
            "SELECT COUNT(*) FROM alerts"
        )

          open_alerts_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM alerts
            WHERE status = 'open'
            """
        )
          investigating_alerts = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM alerts
            WHERE status = 'investigating'
            """
        )
          closed_alerts = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM alerts
            WHERE status = 'closed'
            """
        )
          watchlists_count = await conn.fetchval(
            "SELECT COUNT(*) FROM watchlists"
        )

          cases_count = await conn.fetchval(
            "SELECT COUNT(*) FROM cases"
        )

          reports_count = await conn.fetchval(
            "SELECT COUNT(*) FROM reports"
        )

          high_risk_events = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM events
            WHERE risk_score >= 70
            """
        )
          critical_events = await conn.fetchval(
              """
    SELECT COUNT(*)
    FROM events
    WHERE LOWER(risk_level) = 'critical'
    """
        )

          avg_risk_score = await conn.fetchval(
            """
            SELECT COALESCE(AVG(risk_score), 0)
            FROM events
            """
        )

          latest_event = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                risk_score,
                risk_level,
                last_seen
            FROM events
            ORDER BY risk_score DESC NULLS LAST
            LIMIT 1
            """
        )
          top_event = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                risk_score,
                risk_level,
                last_seen
            FROM events
            ORDER BY risk_score DESC NULLS LAST
            LIMIT 1
            """
        )
          recent_reports = await conn.fetch(
            """
            SELECT
                id,
                title,
                created_at
            FROM reports
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
          risk_distribution = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE risk_level = 'low') AS low,
                COUNT(*) FILTER (WHERE risk_level = 'medium') AS medium,
                COUNT(*) FILTER (WHERE risk_level = 'high') AS high,
                COUNT(*) FILTER (WHERE risk_level = 'critical') AS critical
            FROM events
            """
        )
        return {
        "events": events_count,
        "alerts": alerts_count,
        "open_alerts": open_alerts_count,
        "investigating_alerts": investigating_alerts,
        "closed_alerts": closed_alerts,
        "watchlists": watchlists_count,
        "cases": cases_count,
        "reports": reports_count,
        "high_risk_events": high_risk_events,
        "critical_events": critical_events,
        "average_risk_score": round(float(avg_risk_score or 0), 2),
        "top_event": (
            record_to_dict(latest_event)
            if latest_event
            else None
        ),
        "recent_reports": [
            record_to_dict(row)
            for row in recent_reports
        ],
        "risk_distribution": (
            record_to_dict(risk_distribution)
            if risk_distribution
            else {}
        ),
    }
    async def get_threat_analytics(self) -> dict:
        async with self.pool.acquire() as conn:
            risk_rows = await conn.fetch(
            """
            SELECT
                risk_level,
                COUNT(*) AS count
            FROM events
            GROUP BY risk_level
            ORDER BY count DESC
            """
        )

            topic_rows = await conn.fetch(
            """
            SELECT
                COALESCE(topic, 'unclassified') AS topic,
                COUNT(*) AS count
            FROM events
            GROUP BY COALESCE(topic, 'unclassified')
            ORDER BY count DESC
            LIMIT 10
            """
        )

        return {
        "risk_distribution": [
            {
                "risk_level": row["risk_level"],
                "count": row["count"]
            }
            for row in risk_rows
        ],
        "topic_distribution": [
            {
                "topic": row["topic"],
                "count": row["count"]
            }
            for row in topic_rows
        ]
    }
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
                WHERE LOWER(source_entity) = LOWER($1) OR LOWER(target_entity) = LOWER($1)
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