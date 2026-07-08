from fastembed import TextEmbedding

from backend.shared.logging_config import get_logger

from config import EMBEDDING_MODEL_NAME

logger = get_logger(__name__)

_model: TextEmbedding | None = None


def load_model() -> TextEmbedding:
    global _model
    if _model is None:
        logger.info("loading_embedding_model", model=EMBEDDING_MODEL_NAME)
        _model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
        logger.info("embedding_model_loaded")
    return _model


def get_model() -> TextEmbedding | None:
    return _model


def embed_text(text: str):
    model = load_model()
    return list(model.embed([text]))[0]


def make_vector_str(vector) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
