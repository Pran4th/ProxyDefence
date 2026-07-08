from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SearchStrategy(Enum):
    GRID = "grid"
    RANDOM = "random"
    OPTUNA = "optuna"
    BAYESIAN = "bayesian"


@dataclass
class Trial:
    trial_number: int
    params: dict[str, Any]
    metrics: dict[str, float]
    duration_seconds: float
    status: str = "completed"
    error: str | None = None


@dataclass
class SearchResult:
    strategy: SearchStrategy
    model_type: str
    param_distribution: dict[str, Any]
    n_trials: int
    trials: list[Trial] = field(default_factory=list)
    best_trial: Trial | None = None
    best_params: dict[str, Any] = field(default_factory=dict)
    best_metrics: dict[str, float] = field(default_factory=dict)
    total_duration_seconds: float = 0.0
    convergence_curve: list[float] | None = None


class SearchCallback(ABC):
    @abstractmethod
    async def on_trial_start(self, trial: Trial) -> None: ...

    @abstractmethod
    async def on_trial_end(self, trial: Trial, result: dict) -> None: ...

    @abstractmethod
    async def on_search_end(self, result: SearchResult) -> None: ...
