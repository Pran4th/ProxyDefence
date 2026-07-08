from typing import Any

import numpy as np
import pandas as pd

try:
    import optuna
    _OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None  # type: ignore
    _OPTUNA_AVAILABLE = False
from sklearn.model_selection import cross_val_score, StratifiedKFold

from backend.shared.logging_config import get_logger
from training.models import MODEL_REGISTRY

logger = get_logger(__name__)


class GridSearchOptimizer:
    def __init__(self, model_type: str, param_grid: dict[str, list[Any]],
                 cv: int = 5, scoring: str = "f1_weighted", random_seed: int = 42):
        if model_type not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model type: {model_type}")
        self._model_cls = MODEL_REGISTRY[model_type]
        self._param_grid = param_grid
        self._cv = cv
        self._scoring = scoring
        self._seed = random_seed
        self._results: list[dict] = []

    def optimize(self, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
        from itertools import product
        keys = list(self._param_grid.keys())
        values = list(self._param_grid.values())
        best_score = -np.inf
        best_params = {}

        for combo in product(*values):
            params = dict(zip(keys, combo))
            model = self._model_cls(**params)
            cv_result = cross_val_score(
                model._model, X, y, cv=self._cv, scoring=self._scoring, n_jobs=-1,
            )
            mean_score = cv_result.mean()
            self._results.append({"params": params, "mean_score": mean_score, "std": cv_result.std()})
            if mean_score > best_score:
                best_score = mean_score
                best_params = params

        return {"best_params": best_params, "best_score": best_score,
                "n_trials": len(self._results), "results": sorted(self._results, key=lambda x: -x["mean_score"])}


class RandomSearchOptimizer:
    def __init__(self, model_type: str, param_distributions: dict[str, list[Any]],
                 n_iter: int = 50, cv: int = 5, scoring: str = "f1_weighted",
                 random_seed: int = 42):
        if model_type not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model type: {model_type}")
        self._model_cls = MODEL_REGISTRY[model_type]
        self._param_dist = param_distributions
        self._n_iter = n_iter
        self._cv = cv
        self._scoring = scoring
        self._seed = random_seed
        self._rs = np.random.RandomState(random_seed)

    def optimize(self, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
        results = []
        for i in range(self._n_iter):
            params = {k: self._rs.choice(v) for k, v in self._param_dist.items()}
            model = self._model_cls(**params)
            cv_result = cross_val_score(
                model._model, X, y, cv=self._cv, scoring=self._scoring, n_jobs=-1,
            )
            mean_score = cv_result.mean()
            results.append({"params": params, "mean_score": mean_score, "std": cv_result.std()})

        best = max(results, key=lambda x: x["mean_score"])
        return {"best_params": best["params"], "best_score": best["mean_score"],
                "n_trials": self._n_iter, "results": sorted(results, key=lambda x: -x["mean_score"])}


if _OPTUNA_AVAILABLE:

    class OptunaOptimizer:
        def __init__(self, model_type: str, param_space_fn, n_trials: int = 100,
                     cv: int = 5, scoring: str = "f1_weighted", random_seed: int = 42,
                     study_name: str | None = None):
            if model_type not in MODEL_REGISTRY:
                raise ValueError(f"Unknown model type: {model_type}")
            self._model_cls = MODEL_REGISTRY[model_type]
            self._param_space_fn = param_space_fn
            self._n_trials = n_trials
            self._cv = cv
            self._scoring = scoring
            self._seed = random_seed
            self._study_name = study_name

        def optimize(self, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
            def objective(trial):
                params = self._param_space_fn(trial)
                model = self._model_cls(**params)
                cv_result = cross_val_score(
                    model._model, X, y, cv=self._cv, scoring=self._scoring, n_jobs=-1,
                )
                return cv_result.mean()

            sampler = optuna.samplers.TPESampler(seed=self._seed)
            study = optuna.create_study(
                direction="maximize",
                sampler=sampler,
                study_name=self._study_name,
            )
            study.optimize(objective, n_trials=self._n_trials)

            return {
                "best_params": study.best_params,
                "best_score": study.best_value,
                "n_trials": len(study.trials),
                "best_trial": study.best_trial.number,
            }
