from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

from research.cross_validation.engine import CVEngine
from research.cross_validation.results import CVResult, NestedCVResult
from research.cross_validation.strategies import (
    CVStrategy, _HoldoutSplitter, _NestedSplitter, create_cv_splitter,
)
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit, GroupKFold, RepeatedKFold


class TestCVStrategy:
    def test_enum_values(self):
        assert CVStrategy.HOLDOUT.value == "holdout"
        assert CVStrategy.KFOLD.value == "kfold"
        assert CVStrategy.STRATIFIED_KFOLD.value == "stratified_kfold"
        assert CVStrategy.TIMESERIES.value == "timeseries"
        assert CVStrategy.GROUP_KFOLD.value == "group_kfold"
        assert CVStrategy.REPEATED_KFOLD.value == "repeated_kfold"
        assert CVStrategy.NESTED.value == "nested"

    def test_enum_members(self):
        assert len(CVStrategy) == 7


class TestCreateCVSplitter:
    def test_holdout(self):
        splitter = create_cv_splitter(CVStrategy.HOLDOUT)
        assert isinstance(splitter, _HoldoutSplitter)
        assert splitter.get_n_splits() == 1

    def test_holdout_custom_params(self):
        splitter = create_cv_splitter(CVStrategy.HOLDOUT, {"test_size": 0.3, "stratify": True})
        assert splitter.test_size == 0.3
        assert splitter.stratify is True

    def test_kfold(self):
        splitter = create_cv_splitter(CVStrategy.KFOLD)
        assert isinstance(splitter, KFold)
        assert splitter.n_splits == 5

    def test_kfold_custom(self):
        splitter = create_cv_splitter(CVStrategy.KFOLD, {"n_splits": 3})
        assert splitter.n_splits == 3

    def test_stratified_kfold(self):
        splitter = create_cv_splitter(CVStrategy.STRATIFIED_KFOLD)
        assert isinstance(splitter, StratifiedKFold)

    def test_timeseries(self):
        splitter = create_cv_splitter(CVStrategy.TIMESERIES)
        assert isinstance(splitter, TimeSeriesSplit)

    def test_timeseries_with_gap(self):
        splitter = create_cv_splitter(CVStrategy.TIMESERIES, {"gap": 2})
        assert splitter.gap == 2

    def test_group_kfold(self):
        splitter = create_cv_splitter(CVStrategy.GROUP_KFOLD)
        assert isinstance(splitter, GroupKFold)

    def test_repeated_kfold(self):
        splitter = create_cv_splitter(CVStrategy.REPEATED_KFOLD)
        assert isinstance(splitter, RepeatedKFold)
        assert splitter.n_repeats == 10

    def test_nested(self):
        splitter = create_cv_splitter(CVStrategy.NESTED)
        assert isinstance(splitter, _NestedSplitter)

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            create_cv_splitter("unknown")


class TestHoldoutSplitter:
    def test_split_returns_one_fold(self):
        X = np.array([[1], [2], [3], [4], [5]])
        y = np.array([0, 0, 1, 1, 1])
        splitter = _HoldoutSplitter()
        folds = list(splitter.split(X, y))
        assert len(folds) == 1
        train, test = folds[0]
        assert len(train) + len(test) == 5

    def test_split_stratified(self):
        X = np.array([[1], [2], [3], [4], [5], [6]])
        y = np.array([0, 0, 0, 1, 1, 1])
        splitter = _HoldoutSplitter(stratify=True)
        folds = list(splitter.split(X, y))
        assert len(folds) == 1


class TestCVResult:
    def test_dataclass_fields(self):
        result = CVResult(
            strategy=CVStrategy.KFOLD,
            n_splits=5,
            fold_metrics=[{"acc": 0.9}, {"acc": 0.8}],
            mean_metrics={"acc": 0.85},
            std_metrics={"acc": 0.05},
            confidence_intervals={"acc": {"lower": 0.8, "upper": 0.9}},
            fold_duration_seconds=[1.0, 1.5],
            total_duration_seconds=2.5,
        )
        assert result.strategy == CVStrategy.KFOLD
        assert result.n_splits == 5
        assert result.mean_metrics["acc"] == 0.85
        assert result.total_duration_seconds == 2.5
        assert result.confusion_matrices is None


class TestNestedCVResult:
    def test_dataclass_fields(self):
        result = NestedCVResult(
            outer_folds=[{"fold": 0, "metrics": {"f1": 0.9}}],
            inner_best_params=[{"lr": 0.01}],
            overall_metrics={"f1": 0.9},
            stability_score=0.05,
        )
        assert len(result.outer_folds) == 1
        assert result.inner_best_params[0]["lr"] == 0.01
        assert result.stability_score == 0.05


