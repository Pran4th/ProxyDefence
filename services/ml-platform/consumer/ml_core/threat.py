"""Threat scoring blended with the trained GDELT disruption-risk classifier,
reusing the already-validated /api/v1/risk/disruption-score endpoint (same
blend pattern as energy-service's risk_engine.py::_blend_with_ml) instead of
training a second model for the same underlying concept (escalation risk).

Same function signature as the original ml_core.threat so nothing downstream
changes: score_threat(full_text, sentiment, topic, entity_count) -> (threat, geo_risk, level).
"""
from __future__ import annotations

import os

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

THREAT_KEYWORDS = {
    "critical": ["nuclear", "chemical", "biological", "missile", "genocide", "airstrike"],
    "high": ["attack", "war", "sanction", "retaliation", "crisis", "terror"],
    "medium": ["tension", "warning", "surge", "pressure", "alert", "military"],
}

RISK_ENDPOINT = os.getenv("ML_PLATFORM_URL", "http://127.0.0.1:8007") + "/api/v1/risk/disruption-score"
ML_BLEND_WEIGHT = 0.4  # matches risk_engine.py's ML_BLEND_WEIGHT convention
_TIMEOUT = 3.0


def _keyword_threat_score(full_text: str, sentiment: str, topic: str, entity_count: int) -> float:
    text = full_text.lower()
    keyword_score = 0
    for level, keywords in THREAT_KEYWORDS.items():
        level_weight = {"critical": 35, "high": 20, "medium": 10}[level]
        if any(kw in text for kw in keywords):
            keyword_score += level_weight

    sentiment_score = {"negative": 25, "neutral": 10, "positive": 0}.get(sentiment, 5)
    topic_score = {"war": 20, "cyber": 18, "economics": 12, "diplomacy": 8, "general": 6}.get(topic, 6)
    entity_score = min(entity_count * 2, 15)
    return min(100.0, keyword_score + sentiment_score + topic_score + entity_score)


def _ml_escalation_score(full_text: str, sentiment: str) -> float | None:
    """Calls the trained disruption-risk classifier. Returns None (caller
    falls back to keyword-only) if the ML platform's own endpoint is
    unreachable — same fallback discipline as ml_bridge.py."""
    try:
        import httpx
        tone = -8.0 if sentiment == "negative" else (2.0 if sentiment == "positive" else -1.0)
        text_lower = full_text.lower()
        mention_density = min(len(text_lower.split()) / 20.0, 50)
        resp = httpx.post(
            RISK_ENDPOINT,
            json={
                "avg_tone": tone,
                "num_mentions": 10 + mention_density,
                "num_sources": 2 + mention_density / 10,
                "num_articles": 10 + mention_density,
                "is_root_event": 1,
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            return float(resp.json()["prediction"]) * 100.0  # 0-1 -> 0-100 scale
    except Exception as exc:
        logger.warning("ml_threat_score_unavailable, using keyword-only", error=str(exc))
    return None


def score_threat(full_text: str, sentiment: str, topic: str, entity_count: int) -> tuple[float, float, str]:
    keyword_threat = _keyword_threat_score(full_text, sentiment, topic, entity_count)
    ml_score = _ml_escalation_score(full_text, sentiment)

    if ml_score is not None:
        threat = round((1 - ML_BLEND_WEIGHT) * keyword_threat + ML_BLEND_WEIGHT * ml_score, 2)
    else:
        threat = round(keyword_threat, 2)

    geo_risk = round(min(100.0, threat * 0.92 + keyword_threat * 0.4), 2)

    if threat >= 75:
        level = "critical"
    elif threat >= 55:
        level = "high"
    elif threat >= 30:
        level = "medium"
    else:
        level = "low"

    return threat, geo_risk, level
