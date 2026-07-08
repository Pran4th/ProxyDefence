from abc import ABC, abstractmethod

import joblib
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
try:
    from lightgbm import LGBMClassifier
    _LGBM_AVAILABLE = True
except ImportError:
    LGBMClassifier = None  # type: ignore
    _LGBM_AVAILABLE = False


class BaseModelWrapper(ABC):
    def __init__(self, **params):
        self._model = self._create_model(**params)
        self._params = params

    @abstractmethod
    def _create_model(self, **params):
        ...

    def fit(self, X, y):
        self._model.fit(X, y)
        return self

    def predict(self, X) -> np.ndarray:
        return self._model.predict(X)

    def predict_proba(self, X) -> np.ndarray:
        return self._model.predict_proba(X)

    def get_params(self) -> dict:
        return self._params

    def set_params(self, **params):
        self._model.set_params(**params)
        self._params = params
        return self

    def save(self, path: str):
        joblib.dump(self._model, path)

    @classmethod
    def load(cls, path: str):
        model = joblib.load(path)
        wrapper = cls()
        wrapper._model = model
        return wrapper

    @property
    def classes_(self):
        return self._model.classes_

    @property
    def feature_importances_(self):
        if hasattr(self._model, "feature_importances_"):
            return self._model.feature_importances_
        if hasattr(self._model, "coef_"):
            return np.abs(self._model.coef_).mean(axis=0)
        return None


class LogisticRegressionWrapper(BaseModelWrapper):
    def _create_model(self, **params):
        defaults = {"random_state": 42, "max_iter": 1000, "n_jobs": -1}
        defaults.update(params)
        return LogisticRegression(**defaults)

    @property
    def model_type(self) -> str:
        return "logistic_regression"


class DecisionTreeWrapper(BaseModelWrapper):
    def _create_model(self, **params):
        defaults = {"random_state": 42}
        defaults.update(params)
        return DecisionTreeClassifier(**defaults)

    @property
    def model_type(self) -> str:
        return "decision_tree"


class RandomForestWrapper(BaseModelWrapper):
    def _create_model(self, **params):
        defaults = {"random_state": 42, "n_jobs": -1}
        defaults.update(params)
        return RandomForestClassifier(**defaults)

    @property
    def model_type(self) -> str:
        return "random_forest"


class XGBoostWrapper(BaseModelWrapper):
    def _create_model(self, **params):
        defaults = {"random_state": 42, "n_jobs": -1, "eval_metric": "mlogloss", "verbosity": 0}
        defaults.update(params)
        return XGBClassifier(**defaults)

    @property
    def model_type(self) -> str:
        return "xgboost"


if _LGBM_AVAILABLE:

    class LightGBMWrapper(BaseModelWrapper):
        def _create_model(self, **params):
            defaults = {"random_state": 42, "n_jobs": -1, "verbose": -1}
            defaults.update(params)
            return LGBMClassifier(**defaults)

        @property
        def model_type(self) -> str:
            return "lightgbm"


MODEL_REGISTRY: dict[str, type[BaseModelWrapper]] = {
    "logistic_regression": LogisticRegressionWrapper,
    "decision_tree": DecisionTreeWrapper,
    "random_forest": RandomForestWrapper,
    "xgboost": XGBoostWrapper,
}
if _LGBM_AVAILABLE:
    MODEL_REGISTRY["lightgbm"] = LightGBMWrapper  # type: ignore
