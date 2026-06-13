from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("/")
async def get_articles(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sentiment: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            conditions = []
            params = []

            if sentiment:
                params.append(sentiment)
                conditions.append(f"sentiment = ${len(params)}")

            if topic:
                params.append(topic)
                conditions.append(f"topic = ${len(params)}")

            if risk_level:
                params.append(risk_level)
                conditions.append(f"risk_level = ${len(params)}")

            params.extend([limit, offset])

            where_clause = (
                f"WHERE {' AND '.join(conditions)}"
                if conditions
                else ""
            )

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

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


@router.get("/{id}")
async def get_article(id: int, request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:

            article = await conn.fetchrow(
                """
                SELECT *
                FROM processed_articles
                WHERE id = $1
                """,
                id,
            )

        if not article:
            raise HTTPException(
                status_code=404,
                detail="Article not found"
            )

        return dict(article)

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


@router.get("/{id}/entities")
async def get_article_entities(id: int, request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:

            article_exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM processed_articles
                    WHERE id = $1
                )
                """,
                id,
            )

            if not article_exists:
                raise HTTPException(
                    status_code=404,
                    detail="Article not found"
                )

            rows = await conn.fetch(
                """
                SELECT
                    entity_text,
                    entity_type,
                    confidence,
                    created_at
                FROM extracted_entities
                WHERE article_id = $1
                ORDER BY confidence DESC NULLS LAST,
                         entity_text
                """,
                id,
            )

        return [dict(row) for row in rows]

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Entity lookup error: {str(e)}"
        )