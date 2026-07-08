"""Standardized health-check builder.

Every service creates a ``HealthBuilder``, registers dependency checks,
and exposes a consistent JSON health response at ``/health`` and
``/readiness``.
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from backend.shared.config import SERVICE_VERSION


class HealthBuilder:
    """Builds a standardized health-check response.

    Usage::

        health = HealthBuilder("energy-service")

        async def check_db():
            pool = await get_pool()
            t0 = time.time()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency = (time.time() - t0) * 1000
            return {"status": "connected", "latency_ms": round(latency, 1)}

        health.add_check("postgres", check_db)

        @app.get("/health")
        async def handle():
            return await health.build()
    """

    def __init__(
        self,
        service_name: str,
        version: str = SERVICE_VERSION,
    ):
        self._service_name = service_name
        self._version = version
        self._started_at = datetime.utcnow()
        self._checks: dict[str, Callable[[], Awaitable[dict] | dict]] = {}

    def add_check(
        self,
        name: str,
        fn: Callable[[], Awaitable[dict] | dict],
    ) -> None:
        """Register a dependency check function.

        *fn* should return (or awaitably return) a dict with at least a
        ``"status"`` key.  Standard values: ``"connected"``, ``"loaded"``,
        ``"degraded"``, ``"unavailable"``.
        """
        self._checks[name] = fn

    async def build(self) -> dict[str, Any]:
        """Run all registered dependency checks and return the full response."""
        deps: dict[str, Any] = {}
        overall = "healthy"

        for name, fn in self._checks.items():
            try:
                result = fn()
                if hasattr(result, "__await__"):
                    result = await result  # type: ignore[misc]
                deps[name] = result
                status = result.get("status", "")
                if status in ("error", "unavailable", "disconnected"):
                    overall = "unhealthy"
                elif status == "degraded" and overall == "healthy":
                    overall = "degraded"
            except Exception as exc:
                deps[name] = {"status": "error", "error": str(exc)}
                overall = "unhealthy"

        uptime = (datetime.utcnow() - self._started_at).total_seconds()

        return {
            "status": overall,
            "service": self._service_name,
            "version": self._version,
            "uptime_seconds": round(uptime, 1),
            "started_at": self._started_at.isoformat() + "Z",
            "dependencies": deps,
        }
