from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.api_service.main import app

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("/")
async def get_articles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sentiment: Optional[str] = Query(None)
):
    try:
        async with app.state.pg_pool.acquire() as conn:
            if sentiment:
                articles = await conn.fetch(
                    "SELECT * FROM processed_articles WHERE sentiment = $1 ORDER BY published_at DESC LIMIT $2 OFFSET $3",
                    sentiment, limit, offset
                )
            else:
                articles = await conn.fetch(
                    "SELECT * FROM processed_articles ORDER BY published_at DESC LIMIT $1 OFFSET $2",
                    limit, offset
                )
        return [dict(article) for article in articles]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{article_id}")
async def get_article(article_id: int):
    try:
        async with app.state.pg_pool.acquire() as conn:
            article = await conn.fetchrow(
                "SELECT * FROM processed_articles WHERE article_id = $1",
                article_id
            )

        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        return dict(article)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")