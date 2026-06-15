from fastapi import APIRouter, HTTPException, Request

from backend.api_service.repositories.intelligence import IntelligenceRepository

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_stats(request: Request):
    repo = IntelligenceRepository(request.app.state.pg_pool)
    return await repo.get_dashboard_stats()


@router.get("/threat-trends")
async def get_threat_trends(request: Request):
    repo = IntelligenceRepository(request.app.state.pg_pool)
    return await repo.get_threat_analytics()


@router.get("/summary")
async def get_analytics_summary(request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            total_articles = await conn.fetchval("SELECT COUNT(*) FROM processed_articles")

            last_24h = await conn.fetchval(
                "SELECT COUNT(*) FROM processed_articles WHERE published_at >= NOW() - INTERVAL '24 hours'"
            )

            avg_confidence = await conn.fetchval("SELECT AVG(confidence) FROM processed_articles")
            avg_threat_score = await conn.fetchval("SELECT AVG(threat_score) FROM processed_articles")
            high_risk_articles = await conn.fetchval(
                "SELECT COUNT(*) FROM processed_articles WHERE risk_level IN ('high', 'critical')"
            )

            sentiment_dist = await conn.fetch(
                "SELECT sentiment, COUNT(*) as count FROM processed_articles GROUP BY sentiment"
            )
            topic_rows = await conn.fetch(
                """
                SELECT COALESCE(topic, 'unclassified') AS topic, COUNT(*) AS count
                FROM processed_articles
                GROUP BY COALESCE(topic, 'unclassified')
                ORDER BY count DESC
                LIMIT 5
                """
            )

            sentiment_map = {row['sentiment']: row['count'] for row in sentiment_dist}
            top_topics = [{"topic": row["topic"], "count": row["count"]} for row in topic_rows]

        return {
            "total_articles": total_articles or 0,
            "articles_last_24h": last_24h or 0,
            "avg_confidence": avg_confidence or 0.0,
            "avg_threat_score": avg_threat_score or 0.0,
            "high_risk_articles": high_risk_articles or 0,
            "sentiment_distribution": sentiment_map,
            "top_topics": top_topics,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/graph")
async def get_attack_graph(request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT source_entity, target_entity, relationship_type, confidence
                FROM relationships
                WHERE created_at >= NOW() - INTERVAL '14 days'
                ORDER BY confidence DESC NULLS LAST
                LIMIT 100
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

        nodes = {}
        links = []
        for row in rows:
            source = row["source_entity"]
            target = row["target_entity"]
            nodes[source] = {"id": source, "group": "Actor", "val": nodes.get(source, {}).get("val", 8) + 2}
            nodes[target] = {"id": target, "group": "Actor", "val": nodes.get(target, {}).get("val", 8) + 2}
            links.append(
                {
                    "source": source,
                    "target": target,
                    "value": round(row["confidence"] or 0.5, 2),
                    "type": row["relationship_type"],
                }
            )

        return {"nodes": list(nodes.values()), "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")


@router.get("/dashboard-v2")
async def get_dashboard_stats(
    request: Request
):
    repo = IntelligenceRepository(
        request.app.state.pg_pool
    )

    return await repo.get_dashboard_stats()
@router.get("/timeseries")
async def get_timeseries(request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    TO_CHAR(DATE_TRUNC('day', published_at), 'YYYY-MM-DD') AS bucket,
                    COUNT(*) AS articles,
                    AVG(threat_score) AS avg_threat_score
                FROM processed_articles
                WHERE published_at >= NOW() - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('day', published_at)
                ORDER BY DATE_TRUNC('day', published_at)
                """
            )

        return [
            {
                "bucket": row["bucket"],
                "articles": row["articles"],
                "avg_threat_score": float(row["avg_threat_score"] or 0),
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeseries error: {str(e)}")


@router.get("/entities")
async def get_top_entities(request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_text, entity_type, COUNT(*) AS mentions, AVG(confidence) AS avg_confidence
                FROM extracted_entities
                GROUP BY entity_text, entity_type
                ORDER BY mentions DESC, avg_confidence DESC
                LIMIT 20
                """
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
        raise HTTPException(status_code=500, detail=f"Entity analytics error: {str(e)}")


@router.get("/topics")
async def get_topic_breakdown(request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT COALESCE(topic, 'unclassified') AS topic, COUNT(*) AS count, AVG(threat_score) AS avg_threat_score
                FROM processed_articles
                GROUP BY COALESCE(topic, 'unclassified')
                ORDER BY count DESC
                """
            )

        return [
            {
                "topic": row["topic"],
                "count": row["count"],
                "avg_threat_score": float(row["avg_threat_score"] or 0),
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Topic analytics error: {str(e)}")
