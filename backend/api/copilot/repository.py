from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class CopilotRepository:
    def __init__(self, pool):
        self.pool = pool

    async def search_articles_by_ids(self, article_ids: list[int]) -> list[dict]:
        if not article_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM processed_articles WHERE id = ANY($1)",
                article_ids,
            )
            return [dict(r) for r in rows]

    async def get_entities_for_articles(self, article_ids: list[int]) -> list[dict]:
        if not article_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_text, entity_type, COUNT(*) AS mentions
                FROM extracted_entities
                WHERE article_id = ANY($1)
                  AND entity_type IN ('PERSON', 'ORG', 'GPE')
                GROUP BY entity_text, entity_type
                ORDER BY mentions DESC
                LIMIT 15
                """,
                article_ids,
            )
            return [dict(r) for r in rows]

    async def get_relationships_for_articles(self, article_ids: list[int]) -> list[dict]:
        if not article_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source_entity, target_entity, relationship_type, confidence, article_id
                FROM relationships
                WHERE article_id = ANY($1)
                ORDER BY confidence DESC
                LIMIT 15
                """,
                article_ids,
            )
            return [dict(r) for r in rows]

    async def get_events_for_articles(self, article_ids: list[int]) -> list[dict]:
        if not article_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT e.id, e.title, e.topic, e.risk_level, e.risk_score
                FROM events e
                JOIN event_articles ea ON e.id = ea.event_id
                WHERE ea.article_id = ANY($1)
                ORDER BY e.risk_score DESC
                LIMIT 10
                """,
                article_ids,
            )
            return [dict(r) for r in rows]

    async def get_entity_profiles(self, entity_names: list[str]) -> list[dict]:
        if not entity_names:
            return []
        async with self.pool.acquire() as conn:
            rows = []
            for name in entity_names:
                row = await conn.fetchrow(
                    """
                    SELECT entity_text, entity_type, mention_frequency,
                           risk_trend, associated_events, associated_relationships,
                           CARDINALITY(associated_events) AS event_count,
                           CARDINALITY(associated_relationships) AS relationship_count,
                           last_seen
                    FROM entity_profiles
                    WHERE LOWER(entity_text) = LOWER($1)
                    """,
                    name,
                )
                if row:
                    rows.append(dict(row))
            return rows

    async def get_energy_context_for_articles(self, article_ids: list[int]) -> list[dict]:
        if not article_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT aee.article_id, aee.context, aee.locations, aee.infrastructure,
                       aee.organizations, aee.commodities, aee.infrastructure_events
                FROM article_energy_enrichments aee
                WHERE aee.article_id = ANY($1)
                """,
                article_ids,
            )
            return [dict(r) for r in rows]

    async def get_risk_intelligence_summary(self) -> dict:
        async with self.pool.acquire() as conn:
            active_signals = await conn.fetchval(
                "SELECT COUNT(*) FROM energy.disruption_signals WHERE expires_at > NOW()"
            )
            high_signals = await conn.fetchval(
                """SELECT COUNT(*) FROM energy.disruption_signals
                   WHERE expires_at > NOW() AND severity IN ('high','critical')"""
            )
            avg_risk = await conn.fetchval(
                "SELECT COALESCE(AVG(score), 0) FROM energy.risk_scores WHERE expires_at > NOW()"
            )
            top_signals = await conn.fetch(
                """SELECT title, severity, risk_dimension, description
                   FROM energy.disruption_signals
                   WHERE expires_at > NOW() AND severity IN ('high','critical')
                   ORDER BY created_at DESC LIMIT 5"""
            )
            risk_by_dim = await conn.fetch(
                """SELECT dimension, COALESCE(AVG(score), 0) as avg_score
                   FROM energy.risk_scores WHERE expires_at > NOW()
                   GROUP BY dimension ORDER BY avg_score DESC"""
            )
            return {
                "active_signals": active_signals or 0,
                "high_severity_signals": high_signals or 0,
                "average_risk_score": round(float(avg_risk or 0), 4),
                "critical_signals": [dict(s) for s in top_signals],
                "risk_by_dimension": {
                    r["dimension"]: round(float(r["avg_score"]), 4) for r in risk_by_dim
                },
            }

    async def create_conversation(self, user_id: int | None, title: str) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO copilot_conversations (user_id, title)
                VALUES ($1, $2)
                RETURNING id
                """,
                user_id,
                title,
            )
            return row["id"]

    async def get_conversations(self, user_id: int, limit: int = 20) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, created_at, updated_at
                FROM copilot_conversations
                WHERE user_id = $1
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
            return [dict(r) for r in rows]

    async def add_message(self, conversation_id: int, role: str, content: str, metadata: dict | None = None) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO copilot_messages (conversation_id, role, content, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                conversation_id,
                role,
                content,
                metadata or {},
            )
            await conn.execute(
                "UPDATE copilot_conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )
            return row["id"]

    async def get_messages(self, conversation_id: int, limit: int = 50) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, content, metadata, created_at
                FROM copilot_messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                conversation_id,
                limit,
            )
            return [dict(r) for r in rows]
