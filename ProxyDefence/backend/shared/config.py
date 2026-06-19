import os


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Settings:
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "defenseintel")
    POSTGRES_USER = _required_env("POSTGRES_USER")
    POSTGRES_PASSWORD = _required_env("POSTGRES_PASSWORD")

    ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
    JWT_SECRET_KEY = _required_env("JWT_SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]

settings = Settings()
