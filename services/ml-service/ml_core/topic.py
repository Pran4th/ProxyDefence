from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

TOPIC_KEYWORDS = {
    "war": ["war", "missile", "strike", "attack", "military", "troops", "drone", "airstrike"],
    "diplomacy": ["ceasefire", "summit", "negotiation", "talks", "diplomatic", "alliance", "peace"],
    "economics": ["oil", "trade", "sanction", "economy", "inflation", "market", "currency", "energy"],
    "cyber": ["cyber", "ransomware", "malware", "hacker", "breach", "espionage", "infrastructure"],
}


def classify_topic(full_text: str) -> tuple[str, float]:
    text = full_text.lower()
    scores = {
        topic: sum(text.count(keyword) for keyword in keywords)
        for topic, keywords in TOPIC_KEYWORDS.items()
    }
    best_topic, best_score = max(scores.items(), key=lambda item: item[1], default=("war", 0))
    total = sum(scores.values()) or 1
    confidence = round(best_score / total, 2) if best_score else 0.35
    return (best_topic if best_score else "general", confidence)
