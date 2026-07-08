"""Base connector interface, support types, rate limiter, and retry helpers."""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

from backend.shared.logging_config import get_logger
from connectors.errors import (
    ConnectorError,
    ConnectorConnectionError,
    ConnectorAuthError,
    ConnectorSchemaDiscoveryError,
    ConnectorFetchError,
    ConnectorValidationError,
    ConnectorRateLimitError,
    ConnectorCheckpointError,
)


class ConnectorConfig(BaseModel):
    name: str
    connector_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    rate_limit: dict[str, Any] = Field(default_factory=lambda: {"max_per_second": 10, "burst": 20})
    retry: dict[str, Any] = Field(default_factory=lambda: {"max_retries": 3, "backoff_factor": 1.0, "max_delay": 60.0})


class ConnectorFetchConfig(BaseModel):
    batch_size: int = 1000
    max_records: int | None = None
    start_position: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class ConnectorValidationResult(BaseModel):
    is_valid: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenBucket:
    """Token bucket rate limiter. Blocks until tokens are available."""

    def __init__(self, max_per_second: float, burst: int | None = None):
        self.max_per_second = max_per_second
        self.burst = burst or int(max_per_second) or 1
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()

    async def acquire(self, tokens: float = 1.0) -> float:
        wait_total = 0.0
        while self.tokens < tokens:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(float(self.burst), self.tokens + elapsed * self.max_per_second)
            self.last_refill = now
            if self.tokens >= tokens:
                break
            sleep_time = (tokens - self.tokens) / self.max_per_second
            await asyncio.sleep(sleep_time)
            wait_total += sleep_time
        self.tokens -= tokens
        return wait_total


def exponential_backoff(attempt: int, backoff_factor: float = 1.0, max_delay: float = 60.0) -> float:
    delay = backoff_factor * (2 ** attempt) + random.uniform(0, 0.5 * (2 ** attempt))
    return min(delay, max_delay)


class BaseConnector(ABC):
    """Abstract base for all data connectors."""

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self._rate_limiter: TokenBucket | None = None
        self._is_connected = False
        self._checkpoint_data: dict[str, Any] = {}
        self._setup_rate_limiter()

    def _setup_rate_limiter(self):
        rl = self.config.rate_limit
        self._rate_limiter = TokenBucket(
            max_per_second=rl.get("max_per_second", 10),
            burst=rl.get("burst", rl.get("max_per_second", 10)),
        )

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def discover_schema(self) -> dict:
        ...

    @abstractmethod
    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        ...

    async def validate(self) -> ConnectorValidationResult:
        result = ConnectorValidationResult(is_valid=True)
        if not self.config.name:
            result.is_valid = False
            result.errors.append("Connector name is required")
        if not self.config.connector_type:
            result.is_valid = False
            result.errors.append("Connector type is required")
        return result

    async def get_metadata(self) -> dict:
        return {
            "connector_type": self.config.connector_type,
            "name": self.config.name,
            "is_connected": self._is_connected,
            "rate_limit": self.config.rate_limit,
            "retry": self.config.retry,
        }

    async def checkpoint(self) -> dict:
        return dict(self._checkpoint_data)

    async def restore_checkpoint(self, checkpoint: dict) -> None:
        self._checkpoint_data = dict(checkpoint)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    def _raise_if_not_connected(self):
        if not self._is_connected:
            raise ConnectorConnectionError(f"{self.__class__.__name__} is not connected. Call connect() first.")
