"""Mock ML service response for unit tests."""


def mock_sentiment_analysis(text: str) -> dict:
    """Return deterministic sentiment for any input text."""
    negative_keywords = ["attack", "missile", "war", "threat", "breach", "strike"]
    positive_keywords = ["agreement", "summit", "cooperation", "treaty", "historic"]

    text_lower = text.lower()
    neg_score = sum(1 for kw in negative_keywords if kw in text_lower)
    pos_score = sum(1 for kw in positive_keywords if kw in text_lower)

    if neg_score > pos_score:
        return {"sentiment": "negative", "confidence": 0.8 + (neg_score * 0.05)}
    elif pos_score > neg_score:
        return {"sentiment": "positive", "confidence": 0.7 + (pos_score * 0.05)}
    return {"sentiment": "neutral", "confidence": 0.6}


def mock_entity_extraction(text: str) -> list[dict]:
    entities = [
        {"text": "Iran", "type": "GPE", "confidence": 0.95},
        {"text": "United States", "type": "GPE", "confidence": 0.94},
        {"text": "Russia", "type": "GPE", "confidence": 0.93},
    ]
    if any(word in text.lower() for word in ["iran", "israel", "hezbollah"]):
        return entities
    return []
