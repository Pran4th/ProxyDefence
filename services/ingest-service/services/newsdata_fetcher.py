import hashlib
from datetime import datetime

import requests

from backend.shared.logging_config import get_logger

from config import NEWSDATA_API_KEY, NEWSDATA_API_URL
from producer import producer

logger = get_logger(__name__)


def _normalize_published_at(pub_date: str) -> str:
    """NewsData.io returns pubDate as "YYYY-MM-DD HH:mm:ss" (UTC, space-separated,
    no timezone) which Elasticsearch's strict_date_optional_time mapping rejects.
    Normalize to ISO 8601 to match GNews's publishedAt format."""
    if not pub_date:
        return pub_date
    try:
        return datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S").isoformat() + "Z"
    except ValueError:
        return pub_date


def fetch_newsdata_news():
    """Fetch real-time world/energy/conflict news from NewsData.io — a second live
    source alongside GNews, published to the same `raw_articles` topic with the
    identical article schema so downstream consumers need zero changes."""
    if not NEWSDATA_API_KEY:
        logger.warning("newsdata_api_key_not_configured, skipping fetch")
        return {"message": "NEWSDATA_API_KEY not configured, skipped"}

    logger.info("fetching_newsdata_news")
    params = {
        "apikey": NEWSDATA_API_KEY,
        "q": "war OR conflict OR sanctions OR oil OR energy OR pipeline",
        "language": "en",
    }

    try:
        response = requests.get(NEWSDATA_API_URL, params=params, timeout=15)
        response.raise_for_status()
        articles = response.json().get("results", [])

        logger.info("newsdata_fetched_articles", count=len(articles))
        published = 0
        for article in articles:
            article_url = article.get("link", "")
            if not article_url:
                continue

            article_id = int(hashlib.sha256(article_url.encode("utf-8")).hexdigest(), 16) % 10**8
            source_names = article.get("source_name") or article.get("source_id") or "Unknown"
            content = article.get("content") or ""
            if not content or "ONLY AVAILABLE IN" in content:
                # free-tier NewsData.io locks full article text behind a paid plan and
                # returns a placeholder string instead of omitting the field
                content = article.get("description", "") or ""
            news_data = {
                "id": article_id,
                "title": article.get("title", ""),
                "content": content,
                "source": source_names,
                "published_at": _normalize_published_at(article.get("pubDate", "")),
                "url": article_url,
                "image": article.get("image_url", "") or "",
            }
            producer.produce("raw_articles", news_data)
            published += 1

        producer.poll(0.5)
        logger.info("newsdata_articles_published_to_kafka", count=published)
        return {"message": f"Fetched and sent {published} NewsData.io articles"}

    except Exception as e:
        logger.error("error_fetching_newsdata_news", error=str(e))
        return {"error": str(e)}
