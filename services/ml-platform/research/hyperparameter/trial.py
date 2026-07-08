from __future__ import annotations

import time
from typing import Any

import numpy as np

from research.hyperparameter.base import Trial


class TrialManager:
    def __init__(self):
        self._trials: list[Trial] = []
        self._counter: int = 0

    def start_trial(self, params: dict[str, Any]) -> Trial:
        self._counter += 1
        trial = Trial(
            trial_number=self._counter,
            params=params,
            metrics={},
            duration_seconds=0.0,
            status="running",
        )
        self._trials.append(trial)
        return trial

    def complete_trial(self, trial: Trial, metrics: dict[str, float]) -> None:
        trial.metrics = metrics
        trial.status = "completed"

    def fail_trial(self, trial: Trial, error: str) -> None:
        trial.error = error
        trial.status = "failed"

    def prune_trial(self, trial: Trial) -> None:
        trial.status = "pruned"

    def get_best_trial(self, metric: str = "f1") -> Trial | None:
        completed = [t for t in self._trials if t.status == "completed" and metric in t.metrics]
        if not completed:
            return None
        return max(completed, key=lambda t: t.metrics[metric])

    def get_trials(self) -> list[Trial]:
        return list(self._trials)

    def summary(self) -> dict[str, Any]:
        completed = [t for t in self._trials if t.status == "completed"]
        failed = [t for t in self._trials if t.status == "failed"]
        pruned = [t for t in self._trials if t.status == "pruned"]
        durations = [t.duration_seconds for t in completed] if completed else [0.0]
        return {
            "total": len(self._trials),
            "completed": len(completed),
            "failed": len(failed),
            "pruned": len(pruned),
            "mean_duration_seconds": float(np.mean(durations)),
            "total_duration_seconds": float(np.sum(durations)),
        }
