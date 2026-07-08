import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import numpy as np

from backend.shared.config import GIT_COMMIT
from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR
from db import get_pool


class BaseTrainer(ABC):
    def __init__(self, model: Any, config: dict, logger: Any = None):
        self._model = model
        self._config = config
        self._logger = logger or get_logger(f"{__name__}.{self.__class__.__name__}")
        self._X_train: Any = None
        self._y_train: Any = None
        self._X_val: Any = None
        self._y_val: Any = None
        self._X_test: Any = None
        self._y_test: Any = None
        self._is_fitted: bool = False
        self._training_time: float = 0.0
        self._train_metrics: dict[str, float] = {}

    @abstractmethod
    async def prepare(self, X_train: Any, y_train: Any,
                      X_val: Any = None, y_val: Any = None,
                      X_test: Any = None, y_test: Any = None) -> None:
        ...

    @abstractmethod
    async def train(self) -> dict[str, float]:
        ...

    @abstractmethod
    async def predict(self, X: Any) -> Any:
        ...

    @abstractmethod
    async def evaluate(self, X: Any = None, y: Any = None) -> dict[str, float]:
        ...

    @abstractmethod
    async def save(self, path: str) -> str:
        ...

    @abstractmethod
    async def load(self, path: str) -> None:
        ...

    @abstractmethod
    async def export(self, format: str = "joblib") -> str:
        ...

    @abstractmethod
    async def register(self, experiment_name: str, run_id: str,
                       metrics: dict, tags: dict = None,
                       pool: Any = None) -> str:
        ...

    def get_params(self) -> dict[str, Any]:
        if hasattr(self._model, "get_params"):
            return self._model.get_params()
        return {}

    def set_params(self, params: dict[str, Any]) -> None:
        if hasattr(self._model, "set_params"):
            self._model.set_params(**params)

    def feature_importances(self) -> dict[str, float] | None:
        if not self._is_fitted:
            return None
        model = self._model
        if hasattr(model, "feature_importances_") and model.feature_importances_ is not None:
            scores = model.feature_importances_
            if isinstance(scores, np.ndarray):
                return {f"feature_{i}": float(v) for i, v in enumerate(scores)}
            return dict(scores)
        if hasattr(model, "coef_") and model.coef_ is not None:
            coef = np.abs(model.coef_)
            if coef.ndim > 1:
                coef = coef.mean(axis=0)
            return {f"feature_{i}": float(v) for i, v in enumerate(coef)}
        return None

    def summary(self) -> dict[str, Any]:
        return {
            "model_type": type(self._model).__name__,
            "is_fitted": self._is_fitted,
            "training_time_seconds": round(self._training_time, 4),
            "config": self._config,
            "params": self.get_params(),
            "metrics": self._train_metrics,
        }
