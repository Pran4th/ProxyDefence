"""Unauthenticated preview data for the marketing/landing pages. Deliberately
minimal (a handful of safe, already-public article fields + aggregate stats)
so anonymous visitors see real platform output before signing in, without
exposing the full authenticated data model.
"""
from typing import Any

from fastapi import APIRouter, Request

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
