from typing import Any

from backend.api.common.schema import record_to_dict


class AnalyticsRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def get_dashboard_stats(self) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            events_count = await conn.fetchval("SELECT COUNT(*) FROM events")
            alerts_count = await conn.fetchval("SELECT COUNT(*) FROM alerts")
            open_alerts_count = await conn.fetchval("SELECT COUNT(*) FROM alerts WHERE status = 'open'")
            investigating_alerts = await conn.fetchval("SELECT COUNT(*) FROM alerts WHERE status = 'investigating'")
            closed_alerts = await conn.fetchval("SELECT COUNT(*) FROM alerts WHERE status = 'closed'")
            watchlists_count = await conn.fetchval("SELECT COUNT(*) FROM watchlists")
            cases_count = await conn.fetchval("SELECT COUNT(*) FROM cases")
            reports_count = await conn.fetchval("SELECT COUNT(*) FROM reports")
            high_risk_events = await conn.fetchval("SELECT COUNT(*) FROM events WHERE risk_score >= 70")
            critical_events = await conn.fetchval("SELECT COUNT(*) FROM events WHERE LOWER(risk_level) = 'critical'")
            avg_risk_score = await conn.fetchval("SELECT COALESCE(AVG(risk_score), 0) FROM events")

            latest_event = await conn.fetchrow(
                """
                SELECT id, title, risk_score, risk_level, last_seen
                FROM events
                ORDER BY risk_score DESC NULLS LAST
                LIMIT 1
                """
            )

            recent_reports = await conn.fetch(
                """
                SELECT id, title, created_at
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
            "top_event": record_to_dict(latest_event) if latest_event else None,
            "recent_reports": [record_to_dict(row) for row in recent_reports],
            "risk_distribution": record_to_dict(risk_distribution) if risk_distribution else {},
        }

    async def get_threat_analytics(self) -> dict:
        async with self.pool.acquire() as conn:
            risk_rows = await conn.fetch(
                """
                SELECT risk_level, COUNT(*) AS count
                FROM events
                GROUP BY risk_level
                ORDER BY count DESC
                """
            )
            topic_rows = await conn.fetch(
                """
                SELECT COALESCE(topic, 'unclassified') AS topic, COUNT(*) AS count
                FROM events
                GROUP BY COALESCE(topic, 'unclassified')
                ORDER BY count DESC
                LIMIT 10
                """
            )

        return {
            "risk_distribution": [
                {"risk_level": row["risk_level"], "count": row["count"]}
                for row in risk_rows
            ],
            "topic_distribution": [
                {"topic": row["topic"], "count": row["count"]}
                for row in topic_rows
            ],
        }

    async def get_summary(self) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
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

    async def get_attack_graph(self) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source_entity, target_entity, relationship_type, confidence
                FROM relationships
                WHERE created_at >= NOW() - INTERVAL '14 days'
                ORDER BY confidence DESC NULLS LAST
                LIMIT 100
                """
            )

            if not rows:
                return {
                    "nodes": [
                        {"id": "Iran", "group": "Aggressor", "val": 20},
                        {"id": "Israel", "group": "Defender", "val": 20},
                        {"id": "Saudi Arabia", "group": "Target", "val": 15},
                        {"id": "USA", "group": "Superpower", "val": 30},
                    ],
                    "links": [
                        {"source": "Iran", "target": "Israel", "value": 10},
                        {"source": "USA", "target": "Israel", "value": 5},
                    ],
                }

        nodes = {}
        links = []
        for row in rows:
            source = row["source_entity"]
            target = row["target_entity"]
            nodes[source] = {"id": source, "group": "Actor", "val": nodes.get(source, {}).get("val", 8) + 2}
            nodes[target] = {"id": target, "group": "Actor", "val": nodes.get(target, {}).get("val", 8) + 2}
            links.append({
                "source": source,
                "target": target,
                "value": round(row["confidence"] or 0.5, 2),
                "type": row["relationship_type"],
            })

        return {"nodes": list(nodes.values()), "links": links}

    async def get_timeseries(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
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

    async def get_top_entities(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
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

    async def get_topic_breakdown(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
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
