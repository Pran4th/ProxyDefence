from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

THREAT_KEYWORDS = {
    "critical": ["nuclear", "chemical", "biological", "missile", "genocide", "airstrike"],
    "high": ["attack", "war", "sanction", "retaliation", "crisis", "terror"],
    "medium": ["tension", "warning", "surge", "pressure", "alert", "military"],
}


def score_threat(full_text: str, sentiment: str, topic: str, entity_count: int) -> tuple[float, float, str]:
    text = full_text.lower()
    keyword_score = 0
    for level, keywords in THREAT_KEYWORDS.items():
        level_weight = {"critical": 35, "high": 20, "medium": 10}[level]
        if any(kw in text for kw in keywords):
            keyword_score += level_weight

    sentiment_score = {"negative": 25, "neutral": 10, "positive": 0}.get(sentiment, 5)
    topic_score = {"war": 20, "cyber": 18, "economics": 12, "diplomacy": 8, "general": 6}.get(topic, 6)
    entity_score = min(entity_count * 2, 15)

    threat = min(100.0, keyword_score + sentiment_score + topic_score + entity_score)
    geo_risk = round(min(100.0, threat * 0.92 + keyword_score * 0.4), 2)

    if threat >= 75:
        level = "critical"
    elif threat >= 55:
        level = "high"
    elif threat >= 30:
        level = "medium"
    else:
        level = "low"

    return round(threat, 2), geo_risk, level
