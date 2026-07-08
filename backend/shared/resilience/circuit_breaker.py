import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable

from prometheus_client import Counter, Gauge

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

circuit_breaker_state = Gauge(
    "resilience_circuit_breaker_state",
    "Circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
    ["name"],
)

circuit_breaker_trips_total = Counter(
    "resilience_circuit_breaker_trips_total",
    "Total circuit breaker trips (OPEN transitions)",
    ["name"],
)

_state_values = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}


class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    def __init__(self, name: str) -> None:
        self.breaker_name = name
        super().__init__(f"Circuit breaker '{name}' is OPEN — fast-failing")


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

        self._set_state(CircuitBreakerState.CLOSED)

    def _set_state(self, state: CircuitBreakerState) -> None:
        old_state = self._state
        self._state = state
        circuit_breaker_state.labels(name=self.name).set(_state_values[state.value])
        if state == CircuitBreakerState.OPEN and old_state != CircuitBreakerState.OPEN:
            circuit_breaker_trips_total.labels(name=self.name).inc()

        if old_state != state:
            logger.info(
                "circuit_breaker_state_change",
                name=self.name,
                old_state=old_state.value,
                new_state=state.value,
            )

    async def call(self, coro_factory: Callable[[], Awaitable[Any]]) -> Any:
        async with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                if self._last_failure_time is not None and (
                    time.monotonic() - self._last_failure_time
                ) >= self.recovery_timeout:
                    self._set_state(CircuitBreakerState.HALF_OPEN)
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpenError(self.name)

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name)
                self._half_open_calls += 1

        try:
            result = await coro_factory()
        except Exception as exc:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.monotonic()
                if self._state == CircuitBreakerState.HALF_OPEN:
                    self._set_state(CircuitBreakerState.OPEN)
                elif self._failure_count >= self.failure_threshold:
                    self._set_state(CircuitBreakerState.OPEN)
            raise

        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._set_state(CircuitBreakerState.CLOSED)
                self._failure_count = 0
            elif self._state == CircuitBreakerState.CLOSED:
                self._failure_count = 0

        return result
