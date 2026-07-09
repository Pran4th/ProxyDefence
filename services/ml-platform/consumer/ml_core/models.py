import time

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

_sentiment_pipeline = None
_ner_pipeline = None
_nlp = None

_model_load_time = None
_model_load_errors = []


def get_sentiment_pipeline():
    return _sentiment_pipeline


def get_ner_pipeline():
    return _ner_pipeline


def get_nlp():
    return _nlp


def get_model_health() -> dict:
    sentiment_loaded = _sentiment_pipeline is not None
    ner_loaded = _ner_pipeline is not None
    spacy_loaded = _nlp is not None
    return {
        "sentiment_loaded": sentiment_loaded,
        "ner_loaded": ner_loaded,
        "spacy_loaded": spacy_loaded,
        "models_loaded": sentiment_loaded or ner_loaded or spacy_loaded,
        "load_time_seconds": _model_load_time,
        "load_errors": _model_load_errors[-5:] if _model_load_errors else [],
    }


def load_models():
    global _sentiment_pipeline, _ner_pipeline, _nlp
    global _model_load_time, _model_load_errors

    start = time.time()
    _model_load_errors = []
    logger.info("model_loading_started")

    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        logger.info("model_spacy_loaded")
    except Exception as exc:
        _nlp = None
        msg = f"spaCy failed: {exc}"
        logger.error("model_spacy_failed", error=str(exc))
        _model_load_errors.append(msg)

    try:
        from transformers import pipeline
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
        )
        _ner_pipeline = pipeline(
            "ner",
            model="dbmdz/bert-large-cased-finetuned-conll03-english",
            aggregation_strategy="simple",
        )
        logger.info("model_transformers_loaded")
    except Exception as exc:
        _sentiment_pipeline = None
        _ner_pipeline = None
        msg = f"Transformers failed: {exc}"
        logger.warning("model_transformers_unavailable_fallback_spacy", error=str(exc))
        _model_load_errors.append(msg)

    _model_load_time = round(time.time() - start, 2)
    logger.info("model_loading_completed", elapsed=_model_load_time, models_loaded=_sentiment_pipeline is not None or _ner_pipeline is not None or _nlp is not None)
