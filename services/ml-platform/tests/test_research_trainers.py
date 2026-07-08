from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

from research.trainers.base import BaseTrainer
from research.trainers.classification import ClassificationTrainer
from research.trainers.regression import RegressionTrainer
from research.trainers.forecasting import ForecastingTrainer
from research.trainers.anomaly import AnomalyTrainer
from research.trainers.clustering import ClusteringTrainer
from research.trainers.ranking import RankingTrainer


class MockModel:
    def __init__(self):
        self._fitted = False

    def get_params(self):
        return {"param1": 1, "param2": "a"}

    def set_params(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def fit(self, X, y=None, **kwargs):
        self._fitted = True
        return self

    def predict(self, X):
        return np.array([0, 1, 0])

    def predict_proba(self, X):
        return np.array([[0.8, 0.2], [0.3, 0.7], [0.9, 0.1]])

    @property
    def feature_importances_(self):
        return np.array([0.6, 0.4])

    @property
    def coef_(self):
        return np.array([0.5, -0.3])

    @property
    def labels_(self):
        return np.array([0, 1, 0, 1, 0])

    @property
    def inertia_(self):
        return 42.0


class _ConcreteTrainer(BaseTrainer):
    async def prepare(self, *a, **kw): ...
    async def train(self): return {}
    async def predict(self, X): return X
    async def evaluate(self, *a, **kw): return {}
    async def save(self, path): return path
    async def load(self, path): ...
    async def export(self, fmt="joblib"): return ""
    async def register(self, *a, **kw): return ""


class TestBaseTrainer:
    def test_abstract_methods_raise(self):
        for method in ["prepare", "train", "predict", "evaluate", "save", "load", "export", "register"]:
            assert hasattr(BaseTrainer, method)
            assert getattr(BaseTrainer, method).__isabstractmethod__

    def test_get_params(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        params = trainer.get_params()
        assert params["param1"] == 1

    def test_get_params_no_method(self):
        model = object()
        trainer = ClassificationTrainer(model, {})
        assert trainer.get_params() == {}

    def test_set_params(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        trainer.set_params({"param1": 42})
        assert model.param1 == 42

    def test_set_params_no_method(self):
        model = object()
        trainer = ClassificationTrainer(model, {})
        trainer.set_params({"x": 1})

    def test_feature_importances_not_fitted(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        assert trainer.feature_importances() is None

    def test_summary_structure(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {"key": "val"})
        summary = trainer.summary()
        assert summary["model_type"] == "MockModel"
        assert summary["is_fitted"] is False
        assert summary["config"]["key"] == "val"
        assert "params" in summary
        assert "metrics" in summary


class TestClassificationTrainer:
    @pytest.mark.asyncio
    async def test_prepare(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        y_train = np.array([0, 1, 0, 1, 0])
        await trainer.prepare(np.array([[1], [2], [3], [4], [5]]), y_train)
        assert trainer._n_classes == 2
        assert trainer._class_names == [0, 1]

    @pytest.mark.asyncio
    async def test_prepare_with_class_imbalance_balanced(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {"class_imbalance": {"enabled": True, "method": "balanced"}})
        y_train = np.array([0, 1, 0])
        await trainer.prepare(np.array([[1], [2], [3]]), y_train)

    @pytest.mark.asyncio
    async def test_prepare_with_class_imbalance_sample_weight(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {"class_imbalance": {"enabled": True, "method": "sample_weight", "scale_pos_weight": True}})
        y_train = np.array([0, 1, 0])
        await trainer.prepare(np.array([[1], [2], [3]]), y_train)

    @pytest.mark.asyncio
    async def test_predict_proba(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        trainer._is_fitted = True
        preds = await trainer.predict(np.array([[1], [2], [3]]))
        assert preds.shape == (3, 2)

    @pytest.mark.asyncio
    async def test_evaluate_no_data(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        result = await trainer.evaluate()
        assert result == {}

    def test_feature_importances_fitted(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        trainer._is_fitted = True
        fi = trainer.feature_importances()
        assert fi is not None
        assert "feature_0" in fi

    def test_feature_importances_coef(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        trainer._is_fitted = True
        fi = trainer.feature_importances()
        assert fi is not None

    def test_summary(self):
        model = MockModel()
        trainer = ClassificationTrainer(model, {})
        trainer._is_fitted = True
        trainer._training_time = 1.5
        trainer._train_metrics = {"acc": 0.9}
        s = trainer.summary()
        assert s["is_fitted"] is True
        assert s["training_time_seconds"] == 1.5
        assert s["metrics"]["acc"] == 0.9


class TestRegressionTrainer:
    @pytest.mark.asyncio
    async def test_prepare_numeric_targets(self):
        model = MockModel()
        trainer = RegressionTrainer(model, {})
        y_train = np.array([1.0, 2.5, 3.2])
        await trainer.prepare(np.array([[1], [2], [3]]), y_train)
        assert trainer._X_train is not None

    @pytest.mark.asyncio
    async def test_prepare_non_numeric_targets_raises(self):
        model = MockModel()
        trainer = RegressionTrainer(model, {})
        with pytest.raises(ValueError, match="numeric"):
            await trainer.prepare(np.array([[1]]), np.array(["a"]))

    @pytest.mark.asyncio
    async def test_prepare_with_scaling(self):
        model = MockModel()
        trainer = RegressionTrainer(model, {"scaling": {"enabled": True, "method": "standard"}})
        await trainer.prepare(np.array([[1], [2]]), np.array([1.0, 2.0]))

    @pytest.mark.asyncio
    async def test_evaluate_no_data(self):
        model = MockModel()
        trainer = RegressionTrainer(model, {})
        result = await trainer.evaluate()
        assert result == {}

    @pytest.mark.asyncio
    async def test_predict(self):
        model = MockModel()
        trainer = RegressionTrainer(model, {})
        preds = await trainer.predict(np.array([[1], [2]]))
        assert len(preds) == 3


class TestForecastingTrainer:
    @pytest.mark.asyncio
    async def test_prepare(self):
        model = MockModel()
        trainer = ForecastingTrainer(model, {})
        await trainer.prepare(np.array([[1], [2], [3]]), np.array([1.0, 2.0, 3.0]))
        assert trainer._seasonal_period == 12
        assert trainer._freq == "D"

    @pytest.mark.asyncio
    async def test_prepare_with_lag_features(self):
        model = MockModel()
        trainer = ForecastingTrainer(model, {"lag_features": {"enabled": True, "num_lags": 2}})
        X = np.array([[1, 2], [3, 4], [5, 6]])
        await trainer.prepare(X, np.array([1.0, 2.0, 3.0]))
        assert trainer._lag_features is not None

    @pytest.mark.asyncio
    async def test_prepare_temporal_warning(self):
        model = MockModel()
        trainer = ForecastingTrainer(model, {})
        import pandas as pd
        dates = pd.DatetimeIndex(["2021-01-01", "2021-01-03", "2021-01-02"])
        X = pd.DataFrame({"a": [1, 2, 3]}, index=dates)
        await trainer.prepare(X, np.array([1.0, 2.0, 3.0]))

    @pytest.mark.asyncio
    async def test_evaluate_no_data(self):
        model = MockModel()
        trainer = ForecastingTrainer(model, {})
        result = await trainer.evaluate()
        assert result == {}

    @pytest.mark.asyncio
    async def test_predict(self):
        model = MockModel()
        trainer = ForecastingTrainer(model, {})
        preds = await trainer.predict(np.array([[1], [2]]))
        assert len(preds) == 3


class TestAnomalyTrainer:
    @pytest.mark.asyncio
    async def test_prepare(self):
        model = MockModel()
        trainer = AnomalyTrainer(model, {})
        await trainer.prepare(np.array([[1], [2], [3]]), None)
        assert trainer._X_train is not None
        assert trainer._contamination == 0.1

    @pytest.mark.asyncio
    async def test_prepare_with_contamination_setting(self):
        model = MagicMock()
        model.get_params = MagicMock(return_value={"contamination": 0.1})
        trainer = AnomalyTrainer(model, {"contamination": 0.05})
        await trainer.prepare(np.array([[1], [2]]), None)
        assert trainer._contamination == 0.05

    @pytest.mark.asyncio
    async def test_predict_returns_dict(self):
        model = MockModel()
        trainer = AnomalyTrainer(model, {})
        trainer._is_fitted = True
        trainer._threshold_strategy = "fixed"
        trainer._threshold = 0.5
        result = await trainer.predict(np.array([[1], [2]]))
        assert "scores" in result
        assert "labels" in result

    @pytest.mark.asyncio
    async def test_evaluate_no_data(self):
        model = MockModel()
        trainer = AnomalyTrainer(model, {})
        result = await trainer.evaluate()
        assert result == {}

    def test_decision_function_no_method(self):
        model = MagicMock(spec=[])
        trainer = AnomalyTrainer(model, {})
        scores = trainer._decision_function(np.array([[1], [2]]))
        assert len(scores) == 2


class TestClusteringTrainer:
    @pytest.mark.asyncio
    async def test_prepare_sets_y_to_none(self):
        model = MockModel()
        trainer = ClusteringTrainer(model, {})
        await trainer.prepare(np.array([[1], [2], [3]]), np.array([0, 1, 0]))
        assert trainer._y_train is None

    @pytest.mark.asyncio
    async def test_prepare_without_labels(self):
        model = MockModel()
        trainer = ClusteringTrainer(model, {})
        await trainer.prepare(np.array([[1], [2], [3]]), None)
        assert trainer._y_train is None

    @pytest.mark.asyncio
    async def test_evaluate_no_data(self):
        model = MockModel()
        trainer = ClusteringTrainer(model, {})
        result = await trainer.evaluate()
        assert result == {}

    @pytest.mark.asyncio
    async def test_predict(self):
        model = MockModel()
        trainer = ClusteringTrainer(model, {})
        preds = await trainer.predict(np.array([[1], [2]]))
        assert len(preds) == 3


class TestRankingTrainer:
    @pytest.mark.asyncio
    async def test_prepare_with_group_indices(self):
        model = MockModel()
        trainer = RankingTrainer(model, {"query_groups": {"group_column": 0}})
        X = np.array([[0], [0], [1], [1], [2]])
        await trainer.prepare(X, np.array([1, 2, 1, 2, 1]))
        assert len(trainer._group_indices) > 0

    @pytest.mark.asyncio
    async def test_prepare_without_groups(self):
        model = MockModel()
        trainer = RankingTrainer(model, {})
        await trainer.prepare(np.array([[1], [2], [3]]), np.array([1, 2, 3]))
        assert len(trainer._group_indices) == 1

    @pytest.mark.asyncio
    async def test_prepare_dataframe_group_col(self):
        model = MockModel()
        trainer = RankingTrainer(model, {"query_groups": {"group_column": "grp"}})
        import pandas as pd
        X = pd.DataFrame({"grp": [1, 1, 2, 2], "val": [10, 20, 30, 40]})
        await trainer.prepare(X, np.array([1, 2, 1, 2]))
        assert len(trainer._group_indices) >= 2

    @pytest.mark.asyncio
    async def test_evaluate_no_data(self):
        model = MockModel()
        trainer = RankingTrainer(model, {})
        result = await trainer.evaluate()
        assert result == {}

    @pytest.mark.asyncio
    async def test_predict(self):
        model = MockModel()
        trainer = RankingTrainer(model, {})
        preds = await trainer.predict(np.array([[1], [2]]))
        assert len(preds) == 3


class TestAllTrainersInstantiation:
    def test_classification_trainer(self):
        t = ClassificationTrainer(MockModel(), {})
        assert isinstance(t, BaseTrainer)

    def test_regression_trainer(self):
        t = RegressionTrainer(MockModel(), {})
        assert isinstance(t, BaseTrainer)

    def test_forecasting_trainer(self):
        t = ForecastingTrainer(MockModel(), {})
        assert isinstance(t, BaseTrainer)

    def test_anomaly_trainer(self):
        t = AnomalyTrainer(MockModel(), {})
        assert isinstance(t, BaseTrainer)

    def test_clustering_trainer(self):
        t = ClusteringTrainer(MockModel(), {})
        assert isinstance(t, BaseTrainer)

    def test_ranking_trainer(self):
        t = RankingTrainer(MockModel(), {})
        assert isinstance(t, BaseTrainer)
