import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ExperimentLogger:
    def __init__(self, experiment_name: str, run_name: str | None = None):
        self._experiment = experiment_name
        self._run = run_name or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._metrics: dict[str, float] = {}
        self._params: dict[str, Any] = {}
        self._artifacts: list[str] = []
        self._tags: dict[str, str] = {}
        self._start_time = datetime.now(timezone.utc)

    def log_metric(self, name: str, value: float, step: int | None = None):
        key = f"{name}_step{step}" if step is not None else name
        self._metrics[key] = value
        logger.info("metric: %s = %.4f", name, value)

    def log_metrics(self, metrics: dict[str, float], prefix: str | None = None):
        for k, v in metrics.items():
            name = f"{prefix}_{k}" if prefix else k
            self._metrics[name] = v
        logger.info("logged %d metrics", len(metrics))

    def log_param(self, name: str, value: Any):
        self._params[name] = value
        logger.debug("param: %s = %s", name, value)

    def log_params(self, params: dict[str, Any], prefix: str | None = None):
        for k, v in params.items():
            name = f"{prefix}_{k}" if prefix else k
            self._params[name] = v

    def log_artifact(self, path: str):
        self._artifacts.append(path)
        logger.info("artifact: %s", path)

    def set_tag(self, key: str, value: str):
        self._tags[key] = value

    def get_summary(self) -> dict[str, Any]:
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self._start_time).total_seconds()
        return {
            "experiment": self._experiment,
            "run": self._run,
            "start_time": self._start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "metrics": self._metrics,
            "params": self._params,
            "artifact_count": len(self._artifacts),
            "artifacts": self._artifacts,
            "tags": self._tags,
        }

    def to_json(self) -> str:
        return json.dumps(self.get_summary(), indent=2, default=str)