class TestCVEngine:
    @pytest.mark.asyncio
    async def test_run_cv_holdout(self):
        engine = CVEngine()
        model = MagicMock()
        model.fit = MagicMock()
        model.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model.predict_proba = MagicMock(side_effect=lambda X: np.column_stack([1 - np.zeros(len(X)), np.zeros(len(X))]))
        X = np.random.randn(50, 2)
        y = np.random.randint(0, 2, 50)
        result = await engine.run_cv(model, X, y, CVStrategy.HOLDOUT)
        assert isinstance(result, CVResult)
        assert result.strategy == CVStrategy.HOLDOUT
        assert result.n_splits == 1

    @pytest.mark.asyncio
    async def test_run_cv_kfold(self):
        engine = CVEngine()
        model = MagicMock()
        model.fit = MagicMock()
        model.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model.predict_proba = None
        X = np.random.randn(50, 2)
        y = np.random.randint(0, 2, 50)
        result = await engine.run_cv(model, X, y, CVStrategy.KFOLD, {"n_splits": 3})
        assert result.n_splits == 3
        assert len(result.fold_metrics) == 3

    @pytest.mark.asyncio
    async def test_run_cv_with_string_strategy(self):
        engine = CVEngine()
        model = MagicMock()
        model.fit = MagicMock()
        model.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model.predict_proba = None
        X = np.random.randn(20, 2)
        y = np.random.randint(0, 2, 20)
        result = await engine.run_cv(model, X, y, "kfold", {"n_splits": 2})
        assert isinstance(result, CVResult)

    @pytest.mark.asyncio
    async def test_run_cv_with_scoring(self):
        engine = CVEngine()
        model = MagicMock()
        model.fit = MagicMock()
        model.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model.predict_proba = None
        X = np.random.randn(20, 2)
        y = np.random.randint(0, 2, 20)
        result = await engine.run_cv(model, X, y, CVStrategy.KFOLD, {"n_splits": 2}, scoring={"my_f1": "f1_score"})
        assert isinstance(result, CVResult)

    @pytest.mark.asyncio
    async def test_compare_models_cv(self):
        engine = CVEngine()
        model_a = MagicMock()
        model_a.fit = MagicMock()
        model_a.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model_a.predict_proba = None
        model_b = MagicMock()
        model_b.fit = MagicMock()
        model_b.predict = MagicMock(side_effect=lambda X: np.ones(len(X)))
        model_b.predict_proba = None
        X = np.random.randn(30, 2)
        y = np.random.randint(0, 2, 30)
        results = await engine.compare_models_cv({"a": model_a, "b": model_b}, X, y, CVStrategy.KFOLD, n_splits=2)
        assert "a" in results
        assert "b" in results
        assert isinstance(results["a"], CVResult)

    @pytest.mark.asyncio
    async def test_run_group_cv(self):
        engine = CVEngine()
        model = MagicMock()
        model.fit = MagicMock()
        model.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model.predict_proba = None
        X = np.random.randn(30, 2)
        y = np.random.randint(0, 2, 30)
        groups = np.array([0] * 10 + [1] * 10 + [2] * 10)
        result = await engine.run_group_cv(model, X, y, groups, n_splits=3)
        assert isinstance(result, CVResult)

    @pytest.mark.asyncio
    async def test_run_timeseries_cv(self):
        engine = CVEngine()
        model = MagicMock()
        model.fit = MagicMock()
        model.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model.predict_proba = None
        X = np.random.randn(30, 2)
        y = np.random.randint(0, 2, 30)
        result = await engine.run_timeseries_cv(model, X, y, n_splits=3)
        assert isinstance(result, CVResult)

    @pytest.mark.asyncio
    async def test_run_nested_cv(self):
        engine = CVEngine()
        model_instance = MagicMock()
        model_instance.fit = MagicMock()
        model_instance.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model_instance.predict_proba = None
        model_class = MagicMock(return_value=model_instance)
        X = np.random.randn(40, 2)
        y = np.random.randint(0, 2, 40)
        result = await engine.run_nested_cv(
            model_class, X, y,
            outer_strategy=CVStrategy.KFOLD,
            inner_strategy=CVStrategy.KFOLD,
            param_grid={"random_state": [42]},
            outer_params={"n_splits": 2},
            inner_params={"n_splits": 2},
        )
        assert isinstance(result, NestedCVResult)
        assert result.stability_score >= 0.0

    @pytest.mark.asyncio
    async def test_run_cv_empty_folds(self):
        engine = CVEngine()
        model = MagicMock()
        model.fit = MagicMock()
        model.predict = MagicMock(side_effect=lambda X: np.zeros(len(X)))
        model.predict_proba = None
        X = np.random.randn(5, 2)
        y = np.random.randint(0, 2, 5)
        result = await engine.run_cv(model, X, y, CVStrategy.HOLDOUT, {"test_size": 0.5})
        assert result.n_splits == 1
