import asyncio
from typing import Any, Awaitable, Callable

from prometheus_client import Gauge

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

bulkhead_in_flight = Gauge(
    "resilience_bulkhead_in_flight",
    "Current number of in-flight calls in the bulkhead",
    ["name"],
)

bulkhead_queue_depth = Gauge(
    "resilience_bulkhead_queue_depth",
    "Current number of queued (waiting) calls in the bulkhead",
    ["name"],
)


class BulkheadFullError(Exception):
    def __init__(self, name: str, queue_size: int) -> None:
        self.bulkhead_name = name
        self.queue_size = queue_size
        super().__init__(
            f"Bulkhead '{name}' queue is full ({queue_size} queued)"
        )


class Bulkhead:
    def __init__(self, name: str, max_concurrent: int = 10, max_queue: int = 20) -> None:
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_count = 0
        self._in_flight_count = 0
        self._lock = asyncio.Lock()

    async def run(self, coro_factory: Callable[[], Awaitable[Any]]) -> Any:
        async with self._lock:
            if self._queue_count >= self.max_queue:
                raise BulkheadFullError(self.name, self._queue_count)
            self._queue_count += 1
            bulkhead_queue_depth.labels(name=self.name).set(self._queue_count)

        try:
            async with self._semaphore:
                async with self._lock:
                    self._queue_count -= 1
                    self._in_flight_count += 1
                    bulkhead_queue_depth.labels(name=self.name).set(self._queue_count)
                    bulkhead_in_flight.labels(name=self.name).set(self._in_flight_count)

                try:
                    return await coro_factory()
                finally:
                    async with self._lock:
                        self._in_flight_count -= 1
                        bulkhead_in_flight.labels(name=self.name).set(
                            self._in_flight_count
                        )
        except BulkheadFullError:
            raise
        except Exception:
            raise
