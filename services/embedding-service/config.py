import os

from backend.shared.settings import settings

POSTGRES_PORT = settings.POSTGRES_PORT

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
