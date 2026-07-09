"""Real topic classifier replacing the old keyword-counting heuristic.

Loads the trained article-topic-classifier (TF-IDF over headline-slug text ->
XGBoost, see scripts/train_topic_classifier.py) instead of counting keyword
occurrences. Same function signature as the original ml_core.topic so nothing
downstream needs to change: classify_topic(full_text) -> (topic, confidence).
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

ARTIFACT_DIR = Path("data/artifacts/article-topic-classifier/v1")
FALLBACK_TOPIC = "general"

_cache: dict = {}


def _load() -> bool:
    if _cache:
        return True
    try:
        import joblib
        _cache["model"] = joblib.load(ARTIFACT_DIR / "model.joblib")
        _cache["vectorizer"] = joblib.load(ARTIFACT_DIR / "tfidf_vectorizer.joblib")
        _cache["categories"] = json.loads((ARTIFACT_DIR / "categories.json").read_text())
        return True
    except Exception as exc:
        logger.warning("topic_classifier_unavailable", error=str(exc))
        return False


def classify_topic(full_text: str) -> tuple[str, float]:
    # NOTE: the vectorizer's vocabulary was fit on URL-slug text (see training
    # script docstring). Prose title+content shares most of that vocabulary
    # (same news domain/entities), so the TF-IDF transform still works, but
    # this is a real domain shift from training to inference — not identical
    # to the held-out test accuracy reported at training time.
    if not _load():
        return FALLBACK_TOPIC, 0.35

    try:
        X = _cache["vectorizer"].transform([full_text[:2000]]).toarray()
        proba = _cache["model"].predict_proba(X)[0]
        best_idx = int(proba.argmax())
        topic = _cache["categories"][best_idx]
        confidence = round(float(proba[best_idx]), 4)
        return topic, confidence
    except Exception as exc:
        logger.warning("topic_classification_failed", error=str(exc))
        return FALLBACK_TOPIC, 0.35
