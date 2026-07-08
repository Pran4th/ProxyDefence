from __future__ import annotations

import copy
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from scipy import stats as scipy_stats

from backend.shared.logging_config import get_logger
from research.cross_validation.results import CVResult, NestedCVResult
from research.cross_validation.strategies import CVStrategy, create_cv_splitter

logger = get_logger(__name__)


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray | None = None) -> dict[str, float]:
    metrics: dict[str, float] = {}
    metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
    metrics["precision_macro"] = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    metrics["recall_macro"] = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    metrics["f1_macro"] = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    metrics["precision_weighted"] = float(precision_score(y_true, y_pred, average="weighted", zero_division=0))
    metrics["recall_weighted"] = float(recall_score(y_true, y_pred, average="weighted", zero_division=0))
    metrics["f1_weighted"] = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    unique_classes = np.unique(y_true)
    if y_proba is not None and len(unique_classes) == 2:
        try:
            metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba[:, 1]))
        except (ValueError, IndexError):
            pass

    return metrics


def _compute_confidence_interval(values: list[float], confidence: float = 0.95) -> dict[str, float]:
    n = len(values)
    arr = np.array(values)
    mean = float(np.mean(arr))
    if n < 2:
        return {"lower": mean, "upper": mean}
    se = float(scipy_stats.sem(arr))
    ci = scipy_stats.t.interval(confidence, df=n - 1, loc=mean, scale=se)
    return {"lower": float(ci[0]), "upper": float(ci[1])}


def _aggregate_metrics(fold_metrics: list[dict[str, float]]) -> tuple[dict[str, float], dict[str, float], dict[str, dict[str, float]]]:
    all_keys = set()
    for fm in fold_metrics:
        all_keys.update(fm.keys())

    mean_metrics: dict[str, float] = {}
    std_metrics: dict[str, float] = {}
    confidence_intervals: dict[str, dict[str, float]] = {}

    for key in sorted(all_keys):
        values = [fm[key] for fm in fold_metrics if key in fm]
        if not values:
            continue
        mean_metrics[key] = float(np.mean(values))
        std_metrics[key] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        confidence_intervals[key] = _compute_confidence_interval(values)

    return mean_metrics, std_metrics, confidence_intervals


