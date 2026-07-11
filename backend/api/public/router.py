"""Unauthenticated preview data for the marketing/landing pages, plus a real
public articles list/detail surface for anonymous visitors browsing the
intel feed. Both use narrow, explicit column allowlists (never SELECT *)
so anonymous access can never leak content/url/confidence or other
authenticated-only fields.
"""
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.articles.repository import ArticleRepository
from backend.api_service.rate_limit import limiter

router = APIRouter(prefix="/public", tags=["Public Preview"])


@router.get("/preview")
@limiter.limit("30/minute")
async def get_public_preview(request: Request) -> dict[str, Any]:
    pool = request.app.state.pg_pool
    async with pool.acquire() as conn:
        articles = await conn.fetch(
            """
            SELECT title, source, topic, summary, risk_level, threat_score,
                   sentiment, published_at
            FROM processed_articles
            WHERE risk_level IN ('high', 'critical')
            ORDER BY published_at DESC NULLS LAST
            LIMIT 3
            """
        )
        total_articles = await conn.fetchval("SELECT COUNT(*) FROM processed_articles")
        high_risk = await conn.fetchval(
            "SELECT COUNT(*) FROM processed_articles WHERE risk_level IN ('high', 'critical')"
        )
        avg_confidence = await conn.fetchval("SELECT AVG(confidence) FROM processed_articles")
        avg_threat = await conn.fetchval("SELECT AVG(threat_score) FROM processed_articles")
        trained_models = await conn.fetchval("SELECT COUNT(*) FROM ml.model_versions")
        datasets = await conn.fetchval("SELECT COUNT(*) FROM ml.dataset_catalog")

    return {
        "articles": [dict(a) for a in articles],
        "stats": {
            "total_articles": total_articles or 0,
            "high_risk_articles": high_risk or 0,
            "avg_confidence": float(avg_confidence or 0),
            "avg_threat_score": float(avg_threat or 0),
            "trained_models": trained_models or 0,
            "datasets": datasets or 0,
        },
    }


@router.get("/articles")
@limiter.limit("30/minute")
async def list_public_articles(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    sentiment: str | None = Query(None),
    topic: str | None = Query(None),
    risk_level: str | None = Query(None),
) -> list[dict[str, Any]]:
    repo = ArticleRepository(request.app.state.pg_pool)
    return await repo.list_public_articles(
        limit=limit, offset=offset, sentiment=sentiment, topic=topic, risk_level=risk_level,
    )


@router.get("/articles/{article_id}")
@limiter.limit("30/minute")
async def get_public_article(request: Request, article_id: int) -> dict[str, Any]:
    repo = ArticleRepository(request.app.state.pg_pool)
    article = await repo.get_public_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
