from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/entities", tags=["Entities"])


@router.get("/")
async def get_entities(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    entity_text,
                    entity_type,
                    COUNT(*) AS mentions,
                    AVG(confidence) AS avg_confidence
                FROM extracted_entities
                GROUP BY entity_text, entity_type
                ORDER BY mentions DESC,
                         avg_confidence DESC
                LIMIT $1
                """,
                limit,
            )

        return [
            {
                "entity": row["entity_text"],
                "type": row["entity_type"],
                "mentions": row["mentions"],
                "avg_confidence": float(row["avg_confidence"] or 0),
            }
            for row in rows
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Entity list error: {str(e)}"
        )


@router.get("/{entity_name}")
async def get_entity_profile(entity_name: str, request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:

            profile = await conn.fetchrow(
                """
                SELECT *
                FROM entity_profiles
                WHERE LOWER(entity_text) = LOWER($1)
                """,
                entity_name,
            )

            if not profile:
                raise HTTPException(
                    status_code=404,
                    detail="Entity not found"
                )

        return dict(profile)

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Entity profile error: {str(e)}"
        )


@router.get("/{entity_name}/articles")
async def get_entity_articles(entity_name: str, request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT DISTINCT
                    p.id,
                    p.title,
                    p.topic,
                    p.risk_level,
                    p.threat_score,
                    p.published_at
                FROM processed_articles p
                JOIN extracted_entities e
                    ON p.id = e.article_id
                WHERE LOWER(e.entity_text) = LOWER($1)
                ORDER BY p.published_at DESC NULLS LAST
                LIMIT 50
                """,
                entity_name,
            )

        return [dict(row) for row in rows]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Entity article lookup error: {str(e)}"
        )


@router.get("/{entity_name}/relationships")
async def get_entity_relationships(entity_name: str, request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT
                    source_entity,
                    target_entity,
                    relationship_type,
                    confidence,
                    observed_at
                FROM relationships
                WHERE LOWER(source_entity) = LOWER($1)
                   OR LOWER(target_entity) = LOWER($1)
                ORDER BY confidence DESC,
                         observed_at DESC
                LIMIT 100
                """,
                entity_name,
            )

        return [dict(row) for row in rows]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Entity relationship lookup error: {str(e)}"
        )