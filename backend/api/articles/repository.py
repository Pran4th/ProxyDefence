from typing import Any

ALLOWED_FILTERS = {"sentiment", "topic", "risk_level"}


class ArticleRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def list_articles(
        self,
        limit: int,
        offset: int,
        sentiment: str | None = None,
        topic: str | None = None,
        risk_level: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = {"sentiment": sentiment, "topic": topic, "risk_level": risk_level}
        conditions = []
        params = []

        for col, val in filters.items():
            if val is not None and col in ALLOWED_FILTERS:
                params.append(val)
                conditions.append(f"{col} = ${len(params)}")

        params.extend([limit, offset])

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        else:
            where_clause = ""

        async with self.pool.acquire() as conn:
            articles = await conn.fetch(
                f"""
                SELECT *
                FROM processed_articles
                {where_clause}
                ORDER BY published_at DESC NULLS LAST,
                         created_at DESC
                LIMIT ${len(params) - 1}
                OFFSET ${len(params)}
                """,
                *params,
            )

        return [dict(article) for article in articles]

    async def get_article(self, article_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            article = await conn.fetchrow(
                "SELECT * FROM processed_articles WHERE id = $1",
                article_id,
            )
        return dict(article) if article else None

    async def get_article_entities(self, article_id: int) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_text, entity_type, confidence, created_at
                FROM extracted_entities
                WHERE article_id = $1
                ORDER BY confidence DESC NULLS LAST, entity_text
                """,
                article_id,
            )
        return [dict(row) for row in rows]

    async def get_article_energy_context(self, article_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT locations, infrastructure, organizations, commodities, infrastructure_events, context FROM article_energy_enrichments WHERE article_id = $1",
                article_id,
            )
        return dict(row) if row else None
