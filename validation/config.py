import os
from dataclasses import dataclass, field
from typing import Optional


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass
class ValidationConfig:
    # Service ports (6 backend services; ml-service/8002 was retired -> ml-platform)
    modular_api_port: int = _env_int("MODULAR_API_PORT", 8000)
    ingest_port: int = _env_int("INGEST_PORT", 8001)
    db_port: int = _env_int("DATABASE_SERVICE_PORT", 8003)
    embedding_port: int = _env_int("EMBEDDING_SERVICE_PORT", 8005)
    energy_port: int = _env_int("ENERGY_SERVICE_PORT", 8006)
    ml_platform_port: int = _env_int("ML_PLATFORM_PORT", 8007)
    frontend_port: int = _env_int("FRONTEND_PORT", 8080)

    # Infrastructure ports - read from the same env vars every service uses
    postgres_port: int = _env_int("POSTGRES_PORT", 5434)
    kafka_port: int = 9092
    elasticsearch_port: int = 9200
    redis_port: int = 6379

    # Hosts
    postgres_host: str = _env("POSTGRES_HOST", "localhost")
    kafka_host: str = "localhost"
    elasticsearch_host: str = _env("ELASTICSEARCH_HOST", "localhost")
    redis_host: str = "localhost"
    api_host: str = "localhost"
    frontend_host: str = "localhost"

    # Credentials - default to docker-compose.yml's dev defaults, override via env
    postgres_user: str = _env("POSTGRES_USER", "admin")
    postgres_password: str = _env("POSTGRES_PASSWORD", "change-me")
    postgres_db: str = _env("POSTGRES_DB", "defenseintel")
    elasticsearch_user: str = _env("ELASTICSEARCH_USER", "elastic")
    elasticsearch_password: str = _env("ELASTICSEARCH_PASSWORD", "change-me")

    # Dedicated service-account user the validation suite registers/logs in as
    # to obtain a Bearer token for protected modular-api routes.
    # NOTE: EmailStr rejects reserved TLDs (.local/.test/.invalid/etc) as
    # "special-use or reserved" -- must be a syntactically ordinary domain.
    validation_user_email: str = "validation-suite@proxydefence-test.io"
    validation_user_username: str = "validation_suite"
    validation_user_password: str = "ValidationSuite#2026"

    # ML Platform
    ml_platform_base: str = "/api/v1/ml"

    # GDELT
    gdelt_sample_date: str = "20240101"
    gdelt_datasets_dir: str = "datasets"

    # Timeouts (seconds)
    http_timeout: float = 5.0
    db_timeout: float = 5.0
    kafka_timeout: float = 5.0

    @property
    def modular_api_url(self) -> str:
        return f"http://{self.api_host}:{self.modular_api_port}"

    @property
    def ingest_url(self) -> str:
        return f"http://{self.api_host}:{self.ingest_port}"

    @property
    def db_service_url(self) -> str:
        return f"http://{self.api_host}:{self.db_port}"

    @property
    def embedding_url(self) -> str:
        return f"http://{self.api_host}:{self.embedding_port}"

    @property
    def energy_url(self) -> str:
        return f"http://{self.api_host}:{self.energy_port}"

    @property
    def ml_platform_url(self) -> str:
        return f"http://{self.api_host}:{self.ml_platform_port}"

    @property
    def frontend_url(self) -> str:
        return f"http://{self.frontend_host}:{self.frontend_port}"

    @property
    def elasticsearch_url(self) -> str:
        return f"http://{self.elasticsearch_host}:{self.elasticsearch_port}"

    @property
    def postgres_dsn(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
