import json
from pathlib import Path


def load_sample_articles() -> list[dict]:
    path = Path(__file__).resolve().parent.parent / "sample_data" / "articles.json"
    with open(path) as f:
        return json.load(f)


def sample_article_by_id(article_id: int) -> dict | None:
    articles = load_sample_articles()
    for a in articles:
        if a["id"] == article_id:
            return a
    return None


def sample_articles_by_sentiment(sentiment: str) -> list[dict]:
    return [a for a in load_sample_articles() if a.get("sentiment") == sentiment]


def sample_articles_by_risk(risk_level: str) -> list[dict]:
    return [a for a in load_sample_articles() if a.get("risk_level") == risk_level]
