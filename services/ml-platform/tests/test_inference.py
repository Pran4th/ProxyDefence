import numpy as np
import pandas as pd
import pytest

from inference.predictor import ModelPredictor
from training.models import RandomForestWrapper


class TestPredictor:
    def test_predictor_instantiate(self):
        predictor = ModelPredictor()
        assert predictor is not None

    def test_model_predict(self, X_y):
        X, y = X_y
        model = RandomForestWrapper(random_state=42, n_estimators=10)
        model.fit(X, y)
        preds = model.predict(X.head(5))
        assert len(preds) == 5
        assert all(p in [0, 1, 2, 3] for p in preds)

    def test_predict_proba_shape(self, X_y):
        X, y = X_y
        model = RandomForestWrapper(random_state=42, n_estimators=10)
        model.fit(X, y)
        proba = model.predict_proba(X.head(3))
        assert proba.shape == (3, 4)
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_model_save_load(self, X_y, tmp_path):
        X, y = X_y
        model = RandomForestWrapper(random_state=42, n_estimators=10)
        model.fit(X, y)
        path = str(tmp_path / "test_model.joblib")
        model.save(path)
        loaded = RandomForestWrapper.load(path)
        preds_orig = model.predict(X)
        preds_loaded = loaded.predict(X)
        assert np.array_equal(preds_orig, preds_loaded)
