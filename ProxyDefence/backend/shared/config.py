import os

class Settings:
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "defenseintel")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin123")

    ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")

settings = Settings()