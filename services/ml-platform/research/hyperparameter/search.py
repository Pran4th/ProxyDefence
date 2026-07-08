from __future__ import annotations

import asyncio
import copy
import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel as ConstantKernelGP
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from scipy.stats import norm as scipy_norm

from backend.shared.logging_config import get_logger
from research.cross_validation.engine import CVEngine
from research.cross_validation.strategies import CVStrategy, create_cv_splitter
from research.hyperparameter.base import SearchCallback, SearchResult, SearchStrategy, Trial
from research.hyperparameter.trial import TrialManager

logger = get_logger(__name__)

try:
    import optuna

    _OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None  # type: ignore
    _OPTUNA_AVAILABLE = False


def _compute_metrics_hyper(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray | None = None) -> dict[str, float]:
    metrics: dict[str, float] = {}
    metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
    metrics["f1"] = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
    metrics["precision"] = float(precision_score(y_true, y_pred, average="weighted", zero_division=0))
    metrics["recall"] = float(recall_score(y_true, y_pred, average="weighted", zero_division=0))
    unique_classes = np.unique(y_true)
    if y_proba is not None and len(unique_classes) == 2:
        try:
            metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba[:, 1]))
        except (ValueError, IndexError):
            pass
    return metrics


def _get_optimization_metric(scoring: dict[str, str] | str | None) -> str:
    if scoring is None:
        return "f1"
    if isinstance(scoring, str):
        return scoring
    for preferred in ("f1", "f1_weighted", "accuracy", "roc_auc"):
        if preferred in scoring:
            return preferred
    return next(iter(scoring.keys()))


def _get_metric_value(metrics: dict[str, float], metric_name: str) -> float:
    if metric_name not in metrics and len(metrics) > 0:
        return next(iter(metrics.values()))
    return metrics.get(metric_name, 0.0)


