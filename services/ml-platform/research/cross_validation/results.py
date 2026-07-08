from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research.cross_validation.strategies import CVStrategy


@dataclass
class CVResult:
    strategy: CVStrategy
    n_splits: int
    fold_metrics: list[dict[str, float]]
    mean_metrics: dict[str, float]
    std_metrics: dict[str, float]
    confidence_intervals: dict[str, dict[str, float]]
    fold_duration_seconds: list[float]
    total_duration_seconds: float
    confusion_matrices: list[Any] | None = None


@dataclass
class NestedCVResult:
    outer_folds: list[dict[str, Any]]
    inner_best_params: list[dict[str, Any]]
    overall_metrics: dict[str, float]
    stability_score: float
