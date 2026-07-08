from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

from research.hyperparameter.base import (
    SearchCallback, SearchResult, SearchStrategy, Trial,
)
from research.hyperparameter.search import SearchEngine
from research.hyperparameter.trial import TrialManager


class TestSearchStrategy:
    def test_enum_values(self):
        assert SearchStrategy.GRID.value == "grid"
        assert SearchStrategy.RANDOM.value == "random"
        assert SearchStrategy.OPTUNA.value == "optuna"
        assert SearchStrategy.BAYESIAN.value == "bayesian"

    def test_enum_members(self):
        assert len(SearchStrategy) == 4


class TestTrial:
    def test_dataclass(self):
        trial = Trial(
            trial_number=1,
            params={"lr": 0.01},
            metrics={"f1": 0.9},
            duration_seconds=5.0,
        )
        assert trial.trial_number == 1
        assert trial.status == "completed"
        assert trial.error is None

    def test_trial_with_error(self):
        trial = Trial(
            trial_number=1, params={}, metrics={},
            duration_seconds=0.0, status="failed", error="crash",
        )
        assert trial.error == "crash"


class TestSearchResult:
    def test_dataclass_defaults(self):
        result = SearchResult(
            strategy=SearchStrategy.GRID,
            model_type="xgboost",
            param_distribution={"lr": [0.01]},
            n_trials=1,
        )
        assert result.trials == []
        assert result.best_trial is None
        assert result.best_params == {}
        assert result.total_duration_seconds == 0.0
        assert result.convergence_curve is None

    def test_dataclass_full(self):
        trial = Trial(1, {"lr": 0.01}, {"f1": 0.9}, 5.0)
        result = SearchResult(
            strategy=SearchStrategy.RANDOM,
            model_type="rf",
            param_distribution={"lr": [0.01, 0.1]},
            n_trials=1,
            trials=[trial],
            best_trial=trial,
            best_params={"lr": 0.01},
            best_metrics={"f1": 0.9},
            total_duration_seconds=5.0,
            convergence_curve=[0.9],
        )
        assert result.best_params["lr"] == 0.01
        assert result.convergence_curve == [0.9]


class TestSearchCallback:
    def test_abstract_methods(self):
        methods = ["on_trial_start", "on_trial_end", "on_search_end"]
        for m in methods:
            assert hasattr(SearchCallback, m)
            assert getattr(SearchCallback, m).__isabstractmethod__


class TestTrialManager:
    def test_start_trial(self):
        mgr = TrialManager()
        trial = mgr.start_trial({"lr": 0.01})
        assert trial.trial_number == 1
        assert trial.status == "running"
        assert len(mgr._trials) == 1

    def test_start_trial_increments_counter(self):
        mgr = TrialManager()
        t1 = mgr.start_trial({"a": 1})
        t2 = mgr.start_trial({"a": 2})
        assert t1.trial_number == 1
        assert t2.trial_number == 2

    def test_complete_trial(self):
        mgr = TrialManager()
        trial = mgr.start_trial({})
        mgr.complete_trial(trial, {"acc": 0.95})
        assert trial.status == "completed"
        assert trial.metrics["acc"] == 0.95

    def test_fail_trial(self):
        mgr = TrialManager()
        trial = mgr.start_trial({})
        mgr.fail_trial(trial, "error msg")
        assert trial.status == "failed"
        assert trial.error == "error msg"

    def test_prune_trial(self):
        mgr = TrialManager()
        trial = mgr.start_trial({})
        mgr.prune_trial(trial)
        assert trial.status == "pruned"

    def test_get_best_trial(self):
        mgr = TrialManager()
        t1 = mgr.start_trial({"lr": 0.1})
        mgr.complete_trial(t1, {"f1": 0.8})
        t2 = mgr.start_trial({"lr": 0.01})
        mgr.complete_trial(t2, {"f1": 0.9})
        best = mgr.get_best_trial("f1")
        assert best is t2

    def test_get_best_trial_no_completed(self):
        mgr = TrialManager()
        trial = mgr.start_trial({})
        mgr.fail_trial(trial, "fail")
        assert mgr.get_best_trial("f1") is None

    def test_get_best_trial_empty(self):
        mgr = TrialManager()
        assert mgr.get_best_trial("f1") is None

    def test_get_trials(self):
        mgr = TrialManager()
        mgr.start_trial({})
        mgr.start_trial({})
        assert len(mgr.get_trials()) == 2

    def test_summary_empty(self):
        mgr = TrialManager()
        s = mgr.summary()
        assert s["total"] == 0
        assert s["completed"] == 0

    def test_summary_with_trials(self):
        mgr = TrialManager()
        t1 = mgr.start_trial({})
        mgr.complete_trial(t1, {"f1": 0.9})
        t1.duration_seconds = 2.0
        t2 = mgr.start_trial({})
        mgr.fail_trial(t2, "err")
        s = mgr.summary()
        assert s["total"] == 2
        assert s["completed"] == 1
        assert s["failed"] == 1
        assert s["mean_duration_seconds"] == 2.0

    def test_summary_with_pruned(self):
        mgr = TrialManager()
        t = mgr.start_trial({})
        mgr.prune_trial(t)
        s = mgr.summary()
        assert s["pruned"] == 1