def _param_combinations(param_distribution: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(param_distribution.keys())
    values = list(param_distribution.values())
    combos: list[dict[str, Any]] = []
    for combo in itertools.product(*values):
        combos.append(dict(zip(keys, combo)))
    return combos


def _cv_evaluate_sync(
    model_type: str,
    params: dict[str, Any],
    X: np.ndarray,
    y: np.ndarray,
    cv_strategy: CVStrategy,
    groups: np.ndarray | None = None,
    scoring: dict[str, str] | str | None = None,
) -> dict[str, float]:
    from training.models import MODEL_REGISTRY

    model_cls = MODEL_REGISTRY[model_type]
    model = model_cls(**params)
    splitter = create_cv_splitter(cv_strategy)
    fold_metrics: list[dict[str, float]] = []

    for train_idx, test_idx in splitter.split(X, y, groups):
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
        m = _compute_metrics_hyper(y_test, y_pred, y_proba)
        fold_metrics.append(m)

    mean_metrics: dict[str, float] = {}
    if fold_metrics:
        for key in fold_metrics[0]:
            mean_metrics[key] = float(np.mean([fm[key] for fm in fold_metrics]))
    return mean_metrics


class SearchEngine:
    def __init__(
        self,
        model_type: str,
        param_distribution: dict[str, Any],
        strategy: SearchStrategy = SearchStrategy.GRID,
        n_trials: int = 50,
        scoring: dict[str, str] | str | None = None,
        cv_strategy: CVStrategy = CVStrategy.STRATIFIED_KFOLD,
        random_state: int = 42,
        callbacks: list[SearchCallback] | None = None,
    ):
        self.model_type = model_type
        self.param_distribution = param_distribution
        self.strategy = strategy
        self.n_trials = n_trials
        self.scoring = scoring
        self.cv_strategy = cv_strategy
        self.random_state = random_state
        self.callbacks: list[SearchCallback] = callbacks or []
        self._early_stopping_patience: int | None = None
        self._early_stopping_min_delta: float = 0.001
        self._cv_engine = CVEngine()
        self._rng = np.random.RandomState(random_state)

    def add_callback(self, callback: SearchCallback) -> None:
        self.callbacks.append(callback)

    def set_early_stopping(self, patience: int, min_delta: float = 0.001) -> None:
        self._early_stopping_patience = patience
        self._early_stopping_min_delta = min_delta

    async def run(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        groups: np.ndarray | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> SearchResult:
        if self.strategy == SearchStrategy.GRID:
            return await self.run_grid_search(X, y, groups=groups, pool=pool)
        elif self.strategy == SearchStrategy.RANDOM:
            return await self.run_random_search(X, y, groups=groups, pool=pool)
        elif self.strategy == SearchStrategy.OPTUNA:
            return await self.run_optuna_search(X, y, groups=groups, pool=pool)
        elif self.strategy == SearchStrategy.BAYESIAN:
            return await self.run_bayesian_search(X, y, groups=groups, pool=pool)
        else:
            raise ValueError(f"Unknown search strategy: {self.strategy}")

    async def evaluate_params(
        self,
        params: dict[str, Any],
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> dict[str, float]:
        from training.models import MODEL_REGISTRY

        if self.model_type not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model type: {self.model_type}")
        model_cls = MODEL_REGISTRY[self.model_type]
        model = model_cls(**params)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_val)
        y_proba = None
        if hasattr(model, "predict_proba"):
            try:
                y_proba = model.predict_proba(X_val)
            except Exception:
                pass
        return _compute_metrics_hyper(y_val, y_pred, y_proba)

    async def run_grid_search(
        self,
        X: np.ndarray,
        y: np.ndarray,
        cv: int | None = None,
        groups: np.ndarray | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> SearchResult:
        from training.models import MODEL_REGISTRY

        trial_manager = TrialManager()
        opt_metric = _get_optimization_metric(self.scoring)
        combos = _param_combinations(self.param_distribution)
        n_trials = min(len(combos), self.n_trials)

        start_time = time.perf_counter()
        best_score = -np.inf
        best_trial: Trial | None = None
        convergence_curve: list[float] = []
        no_improve_count = 0

        for i in range(n_trials):
            params = combos[i]
            trial = trial_manager.start_trial(params)
            for cb in self.callbacks:
                await cb.on_trial_start(trial)

            trial_start = time.perf_counter()
            try:
                model_cls = MODEL_REGISTRY[self.model_type]
                model = model_cls(**params)
                cv_result = await self._cv_engine.run_cv(model, X, y, self.cv_strategy, groups=groups)
                metrics = cv_result.mean_metrics
                score = _get_metric_value(metrics, opt_metric)
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.complete_trial(trial, metrics)
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, metrics)

                if score > best_score + self._early_stopping_min_delta:
                    best_score = score
                    best_trial = trial
                    no_improve_count = 0
                else:
                    no_improve_count += 1
            except Exception as e:
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.fail_trial(trial, str(e))
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, {"error": str(e)})
                logger.error("Grid search trial %d failed: %s", i + 1, e)

            current_best = best_score if best_score > -np.inf else 0.0
            convergence_curve.append(current_best)

            if self._early_stopping_patience is not None and no_improve_count >= self._early_stopping_patience:
                logger.info("Early stopping at trial %d after %d without improvement", i + 1, no_improve_count)
                break

        total_duration = time.perf_counter() - start_time
        all_trials = trial_manager.get_trials()
        result = SearchResult(
            strategy=SearchStrategy.GRID,
            model_type=self.model_type,
            param_distribution=self.param_distribution,
            n_trials=len(all_trials),
            trials=all_trials,
            best_trial=best_trial,
            best_params=best_trial.params if best_trial else {},
            best_metrics=best_trial.metrics if best_trial else {},
            total_duration_seconds=total_duration,
            convergence_curve=convergence_curve if convergence_curve else None,
        )
        for cb in self.callbacks:
            await cb.on_search_end(result)
        return result

    async def run_random_search(
        self,
        X: np.ndarray,
        y: np.ndarray,
        cv: int | None = None,
        groups: np.ndarray | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> SearchResult:
        from training.models import MODEL_REGISTRY

        trial_manager = TrialManager()
        opt_metric = _get_optimization_metric(self.scoring)
        keys = list(self.param_distribution.keys())
        values = list(self.param_distribution.values())

        start_time = time.perf_counter()
        best_score = -np.inf
        best_trial: Trial | None = None
        convergence_curve: list[float] = []
        no_improve_count = 0

        for i in range(self.n_trials):
            params = {k: self._rng.choice(v) for k, v in zip(keys, values)}
            trial = trial_manager.start_trial(params)
            for cb in self.callbacks:
                await cb.on_trial_start(trial)

            trial_start = time.perf_counter()
            try:
                model_cls = MODEL_REGISTRY[self.model_type]
                model = model_cls(**params)
                cv_result = await self._cv_engine.run_cv(model, X, y, self.cv_strategy, groups=groups)
                metrics = cv_result.mean_metrics
                score = _get_metric_value(metrics, opt_metric)
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.complete_trial(trial, metrics)
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, metrics)

                if score > best_score + self._early_stopping_min_delta:
                    best_score = score
                    best_trial = trial
                    no_improve_count = 0
                else:
                    no_improve_count += 1
            except Exception as e:
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.fail_trial(trial, str(e))
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, {"error": str(e)})
                logger.error("Random search trial %d failed: %s", i + 1, e)

            current_best = best_score if best_score > -np.inf else 0.0
            convergence_curve.append(current_best)

            if self._early_stopping_patience is not None and no_improve_count >= self._early_stopping_patience:
                logger.info("Early stopping at trial %d after %d without improvement", i + 1, no_improve_count)
                break

        total_duration = time.perf_counter() - start_time
        all_trials = trial_manager.get_trials()
        result = SearchResult(
            strategy=SearchStrategy.RANDOM,
            model_type=self.model_type,
            param_distribution=self.param_distribution,
            n_trials=len(all_trials),
            trials=all_trials,
            best_trial=best_trial,
            best_params=best_trial.params if best_trial else {},
            best_metrics=best_trial.metrics if best_trial else {},
            total_duration_seconds=total_duration,
            convergence_curve=convergence_curve if convergence_curve else None,
        )
        for cb in self.callbacks:
            await cb.on_search_end(result)
        return result

    async def run_optuna_search(
        self,
        X: np.ndarray,
        y: np.ndarray,
        cv: int | None = None,
        groups: np.ndarray | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> SearchResult:
        if not _OPTUNA_AVAILABLE:
            raise ImportError("Optuna is not installed. Install it with: pip install optuna")

        trial_manager = TrialManager()
        opt_metric = _get_optimization_metric(self.scoring)
        keys = list(self.param_distribution.keys())
        values = list(self.param_distribution.values())

        def _suggest_params(optuna_trial: optuna.trial.Trial) -> dict[str, Any]:
            params: dict[str, Any] = {}
            for k, v_list in zip(keys, values):
                if all(isinstance(item, (int, np.integer)) for item in v_list):
                    params[k] = int(optuna_trial.suggest_int(k, int(min(v_list)), int(max(v_list))))
                elif all(isinstance(item, (float, np.floating)) for item in v_list):
                    params[k] = float(optuna_trial.suggest_float(k, float(min(v_list)), float(max(v_list))))
                else:
                    str_list = [str(item) for item in v_list]
                    chosen = optuna_trial.suggest_categorical(k, str_list)
                    for orig in v_list:
                        if str(orig) == chosen:
                            params[k] = orig
                            break
            return params

        best_score = -np.inf
        best_trial_obj: Trial | None = None
        convergence_curve: list[float] = []
        study_start = time.perf_counter()

        def _objective(optuna_trial: optuna.trial.Trial) -> float:
            nonlocal best_score, best_trial_obj

            params = _suggest_params(optuna_trial)
            trial = trial_manager.start_trial(params)
            trial_start_local = time.perf_counter()

            try:
                metrics = _cv_evaluate_sync(
                    self.model_type, params, X, y, self.cv_strategy, groups, self.scoring,
                )
                score = _get_metric_value(metrics, opt_metric)
                trial.duration_seconds = time.perf_counter() - trial_start_local
                trial_manager.complete_trial(trial, metrics)
                convergence_curve.append(max(convergence_curve[-1] if convergence_curve else -np.inf, score))

                if score > best_score:
                    best_score = score
                    best_trial_obj = trial

                return score
            except Exception as e:
                trial.duration_seconds = time.perf_counter() - trial_start_local
                trial_manager.fail_trial(trial, str(e))
                logger.error("Optuna trial %d failed: %s", trial.trial_number, e)
                raise optuna.TrialPruned()

        sampler = optuna.samplers.TPESampler(seed=self.random_state)
        pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=0, interval_steps=1)
        study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(pool, lambda: study.optimize(_objective, n_trials=self.n_trials))

        total_duration = time.perf_counter() - study_start
        all_trials = trial_manager.get_trials()
        best_trial_final = trial_manager.get_best_trial(opt_metric)
        best_params = dict(study.best_params) if hasattr(study, "best_params") and study.best_params else (
            best_trial_final.params if best_trial_final else {}
        )
        best_metrics = best_trial_final.metrics if best_trial_final else (
            best_trial_obj.metrics if best_trial_obj else {}
        )
        result = SearchResult(
            strategy=SearchStrategy.OPTUNA,
            model_type=self.model_type,
            param_distribution=self.param_distribution,
            n_trials=len(all_trials),
            trials=all_trials,
            best_trial=best_trial_final or best_trial_obj,
            best_params=best_params,
            best_metrics=best_metrics,
            total_duration_seconds=total_duration,
            convergence_curve=convergence_curve if convergence_curve else None,
        )
        for cb in self.callbacks:
            await cb.on_search_end(result)
        return result

    async def run_bayesian_search(
        self,
        X: np.ndarray,
        y: np.ndarray,
        cv: int | None = None,
        groups: np.ndarray | None = None,
        pool: ThreadPoolExecutor | None = None,
    ) -> SearchResult:
        from training.models import MODEL_REGISTRY

        trial_manager = TrialManager()
        opt_metric = _get_optimization_metric(self.scoring)
        keys = list(self.param_distribution.keys())
        values = list(self.param_distribution.values())

        param_index_map: list[list[Any]] = [list(v) for v in values]

        def _params_to_vector(params: dict[str, Any]) -> np.ndarray:
            vec: list[float] = []
            for i, k in enumerate(keys):
                choices = param_index_map[i]
                val = params[k]
                if val in choices:
                    idx = choices.index(val)
                    vec.append(float(idx))
                else:
                    vec.append(0.0)
            return np.array(vec).reshape(1, -1)

        def _vector_to_params(vec: np.ndarray) -> dict[str, Any]:
            params: dict[str, Any] = {}
            for i, k in enumerate(keys):
                idx = int(round(float(vec[0, i])))
                idx = max(0, min(idx, len(param_index_map[i]) - 1))
                params[k] = param_index_map[i][idx]
            return params

        n_initial = min(max(5, self.n_trials // 5), self.n_trials)
        observed_X: list[np.ndarray] = []
        observed_y_list: list[float] = []

        start_time = time.perf_counter()
        best_score = -np.inf
        best_trial: Trial | None = None
        convergence_curve: list[float] = []
        no_improve_count = 0

        for i in range(n_initial):
            params = {k: self._rng.choice(v) for k, v in zip(keys, values)}
            trial = trial_manager.start_trial(params)
            for cb in self.callbacks:
                await cb.on_trial_start(trial)

            trial_start = time.perf_counter()
            try:
                model_cls = MODEL_REGISTRY[self.model_type]
                model = model_cls(**params)
                cv_result = await self._cv_engine.run_cv(model, X, y, self.cv_strategy, groups=groups)
                metrics = cv_result.mean_metrics
                score = _get_metric_value(metrics, opt_metric)
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.complete_trial(trial, metrics)
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, metrics)

                observed_X.append(_params_to_vector(params))
                observed_y_list.append(score)

                if score > best_score:
                    best_score = score
                    best_trial = trial
            except Exception as e:
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.fail_trial(trial, str(e))
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, {"error": str(e)})
                logger.error("Bayesian initial trial %d failed: %s", i + 1, e)

            convergence_curve.append(best_score if best_score > -np.inf else 0.0)

        kernel = ConstantKernelGP(1.0) * Matern(length_scale=1.0, nu=2.5)
        gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=5, random_state=self.random_state, alpha=1e-6)

        for i in range(n_initial, self.n_trials):
            X_obs = np.vstack(observed_X)
            y_obs = np.array(observed_y_list)
            gp.fit(X_obs, y_obs)

            candidates: list[dict[str, Any]] = []
            for _ in range(100):
                candidate = {k: self._rng.choice(v) for k, v in zip(keys, values)}
                candidates.append(candidate)

            best_acq = -np.inf
            best_candidate: dict[str, Any] | None = None
            y_best = float(np.max(y_obs))

            for candidate in candidates:
                x_candidate = _params_to_vector(candidate)
                mu, sigma = gp.predict(x_candidate, return_std=True)
                sigma_val = float(sigma[0])
                if sigma_val <= 0:
                    acq = 0.0
                else:
                    gamma = (float(mu[0]) - y_best) / sigma_val
                    acq = float(sigma_val * (gamma * scipy_norm.cdf(gamma) + scipy_norm.pdf(gamma)))
                if acq > best_acq:
                    best_acq = acq
                    best_candidate = candidate

            if best_candidate is None:
                best_candidate = {k: self._rng.choice(v) for k, v in zip(keys, values)}

            params = best_candidate
            trial = trial_manager.start_trial(params)
            for cb in self.callbacks:
                await cb.on_trial_start(trial)

            trial_start = time.perf_counter()
            try:
                model_cls = MODEL_REGISTRY[self.model_type]
                model = model_cls(**params)
                cv_result = await self._cv_engine.run_cv(model, X, y, self.cv_strategy, groups=groups)
                metrics = cv_result.mean_metrics
                score = _get_metric_value(metrics, opt_metric)
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.complete_trial(trial, metrics)
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, metrics)

                observed_X.append(_params_to_vector(params))
                observed_y_list.append(score)

                if score > best_score + self._early_stopping_min_delta:
                    best_score = score
                    best_trial = trial
                    no_improve_count = 0
                else:
                    no_improve_count += 1
            except Exception as e:
                trial.duration_seconds = time.perf_counter() - trial_start
                trial_manager.fail_trial(trial, str(e))
                for cb in self.callbacks:
                    await cb.on_trial_end(trial, {"error": str(e)})
                logger.error("Bayesian trial %d failed: %s", i + 1, e)

            convergence_curve.append(best_score if best_score > -np.inf else 0.0)

            if self._early_stopping_patience is not None and no_improve_count >= self._early_stopping_patience:
                logger.info("Bayesian early stopping at trial %d after %d without improvement", i + 1, no_improve_count)
                break

        total_duration = time.perf_counter() - start_time
        all_trials = trial_manager.get_trials()
        result = SearchResult(
            strategy=SearchStrategy.BAYESIAN,
            model_type=self.model_type,
            param_distribution=self.param_distribution,
            n_trials=len(all_trials),
            trials=all_trials,
            best_trial=best_trial,
            best_params=best_trial.params if best_trial else {},
            best_metrics=best_trial.metrics if best_trial else {},
            total_duration_seconds=total_duration,
            convergence_curve=convergence_curve if convergence_curve else None,
        )
        for cb in self.callbacks:
            await cb.on_search_end(result)
        return result
