import asyncio
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    logger.warning("psutil not available, resource monitoring disabled")


class ExecutionObserver:
    def __init__(self, execution_id: str):
        self._execution_id = execution_id
        self._logs: list[dict] = []
        self._metrics: dict[str, list[dict]] = defaultdict(list)
        self._params: dict[str, Any] = {}
        self._timeline: list[dict] = []
        self._start_time = time.monotonic()

    def log_stage_start(self, stage_name: str, stage_type: str):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self._execution_id,
            "type": "stage_start",
            "stage_name": stage_name,
            "stage_type": stage_type,
        }
        self._logs.append(entry)
        self._timeline.append({**entry, "elapsed_ms": (time.monotonic() - self._start_time) * 1000})
        logger.info("stage start: execution=%s stage=%s type=%s", self._execution_id, stage_name, stage_type)

    def log_stage_end(self, stage_name: str, stage_type: str, status: str,
                      duration_ms: float, metrics: dict = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self._execution_id,
            "type": "stage_end",
            "stage_name": stage_name,
            "stage_type": stage_type,
            "status": status,
            "duration_ms": duration_ms,
            "metrics": metrics or {},
        }
        self._logs.append(entry)
        self._timeline.append({**entry, "elapsed_ms": (time.monotonic() - self._start_time) * 1000})
        logger.info(
            "stage end: execution=%s stage=%s status=%s duration=%.0fms",
            self._execution_id, stage_name, status, duration_ms,
        )

    def log_metric(self, name: str, value: float, step: int = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self._execution_id,
            "type": "metric",
            "metric_name": name,
            "metric_value": value,
            "step": step,
        }
        self._logs.append(entry)
        self._metrics[name].append({"value": value, "step": step, "timestamp": entry["timestamp"]})
        logger.debug("metric: execution=%s %s=%s step=%s", self._execution_id, name, value, step)

    def log_param(self, name: str, value: Any):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self._execution_id,
            "type": "param",
            "param_name": name,
            "param_value": value,
        }
        self._logs.append(entry)
        self._params[name] = value
        logger.debug("param: execution=%s %s=%s", self._execution_id, name, value)

    def log_error(self, stage_name: str, error: str, details: dict = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self._execution_id,
            "type": "error",
            "stage_name": stage_name,
            "error": error,
            "details": details or {},
        }
        self._logs.append(entry)
        self._timeline.append({**entry, "elapsed_ms": (time.monotonic() - self._start_time) * 1000})
        logger.error("error: execution=%s stage=%s error=%s", self._execution_id, stage_name, error)

    def get_logs(self) -> list[dict]:
        return list(self._logs)

    def get_metrics(self) -> dict:
        return {name: [m["value"] for m in values] for name, values in self._metrics.items()}

    def get_timeline(self) -> list[dict]:
        return list(self._timeline)


class StageTimer:
    def __init__(self, observer: ExecutionObserver, stage_name: str, stage_type: str):
        self._observer = observer
        self._stage_name = stage_name
        self._stage_type = stage_type
        self._start: float | None = None

    async def __aenter__(self):
        self._observer.log_stage_start(self._stage_name, self._stage_type)
        self._start = time.monotonic()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.monotonic() - self._start) * 1000 if self._start else 0.0
        if exc_type is not None:
            self._observer.log_stage_end(
                self._stage_name, self._stage_type, "failed", duration_ms,
            )
            self._observer.log_error(
                self._stage_name, str(exc_val),
                details={"exception_type": exc_type.__name__},
            )
        else:
            self._observer.log_stage_end(
                self._stage_name, self._stage_type, "completed", duration_ms,
            )


class ResourceMonitor:
    def __init__(self, interval_seconds: float = 5.0):
        self._interval = interval_seconds
        self._monitoring = False
        self._thread: threading.Thread | None = None
        self._cpu_samples: list[float] = []
        self._memory_samples: list[float] = []
        self._peak_memory_mb: float = 0.0

    def start(self):
        if not _HAS_PSUTIL:
            logger.warning("psutil unavailable, resource monitoring not started")
            return
        self._monitoring = True
        self._cpu_samples.clear()
        self._memory_samples.clear()
        self._peak_memory_mb = 0.0
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("resource monitoring started (interval=%.1fs)", self._interval)

    def stop(self):
        self._monitoring = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info(
            "resource monitoring stopped: peak_memory=%.1fMB avg_cpu=%.1f%%",
            self._peak_memory_mb, self.get_average_cpu(),
        )

    def _monitor_loop(self):
        while self._monitoring:
            try:
                cpu = psutil.cpu_percent(interval=0.1)
                mem = psutil.Process().memory_info().rss / (1024 * 1024)
                self._cpu_samples.append(cpu)
                self._memory_samples.append(mem)
                if mem > self._peak_memory_mb:
                    self._peak_memory_mb = mem
            except Exception as exc:
                logger.debug("resource monitor sample error: %s", exc)
            time.sleep(self._interval)

    def get_peak_memory_mb(self) -> float:
        if not _HAS_PSUTIL:
            return 0.0
        if self._memory_samples:
            return max(self._memory_samples)
        try:
            return psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def get_cpu_usage(self) -> float:
        if not _HAS_PSUTIL:
            return 0.0
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception:
            return 0.0

    def get_average_cpu(self) -> float:
        if not _HAS_PSUTIL or not self._cpu_samples:
            return 0.0
        return sum(self._cpu_samples) / len(self._cpu_samples)
