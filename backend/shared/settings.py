"""Single source of truth for ALL environment variable parsing.

Every service imports from here.  No service parses its own env vars.
Service-specific overrides (e.g. NEWS_API_KEY, EMBEDDING_MODEL_NAME) stay
in that service's config.py and import the shared base vars from here.
"""

import os

from backend.shared.config import _required_env


class Settings:
    # ── PostgreSQL ────────────────────────────────────────────────
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "defenseintel")
    POSTGRES_USER: str = _required_env("POSTGRES_USER")
    POSTGRES_PASSWORD: str = _required_env("POSTGRES_PASSWORD")

    # ── Elasticsearch ─────────────────────────────────────────────
    ELASTICSEARCH_HOST: str = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
    ELASTICSEARCH_PORT: int = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
    ELASTICSEARCH_USER: str = os.getenv("ELASTICSEARCH_USER", "elastic")
    ELASTICSEARCH_PASSWORD: str = _required_env("ELASTICSEARCH_PASSWORD")

    # ── Kafka ─────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"
    )

    # ── JWT ───────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = _required_env("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # ── CORS ──────────────────────────────────────────────────────
    print("=" * 80)
    print("ENV CORS_ORIGINS =", os.getenv("CORS_ORIGINS"))
    print("=" * 80)

    CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080",
    ).split(",")
    if origin.strip()
]

    print("PARSED CORS_ORIGINS =", CORS_ORIGINS)
    print("=" * 80)

    # ── Service URLs (overridden in local dev via .env) ────────────
    EMBEDDING_SERVICE_URL: str = os.getenv(
        "EMBEDDING_SERVICE_URL", "http://embedding-service:8005"
    )
    ENERGY_SERVICE_URL: str = os.getenv(
        "ENERGY_SERVICE_URL", "http://energy-service:8000"
    )

    # ── Logging ───────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "unknown")


settings = Settings()
