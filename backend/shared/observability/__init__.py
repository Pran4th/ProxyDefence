"""Production-quality observability for every service.

Provides standardized health checks, Prometheus metrics, and startup timing
so every service exposes consistent ``/health``, ``/readiness``, ``/liveness``,
and ``/metrics`` endpoints.
"""

from backend.shared.observability.health import HealthBuilder
from backend.shared.observability.metrics import (
    db_query_latency,
    pool_usage,
    pool_idle,
    kafka_lag,
    embedding_latency,
    ml_inference_latency,
    memory_bytes,
    cpu_usage,
    startup_duration_seconds,
    collect_system_metrics,
)
from backend.shared.observability.startup import StartupTimer

__all__ = [
    "HealthBuilder",
    "db_query_latency",
    "pool_usage",
    "pool_idle",
    "kafka_lag",
    "embedding_latency",
    "ml_inference_latency",
    "memory_bytes",
    "cpu_usage",
    "startup_duration_seconds",
    "collect_system_metrics",
    "StartupTimer",
]
