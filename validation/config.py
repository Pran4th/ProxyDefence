from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationConfig:
    # Service ports
    modular_api_port: int = 8000
    ingest_port: int = 8001
    ml_port: int = 8002
    db_port: int = 8003
    embedding_port: int = 8005
    energy_port: int = 8006
    ml_platform_port: int = 8007
    frontend_port: int = 8080

    # Infrastructure ports
    postgres_port: int = 5432
    kafka_port: int = 9092
    elasticsearch_port: int = 9200
    redis_port: int = 6379

    # Hosts
    postgres_host: str = "localhost"
    kafka_host: str = "localhost"
    elasticsearch_host: str = "localhost"
    redis_host: str = "localhost"
    api_host: str = "localhost"
    frontend_host: str = "localhost"

    # Credentials
    postgres_user: str = "admin"
    postgres_password: str = "change-me"
    postgres_db: str = "defenseintel"
    elasticsearch_user: str = "elastic"
    elasticsearch_password: str = "change-me"

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
    def ml_url(self) -> str:
        return f"http://{self.api_host}:{self.ml_port}"

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