class CVEngine:
    async def run_cv(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        strategy: CVStrategy | str,
        params: dict[str, Any] | None = None,
        groups: np.ndarray | None = None,
        scoring: dict[str, str] | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> CVResult:
        if isinstance(strategy, str):
            strategy = CVStrategy(strategy)

        splitter = create_cv_splitter(strategy, params)
        n_splits = splitter.get_n_splits(X, y, groups)

        fold_metrics_list: list[dict[str, float]] = []
        fold_durations: list[float] = []
        confusion_matrices_list: list[Any] = []

        start_time = time.perf_counter()

        for fold_idx, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups)):
            fold_start = time.perf_counter()
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            model_copy = copy.deepcopy(model)
            model_copy.fit(X_train, y_train)
            y_pred = model_copy.predict(X_test)

            y_proba = None
            if hasattr(model_copy, "predict_proba"):
                try:
                    y_proba = model_copy.predict_proba(X_test)
                except Exception:
                    pass

            metrics = _compute_metrics(y_test, y_pred, y_proba)

            if scoring:
                for metric_name, sklearn_metric in scoring.items():
                    try:
                        metric_func = getattr(__import__("sklearn.metrics", fromlist=[sklearn_metric]), sklearn_metric)
                        if y_proba is not None and sklearn_metric in ("roc_auc", "average_precision"):
                            metrics[metric_name] = float(metric_func(y_test, y_proba[:, 1]))
                        else:
                            metrics[metric_name] = float(metric_func(y_test, y_pred))
                    except (AttributeError, ValueError, Exception):
                        pass

            cm = confusion_matrix(y_test, y_pred).tolist()
            fold_duration = time.perf_counter() - fold_start

            fold_metrics_list.append(metrics)
            fold_durations.append(fold_duration)
            confusion_matrices_list.append(cm)

            logger.debug("Fold %d/%d complete: f1_weighted=%.4f, duration=%.2fs", fold_idx + 1, n_splits, metrics.get("f1_weighted", 0.0), fold_duration)

        total_duration = time.perf_counter() - start_time
        mean_metrics, std_metrics, confidence_intervals = _aggregate_metrics(fold_metrics_list)

        return CVResult(
            strategy=strategy,
            n_splits=n_splits,
            fold_metrics=fold_metrics_list,
            mean_metrics=mean_metrics,
            std_metrics=std_metrics,
            confidence_intervals=confidence_intervals,
            fold_duration_seconds=fold_durations,
            total_duration_seconds=total_duration,
            confusion_matrices=confusion_matrices_list,
        )

    async def run_nested_cv(
        self,
        model_class: type,
        X: np.ndarray,
        y: np.ndarray,
        outer_strategy: CVStrategy,
        inner_strategy: CVStrategy,
        param_grid: dict[str, list[Any]],
        outer_params: dict[str, Any] | None = None,
        inner_params: dict[str, Any] | None = None,
        scoring: dict[str, str] | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> NestedCVResult:
        outer_params = outer_params or {}
        inner_params = inner_params or {}
        outer_splitter = create_cv_splitter(outer_strategy, outer_params)
        inner_splitter = create_cv_splitter(inner_strategy, inner_params)

        outer_folds: list[dict[str, Any]] = []
        inner_best_params_list: list[dict[str, Any]] = []

        for outer_idx, (train_idx, test_idx) in enumerate(outer_splitter.split(X, y)):
            outer_fold_start = time.perf_counter()
            X_outer_train, X_outer_test = X[train_idx], X[test_idx]
            y_outer_train, y_outer_test = y[train_idx], y[test_idx]

            inner_best_score = -np.inf
            inner_best_params: dict[str, Any] = {}

            from itertools import product
            keys = list(param_grid.keys())
            values = list(param_grid.values())

            for combo in product(*values):
                params = dict(zip(keys, combo))
                inner_scores = []

                for inner_idx, (inner_train_idx, inner_val_idx) in enumerate(inner_splitter.split(X_outer_train, y_outer_train)):
                    X_inner_train, X_inner_val = X_outer_train[inner_train_idx], X_outer_train[inner_val_idx]
                    y_inner_train, y_inner_val = y_outer_train[inner_train_idx], y_outer_train[inner_val_idx]

                    inner_model = model_class(**params)
                    inner_model.fit(X_inner_train, y_inner_train)
                    inner_pred = inner_model.predict(X_inner_val)
                    inner_score = float(f1_score(y_inner_val, inner_pred, average="weighted", zero_division=0))
                    inner_scores.append(inner_score)

                mean_inner = float(np.mean(inner_scores))
                if mean_inner > inner_best_score:
                    inner_best_score = mean_inner
                    inner_best_params = params

            best_model = model_class(**inner_best_params)
            best_model.fit(X_outer_train, y_outer_train)
            outer_pred = best_model.predict(X_outer_test)

            outer_y_proba = None
            if hasattr(best_model, "predict_proba"):
                try:
                    outer_y_proba = best_model.predict_proba(X_outer_test)
                except Exception:
                    pass

            outer_metrics = _compute_metrics(y_outer_test, outer_pred, outer_y_proba)
            outer_fold_duration = time.perf_counter() - outer_fold_start

            outer_folds.append({"fold": outer_idx, "metrics": outer_metrics, "duration": outer_fold_duration})
            inner_best_params_list.append(inner_best_params)
            logger.debug("Nested outer fold %d complete: f1_weighted=%.4f, best_inner=%s", outer_idx, outer_metrics.get("f1_weighted", 0.0), inner_best_params)

        overall_metrics = {}
        all_keys = set()
        for fold in outer_folds:
            all_keys.update(fold["metrics"].keys())
        for key in sorted(all_keys):
            values_list = [fold["metrics"][key] for fold in outer_folds if key in fold["metrics"]]
            overall_metrics[key] = float(np.mean(values_list))
        overall_metrics["f1_weighted_mean"] = overall_metrics.get("f1_weighted", 0.0)

        f1_values = [fold["metrics"].get("f1_weighted", 0.0) for fold in outer_folds]
        stability_score = float(np.std(f1_values, ddof=1)) if len(f1_values) > 1 else 0.0

        return NestedCVResult(
            outer_folds=outer_folds,
            inner_best_params=inner_best_params_list,
            overall_metrics=overall_metrics,
            stability_score=stability_score,
        )

    async def run_group_cv(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        groups: np.ndarray,
        strategy: CVStrategy = CVStrategy.GROUP_KFOLD,
        n_splits: int = 5,
        scoring: dict[str, str] | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> CVResult:
        return await self.run_cv(
            model=model,
            X=X,
            y=y,
            strategy=strategy,
            params={"n_splits": n_splits},
            groups=groups,
            scoring=scoring,
            pool=pool,
        )

    async def run_timeseries_cv(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        n_splits: int = 5,
        gap: int = 0,
        scoring: dict[str, str] | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> CVResult:
        return await self.run_cv(
            model=model,
            X=X,
            y=y,
            strategy=CVStrategy.TIMESERIES,
            params={"n_splits": n_splits, "gap": gap},
            groups=None,
            scoring=scoring,
            pool=pool,
        )

    async def compare_models_cv(
        self,
        models: dict[str, Any],
        X: np.ndarray,
        y: np.ndarray,
        strategy: CVStrategy = CVStrategy.STRATIFIED_KFOLD,
        n_splits: int = 5,
        scoring: dict[str, str] | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> dict[str, CVResult]:
        results: dict[str, CVResult] = {}
        for name, model in models.items():
            logger.info("Running CV for model: %s", name)
            cv_result = await self.run_cv(
                model=model,
                X=X,
                y=y,
                strategy=strategy,
                params={"n_splits": n_splits},
                groups=None,
                scoring=scoring,
                pool=pool,
            )
            results[name] = cv_result
        return results