class TestSearchEngine:
    def test_constructor_defaults(self):
        engine = SearchEngine(
            model_type="xgboost",
            param_distribution={"max_depth": [3, 5]},
        )
        assert engine.model_type == "xgboost"
        assert engine.strategy == SearchStrategy.GRID
        assert engine.n_trials == 50
        assert engine._early_stopping_patience is None

    def test_constructor_custom(self):
        engine = SearchEngine(
            model_type="rf",
            param_distribution={"n_estimators": [10, 50]},
            strategy=SearchStrategy.RANDOM,
            n_trials=10,
        )
        assert engine.strategy == SearchStrategy.RANDOM
        assert engine.n_trials == 10

    def test_add_callback(self):
        cb = MagicMock(spec=SearchCallback)
        engine = SearchEngine("xgboost", {"lr": [0.01]})
        engine.add_callback(cb)
        assert cb in engine.callbacks

    def test_set_early_stopping(self):
        engine = SearchEngine("xgboost", {"lr": [0.01]})
        engine.set_early_stopping(patience=5, min_delta=0.01)
        assert engine._early_stopping_patience == 5
        assert engine._early_stopping_min_delta == 0.01

    @pytest.mark.asyncio
    async def test_run_unknown_strategy(self):
        engine = SearchEngine(
            model_type="xgboost",
            param_distribution={"lr": [0.01, 0.1]},
        )
        engine.strategy = "unknown"
        with pytest.raises(ValueError, match="Unknown"):
            await engine.run(np.array([[1]]), np.array([0]))

    def test_get_optimization_metric_default(self):
        from research.hyperparameter.search import _get_optimization_metric
        assert _get_optimization_metric(None) == "f1"

    def test_get_optimization_metric_string(self):
        from research.hyperparameter.search import _get_optimization_metric
        assert _get_optimization_metric("accuracy") == "accuracy"

    def test_get_metric_value_present(self):
        from research.hyperparameter.search import _get_metric_value
        assert _get_metric_value({"f1": 0.9}, "f1") == 0.9

    def test_get_metric_value_missing(self):
        from research.hyperparameter.search import _get_metric_value
        metrics = {"acc": 0.9}
        val = _get_metric_value(metrics, "f1")
        assert val == 0.9

    def test_param_combinations(self):
        from research.hyperparameter.search import _param_combinations
        dist = {"lr": [0.01, 0.1], "depth": [3, 5]}
        combos = _param_combinations(dist)
        assert len(combos) == 4

    @pytest.mark.asyncio
    async def test_evaluate_params_unknown_model(self):
        engine = SearchEngine("unknown_model", {})
        with pytest.raises(ValueError, match="Unknown model type"):
            await engine.evaluate_params({}, np.array([[1]]), np.array([0]), np.array([[1]]), np.array([0]))


class TestSearchResultConvergence:
    def test_convergence_curve_none(self):
        result = SearchResult(
            strategy=SearchStrategy.GRID, model_type="xgb",
            param_distribution={"lr": [0.01]}, n_trials=0,
            convergence_curve=None,
        )
        assert result.convergence_curve is None

    def test_convergence_curve_populated(self):
        result = SearchResult(
            strategy=SearchStrategy.RANDOM, model_type="xgb",
            param_distribution={"lr": [0.01]}, n_trials=3,
            convergence_curve=[0.5, 0.8, 0.9],
        )
        assert result.convergence_curve == [0.5, 0.8, 0.9]
