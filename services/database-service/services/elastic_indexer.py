from typing import Any

from fastapi import HTTPException

from backend.shared.logging_config import get_logger

from db import get_es_client, close_es

logger = get_logger(__name__)


def index_article(data: dict[str, Any]) -> None:
    client = get_es_client()
    if client is None:
        logger.warning("es_skipping_index_unavailable")
        return

    document = {
        "article_id": data.get("id"),
        "title": data.get("title"),
        "content": data.get("content"),
        "source": data.get("source"),
        "published_at": data.get("published_at"),
        "ml_processed": data.get("ml_processed", False),
        "confidence": data.get("confidence", 0.0),
        "sentiment": data.get("sentiment", "neutral"),
        "summary": data.get("summary"),
        "topic": data.get("topic"),
        "threat_score": data.get("threat_score", 0.0),
        "geopolitical_risk": data.get("geopolitical_risk", 0.0),
        "risk_level": data.get("risk_level", "low"),
        "entities": [entity.get("text") for entity in data.get("entities", [])],
    }
    client.index(
        index="processed_articles",
        id=data.get("dedupe_key") or data.get("id"),
        document=document,
    )
    close_es(client)


def search_articles(q: str):
    client = get_es_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Search backend unavailable")

    response = client.search(
        index="processed_articles",
        body={
            "size": 20,
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": ["title^3", "summary^2", "content", "source", "topic"],
                    "fuzziness": "AUTO",
                }
            },
        },
    )
    close_es(client)

    return {
        "query": q,
        "total_results": response["hits"]["total"]["value"],
        "results": [hit["_source"] for hit in response["hits"]["hits"]],
    }
