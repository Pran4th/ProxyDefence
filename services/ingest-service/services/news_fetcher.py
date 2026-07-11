import hashlib
import json
from datetime import datetime, timedelta

import requests

from backend.shared.logging_config import get_logger

from config import NEWS_API_KEY, NEWS_API_URL
from producer import producer
from services.response_decoding import decode_json

logger = get_logger(__name__)


def fetch_real_news():
    """Fetch real news about conflict zones from GNews API."""
    logger.info("fetching_real_news")
    today = datetime.utcnow()

    params = {
        "q": '"world news" OR "conflict" OR "war"',
        "lang": "en",
        "max": 10,
        "apikey": NEWS_API_KEY,
        "from": (today - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    try:
        response = requests.get(NEWS_API_URL, params=params)
        response.raise_for_status()
        articles = decode_json(response).get("articles", [])

        logger.info("gnews_fetched_articles", count=len(articles))
        for article in articles:
            article_url = article.get("url", "")
            if not article_url:
                continue

            article_id = int(hashlib.sha256(article_url.encode("utf-8")).hexdigest(), 16) % 10**8
            news_data = {
                "id": article_id,
                "title": article.get("title", ""),
                "content": article.get("content", "") or article.get("description", ""),
                "source": article.get("source", {}).get("name", "Unknown"),
                "published_at": article.get("publishedAt", ""),
                "url": article.get("url", ""),
                "image": article.get("image", ""),
            }
            producer.produce("raw_articles", news_data)

        producer.poll(0.5)
        logger.info("articles_published_to_kafka", count=len(articles))
        return {"message": f"Fetched and sent {len(articles)} real news articles"}

    except Exception as e:
        logger.error("error_fetching_news", error=str(e))
        return {"error": str(e)}
