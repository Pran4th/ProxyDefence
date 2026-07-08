import numpy as np
import pytest

from training.models import MODEL_REGISTRY
from training.optimization import GridSearchOptimizer, RandomSearchOptimizer


class TestModelWrappers:
    def test_all_models_instantiate(self, all_models):
        for name, model in all_models.items():
            assert model is not None
            assert model.model_type == name

    def test_all_models_fit_and_predict(self, X_y, all_models):
        X, y = X_y
        for name, model in all_models.items():
            model.fit(X, y)
            preds = model.predict(X)
            assert len(preds) == len(y)
            assert preds.dtype in (np.int64, np.int32, np.float64)
            proba = model.predict_proba(X)
            assert proba.shape == (len(X), 4)
            assert np.allclose(proba.sum(axis=1), 1.0)

    def test_save_load_roundtrip(self, X_y, tmp_path):
        from training.models import RandomForestWrapper
        X, y = X_y
        model = RandomForestWrapper(random_state=42, n_estimators=10)
        model.fit(X, y)
        path = str(tmp_path / "model.joblib")
        model.save(path)
        loaded = RandomForestWrapper.load(path)
        assert np.array_equal(model.predict(X), loaded.predict(X))

    def test_get_params(self, all_models):
        for name, model in all_models.items():
            params = model.get_params()
            assert isinstance(params, dict)
            assert len(params) > 0


class TestOptimization:
    def test_grid_search(self, X_y):
        X, y = X_y
        optimizer = GridSearchOptimizer(
            "decision_tree",
            param_grid={"max_depth": [3, 5], "min_samples_split": [2, 5]},
            cv=3, random_seed=42,
        )
        result = optimizer.optimize(X, y)
        assert "best_params" in result
        assert "best_score" in result
        assert 0 < result["best_score"] <= 1.0

    def test_random_search(self, X_y):
        X, y = X_y
        optimizer = RandomSearchOptimizer(
            "decision_tree",
            param_distributions={"max_depth": [3, 5, 10], "min_samples_split": [2, 5, 10]},
            n_iter=3, cv=3, random_seed=42,
        )
        result = optimizer.optimize(X, y)
        assert "best_params" in result
        assert result["n_trials"] == 3
