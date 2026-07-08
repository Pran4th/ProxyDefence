import asyncio
import random
from functools import wraps
from typing import Any, Callable, Coroutine, Type

import structlog
from prometheus_client import Counter

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

retry_attempts_total = Counter(
    "resilience_retry_attempts_total",
    "Total retry attempts",
    ["service", "operation"],
)

retry_success_total = Counter(
    "resilience_retry_success_total",
    "Total successful retries",
    ["service", "operation"],
)

retry_failure_total = Counter(
    "resilience_retry_failure_total",
    "Total retry failures after exhaustion",
    ["service", "operation"],
)


def async_retry(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    exponential_base: float = 2,
    jitter: bool = True,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable[..., Coroutine[Any, Any, Any]]:
    def decorator(
        coro: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(coro)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            operation = coro.__name__
            attempt = 0
            last_exception: Exception | None = None

            while attempt <= max_retries:
                try:
                    result = await coro(*args, **kwargs)
                    if attempt > 0:
                        retry_success_total.labels(
                            service="unknown", operation=operation
                        ).inc()
                    return result
                except retryable_exceptions as exc:
                    attempt += 1
                    last_exception = exc
                    retry_attempts_total.labels(
                        service="unknown", operation=operation
                    ).inc()

                    if attempt > max_retries:
                        logger.error(
                            "retry_exhausted",
                            operation=operation,
                            attempt=attempt,
                            max_retries=max_retries,
                            error=str(exc),
                        )
                        retry_failure_total.labels(
                            service="unknown", operation=operation
                        ).inc()
                        raise

                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.warning(
                        "retry_attempt",
                        operation=operation,
                        attempt=attempt,
                        max_retries=max_retries,
                        delay=round(delay, 3),
                        error=str(exc),
                    )

                    await asyncio.sleep(delay)

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
