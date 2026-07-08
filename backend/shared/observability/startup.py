"""Startup timing — tracks how long each initialisation phase takes.

Every service uses ``StartupTimer`` in its lifespan to record phase
durations and export them as Prometheus metrics.
"""

import time

from backend.shared.observability.metrics import startup_duration_seconds


class StartupTimer:
    """Records elapsed time for each startup phase.

    Usage in a service lifespan::

        timer = StartupTimer("energy-service")
        timer.phase("config")
        # ... imports, config ...
        timer.phase("database")
        pool = await get_pool()
        timer.phase("bootstrap")
        await bootstrap(pool)
        timer.phase("ready")
        logger.info("ready", startup=timer.finish())
    """

    def __init__(self, service_name: str):
        self._service_name = service_name
        self._current_phase: str | None = None
        self._current_start: float | None = None
        self._start = time.monotonic()
        self._phases: list[dict] = []
        self._finished = False

    def phase(self, name: str) -> None:
        """Transition to a new startup phase, recording the previous one."""
        if self._current_phase is not None:
            self._record_phase()
        self._current_phase = name
        self._current_start = time.monotonic()

    def _record_phase(self) -> None:
        if self._current_phase is None or self._current_start is None:
            return
        elapsed = time.monotonic() - self._current_start
        self._phases.append({
            "phase": self._current_phase,
            "seconds": round(elapsed, 3),
        })
        startup_duration_seconds.labels(
            service=self._service_name,
            phase=self._current_phase,
        ).set(elapsed)

    def finish(self) -> dict:
        """Finalise timing and return a summary dict.

        Call once at the end of startup (do not call ``phase()`` after).
        """
        if not self._finished:
            if self._current_phase is not None:
                self._record_phase()
            self._finished = True
        total = time.monotonic() - self._start
        return {
            "service": self._service_name,
            "total_seconds": round(total, 3),
            "phases": self._phases,
        }

    @property
    def total_seconds(self) -> float:
        return round(time.monotonic() - self._start, 3)
