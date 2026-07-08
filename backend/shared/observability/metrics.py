"""Custom Prometheus metric definitions.

Every metric defined here is registered once at import time and available
at the ``/metrics`` endpoint exposed by ``prometheus_fastapi_instrumentator``
in every service.
"""

import asyncio
import os

from prometheus_client import Gauge, Histogram

# ── Database ──────────────────────────────────────────────────────

db_query_latency = Histogram(
    "db_query_latency_seconds",
    "Database query latency in seconds",
    ["service", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

pool_usage = Gauge(
    "db_pool_in_use",
    "Database pool connections currently in use",
    ["service"],
)

pool_idle = Gauge(
    "db_pool_idle",
    "Database pool idle (available) connections",
    ["service"],
)

# ── Kafka ─────────────────────────────────────────────────────────

kafka_lag = Gauge(
    "kafka_consumer_lag",
    "Kafka consumer group lag per topic / partition",
    ["group", "topic", "partition"],
)

# ── Embedding ─────────────────────────────────────────────────────

embedding_latency = Histogram(
    "embedding_latency_seconds",
    "Text embedding generation latency in seconds",
    ["service"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── LLM / Agent ──────────────────────────────────────────────────

llm_request_latency = Histogram(
    "llm_request_latency_seconds",
    "LLM request latency in seconds",
    ["service", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 30.0, 60.0),
)

llm_token_count = Histogram(
    "llm_token_count",
    "LLM token counts per request",
    ["service", "model", "token_type"],
    buckets=(100, 500, 1000, 2000, 4000, 8000, 16000, 32000),
)

llm_cost_total = Gauge(
    "llm_cost_total_dollars",
    "Accumulated LLM API cost in USD",
    ["service"],
)

llm_requests_total = Gauge(
    "llm_requests_total",
    "Total number of LLM API requests",
    ["service", "status"],
)

tool_execution_latency = Histogram(
    "tool_execution_latency_seconds",
    "Agent tool execution latency in seconds",
    ["service", "tool_name"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

tool_execution_total = Gauge(
    "tool_execution_total",
    "Total number of tool executions",
    ["service", "tool_name", "status"],
)

agent_run_latency = Histogram(
    "agent_run_latency_seconds",
    "End-to-end agent run latency in seconds",
    ["service", "agent_name"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0),
)

rag_retrieval_latency = Histogram(
    "rag_retrieval_latency_seconds",
    "RAG hybrid retrieval latency in seconds",
    ["service", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# ── ML / Inference ────────────────────────────────────────────────

ml_inference_latency = Histogram(
    "ml_inference_latency_seconds",
    "ML model inference latency in seconds",
    ["service", "model_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# ── System ────────────────────────────────────────────────────────

memory_bytes = Gauge(
    "process_memory_bytes",
    "Process resident memory in bytes",
    ["service"],
)

cpu_usage = Gauge(
    "process_cpu_ratio",
    "Process CPU usage (0-1 fraction of a core)",
    ["service"],
)

# ── Startup ───────────────────────────────────────────────────────

startup_duration_seconds = Gauge(
    "service_startup_phase_seconds",
    "Duration of each startup phase",
    ["service", "phase"],
)


# ── Background collector ──────────────────────────────────────────

async def collect_system_metrics(service_name: str, interval: int = 30) -> None:
    """Periodically scrape OS-level process metrics.

    Spawn this as a background task in the service lifespan::

        task = asyncio.create_task(collect_system_metrics("my-service"))
    """
    has_psutil = False
    try:
        import psutil  # noqa: F401
        has_psutil = True
    except ImportError:
        pass

    while True:
        try:
            if has_psutil:
                import psutil

                proc = psutil.Process()
                mem = proc.memory_info().rss
                cpu = proc.cpu_percent(interval=0.1) / 100.0
            else:
                # Fallback: read /proc/self/status on Linux
                mem = _read_proc_status()
                cpu = 0.0

            memory_bytes.labels(service=service_name).set(mem)
            cpu_usage.labels(service=service_name).set(cpu)
        except Exception:
            pass

        await asyncio.sleep(interval)


def _read_proc_status() -> int:
    """Read VmRSS from /proc/self/status (Linux only)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0
