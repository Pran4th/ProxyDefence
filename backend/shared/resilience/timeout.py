import asyncio
from typing import Any, Awaitable, Callable

from prometheus_client import Histogram

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

operation_duration_seconds = Histogram(
    "resilience_operation_duration_seconds",
    "Duration of protected operations in seconds",
    ["operation", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)


class TimeoutError(asyncio.TimeoutError):
    pass


async def async_with_timeout(
    coro_factory: Callable[[], Awaitable[Any]],
    timeout: float = 30.0,
    operation_name: str = "unknown",
) -> Any:
    start = asyncio.get_event_loop().time()
    try:
        coro = coro_factory()
        result = await asyncio.wait_for(coro, timeout=timeout)
        elapsed = asyncio.get_event_loop().time() - start
        operation_duration_seconds.labels(
            operation=operation_name, status="success"
        ).observe(elapsed)
        return result
    except asyncio.TimeoutError:
        elapsed = asyncio.get_event_loop().time() - start
        operation_duration_seconds.labels(
            operation=operation_name, status="timeout"
        ).observe(elapsed)
        logger.error("operation_timeout", operation=operation_name, timeout=timeout)
        raise TimeoutError(
            f"Operation '{operation_name}' timed out after {timeout}s"
        )
    except Exception as exc:
        elapsed = asyncio.get_event_loop().time() - start
        operation_duration_seconds.labels(
            operation=operation_name, status="error"
        ).observe(elapsed)
        raise
