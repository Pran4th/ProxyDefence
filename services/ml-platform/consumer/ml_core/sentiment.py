from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


def analyze_sentiment(full_text: str) -> tuple[str, float]:
    from ml_core.models import get_sentiment_pipeline

    pipeline = get_sentiment_pipeline()
    if pipeline is None:
        return "neutral", 0.4

    result = pipeline(full_text[:1000])[0]
    label = result["label"].lower()
    score = float(result["score"])
    if label == "negative":
        return "negative", score
    if label == "positive":
        return "positive", score
    return "neutral", score
