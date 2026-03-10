from fastapi import APIRouter, HTTPException
from backend.api_service.main import app

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
async def get_analytics_summary():
    try:
        async with app.state.pg_pool.acquire() as conn:
            total_articles = await conn.fetchval("SELECT COUNT(*) FROM processed_articles")

            last_24h = await conn.fetchval(
                "SELECT COUNT(*) FROM processed_articles WHERE published_at >= NOW() - INTERVAL '24 hours'"
            )

            avg_confidence = await conn.fetchval("SELECT AVG(confidence) FROM processed_articles")

            sentiment_dist = await conn.fetch(
                "SELECT sentiment, COUNT(*) as count FROM processed_articles GROUP BY sentiment"
            )

            sentiment_map = {row['sentiment']: row['count'] for row in sentiment_dist}

        return {
            "total_articles": total_articles or 0,
            "articles_last_24h": last_24h or 0,
            "avg_confidence": avg_confidence or 0.0,
            "sentiment_distribution": sentiment_map
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/graph")
async def get_attack_graph():
    try:
        async with app.state.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT pa.id, pa.title, ee.entity_text, ee.entity_type
                FROM processed_articles pa
                JOIN extracted_entities ee ON pa.id = ee.article_id
                WHERE pa.sentiment = 'negative'
                AND pa.published_at >= NOW() - INTERVAL '7 days'
                AND ee.entity_type IN ('LOC', 'ORG', 'MISC')
            """)

            if not rows:
                return {
                    "nodes": [
                        {"id": "Iran", "group": "Aggressor", "val": 20},
                        {"id": "Israel", "group": "Defender", "val": 20},
                        {"id": "Saudi Arabia", "group": "Target", "val": 15},
                        {"id": "USA", "group": "Superpower", "val": 30}
                    ],
                    "links": [
                        {"source": "Iran", "target": "Israel", "value": 10},
                        {"source": "USA", "target": "Israel", "value": 5}
                    ]
                }

        return {"nodes": [], "links": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")