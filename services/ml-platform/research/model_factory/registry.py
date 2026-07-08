from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

_CATBOOST_AVAILABLE = False
try:
    from catboost import CatBoostClassifier, CatBoostRegressor
    _CATBOOST_AVAILABLE = True
except ImportError:
    CatBoostClassifier = None  # type: ignore
    CatBoostRegressor = None  # type: ignore

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    _LGBM_AVAILABLE = True
except ImportError:
    LGBMClassifier = None  # type: ignore
    LGBMRegressor = None  # type: ignore
    _LGBM_AVAILABLE = False

try:
    from xgboost import XGBClassifier, XGBRegressor
    _XGB_AVAILABLE = True
except ImportError:
    XGBClassifier = None  # type: ignore
    XGBRegressor = None  # type: ignore
    _XGB_AVAILABLE = False

from sklearn.ensemble import (
    ExtraTreesClassifier, ExtraTreesRegressor, IsolationForest,
    RandomForestClassifier, RandomForestRegressor,
)
from sklearn.cluster import DBSCAN, KMeans
from sklearn.linear_model import ElasticNet, LinearRegression, LogisticRegression
from sklearn.svm import OneClassSVM


class ModelTypeRegistry:
    def __init__(self):
        self._types: dict[str, list[dict[str, Any]]] = {}
        self._categories: dict[str, list[str]] = {
            "classification": [],
            "regression": [],
            "anomaly": [],
            "clustering": [],
            "future_ready": [],
        }
        self._register_defaults()

    def _register_defaults(self) -> None:
        cls_defaults = {"random_state": 42, "n_jobs": -1}
        reg_defaults = {"random_state": 42, "n_jobs": -1}

        self.register("xgboost", XGBClassifier, {
            **cls_defaults, "eval_metric": "mlogloss", "verbosity": 0,
        }, category="classification")
        self.register("lightgbm", LGBMClassifier, {
            **cls_defaults, "verbose": -1,
        }, category="classification")
        self.register("random_forest", RandomForestClassifier, {
            **cls_defaults,
        }, category="classification")
        self.register("extra_trees", ExtraTreesClassifier, {
            **cls_defaults,
        }, category="classification")
        self.register("logistic_regression", LogisticRegression, {
            "random_state": 42, "max_iter": 1000, "n_jobs": -1,
        }, category="classification")
        if _CATBOOST_AVAILABLE:
            self.register("catboost", CatBoostClassifier, {
                "random_seed": 42, "verbose": False,
            }, category="classification")

        self.register("xgboost", XGBRegressor, {
            **reg_defaults, "verbosity": 0,
        }, category="regression")
        self.register("lightgbm", LGBMRegressor, {
            **reg_defaults, "verbose": -1,
        }, category="regression")
        self.register("random_forest", RandomForestRegressor, {
            **reg_defaults,
        }, category="regression")
        self.register("extra_trees", ExtraTreesRegressor, {
            **reg_defaults,
        }, category="regression")
        self.register("linear_regression", LinearRegression, {
            "n_jobs": -1,
        }, category="regression")
        self.register("elasticnet", ElasticNet, {
            "random_state": 42, "max_iter": 1000,
        }, category="regression")
        if _CATBOOST_AVAILABLE:
            self.register("catboost", CatBoostRegressor, {
                "random_seed": 42, "verbose": False,
            }, category="regression")

        self.register("isolation_forest", IsolationForest, {
            "random_state": 42, "n_jobs": -1, "contamination": 0.1,
        }, category="anomaly")
        self.register("one_class_svm", OneClassSVM, {
            "kernel": "rbf", "gamma": "auto", "nu": 0.1,
        }, category="anomaly")

        self.register("kmeans", KMeans, {
            "random_state": 42, "n_init": 10,
        }, category="clustering")
        self.register("dbscan", DBSCAN, {
            "eps": 0.5, "min_samples": 5, "n_jobs": -1,
        }, category="clustering")

        self.register("lstm", None, {
            "hidden_size": 128, "num_layers": 2, "dropout": 0.2, "bidirectional": False,
        }, category="future_ready")
        self.register("transformer", None, {
            "nhead": 8, "num_encoder_layers": 6, "dim_feedforward": 2048, "dropout": 0.1,
        }, category="future_ready")
        self.register("graph_neural_network", None, {
            "hidden_channels": 64, "num_layers": 3, "dropout": 0.2,
        }, category="future_ready")

    def register(self, model_type: str, model_class: type | None,
                 default_params: dict = None,
                 category: str = "classification") -> None:
        if category not in self._categories:
            self._categories[category] = []
        if model_type not in self._categories[category]:
            self._categories[category].append(model_type)
        entry = {
            "class": model_class,
            "default_params": default_params or {},
            "category": category,
        }
        if model_type not in self._types:
            self._types[model_type] = []
        existing = [e for e in self._types[model_type] if e["category"] == category]
        if existing:
            existing[0].update(entry)
        else:
            self._types[model_type].append(entry)
        logger.debug("registered model type: %s (category=%s)", model_type, category)

    def get(self, model_type: str, category: str | None = None) -> tuple[type | None, dict]:
        entries = self._types.get(model_type)
        if not entries:
            raise KeyError(f"Unknown model type: {model_type}. Available: {list(self._types.keys())}")
        if category:
            for e in entries:
                if e["category"] == category:
                    return e["class"], e["default_params"]
            raise KeyError(
                f"Model type '{model_type}' not found in category '{category}'. "
                f"Available categories: {[e['category'] for e in entries]}"
            )
        entry = entries[0]
        if len(entries) > 1:
            logger.warning(
                "Model type '%s' has %d registrations across categories (%s); "
                "returning first (%s). Specify category for exact match.",
                model_type, len(entries),
                [e["category"] for e in entries],
                entry["category"],
            )
        return entry["class"], entry["default_params"]

    def get_entries(self, model_type: str) -> list[dict[str, Any]]:
        return list(self._types.get(model_type, []))

    def list_types(self, category: str | None = None) -> list[dict[str, Any]]:
        if category:
            type_names = self._categories.get(category, [])
        else:
            type_names = list(self._types.keys())
        result = []
        for name in type_names:
            entries = self._types.get(name, [])
            for e in entries:
                if category and e["category"] != category:
                    continue
                result.append({
                    "name": name,
                    "category": e["category"],
                    "has_class": e["class"] is not None,
                    "default_params": e["default_params"],
                })
        return result

    def get_default_params(self, model_type: str, category: str | None = None) -> dict:
        _, params = self.get(model_type, category=category)
        return dict(params)

    @property
    def available_types(self) -> list[str]:
        return list(self._types.keys())

    def __contains__(self, model_type: str) -> bool:
        return model_type in self._types
