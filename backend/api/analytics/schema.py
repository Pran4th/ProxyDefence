from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_articles: int = 0
    articles_last_24h: int = 0
    avg_confidence: float = 0.0
    avg_threat_score: float = 0.0
    high_risk_articles: int = 0
    sentiment_distribution: dict = {}
    top_topics: list[dict] = []
