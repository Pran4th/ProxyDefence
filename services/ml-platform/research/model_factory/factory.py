from typing import Any

from backend.shared.logging_config import get_logger
from research.trainers import (
    AnomalyTrainer, BaseTrainer, ClassificationTrainer, ClusteringTrainer,
    ForecastingTrainer, RankingTrainer, RegressionTrainer,
)

from .registry import ModelTypeRegistry

logger = get_logger(__name__)

_TRAINER_MAP: dict[str, type[BaseTrainer]] = {
    "classification": ClassificationTrainer,
    "regression": RegressionTrainer,
    "forecasting": ForecastingTrainer,
    "anomaly": AnomalyTrainer,
    "clustering": ClusteringTrainer,
    "ranking": RankingTrainer,
}

_CATEGORY_TO_TRAINER: dict[str, type[BaseTrainer]] = {
    "classification": ClassificationTrainer,
    "regression": RegressionTrainer,
    "anomaly": AnomalyTrainer,
    "clustering": ClusteringTrainer,
    "future_ready": ClassificationTrainer,
}

_CATEGORY_ALIASES: dict[str, str] = {
    "forecasting": "regression",
    "ranking": "classification",
}


class ModelFactory:
    def __init__(self, registry: ModelTypeRegistry | None = None):
        self._registry = registry or ModelTypeRegistry()

    def create_model(self, model_type: str, params: dict | None = None,
                     random_state: int = 42,
                     category: str | None = None) -> Any:
        model_class, default_params = self._registry.get(model_type, category=category)
        if model_class is None:
            raise ValueError(
                f"Model type '{model_type}' has no registered class "
                f"(future-ready types cannot be instantiated yet)"
            )
        merged = dict(default_params)
        if params:
            merged.update(params)
        if "random_state" in model_class().get_params() if hasattr(model_class(), "get_params") else False:
            merged.setdefault("random_state", random_state)
        try:
            instance = model_class(**merged)
        except TypeError:
            merged.pop("random_state", None)
            try:
                instance = model_class(**merged)
            except TypeError:
                raise ValueError(f"Cannot instantiate {model_type} with given parameters")
        logger.info("created model: %s with %d params", model_type, len(merged))
        return instance

    def _detect_category(self, model_type: str) -> str:
        entries = self._registry.get_entries(model_type)
        if len(entries) == 1:
            return entries[0]["category"]
        logger.info(
            "Model type '%s' has multiple categories (%s); defaulting to 'classification'",
            model_type, [e["category"] for e in entries],
        )
        return "classification"

    def _resolve_trainer_cls(self, category: str) -> type[BaseTrainer]:
        resolved = _CATEGORY_ALIASES.get(category, category)
        return _CATEGORY_TO_TRAINER.get(resolved, ClassificationTrainer)

    def create_trainer(self, model_type: str, params: dict | None = None,
                       config: dict | None = None) -> BaseTrainer:
        category = self._detect_category(model_type)
        trainer_cls = self._resolve_trainer_cls(category)
        model = self.create_model(model_type, params, category=category)
        merged_config = {
            "model_type": model_type,
            "model_name": model_type,
            "category": category,
        }
        if config:
            merged_config.update(config)
        trainer = trainer_cls(model, merged_config)
        logger.info("created trainer: %s wrapping %s", trainer_cls.__name__, model_type)
        return trainer

    def create_from_config(self, config: dict) -> tuple[Any, BaseTrainer]:
        model_cfg = config.get("model", {})
        experiment_cfg = config.get("experiment", {})
        dataset_cfg = config.get("dataset", {})
        model_type = model_cfg.get("type", "xgboost")
        params = model_cfg.get("parameters", {})
        experiment_type = experiment_cfg.get("type", "classification")
        category = self._resolve_category_from_experiment_type(experiment_type)
        model = self.create_model(model_type, params, category=category)
        trainer_cfg = {
            "model_type": model_type,
            "model_name": experiment_cfg.get("name", model_type),
            "category": category,
            "export_path": config.get("export", {}).get("path"),
            "dataset_version": dataset_cfg.get("version"),
            "feature_version": None,
        }
        for key, value in model_cfg.items():
            if key not in ("type", "parameters"):
                trainer_cfg[key] = value
        trainer_cls = self._resolve_trainer_cls(category)
        trainer = trainer_cls(model, trainer_cfg)
        logger.info("created from config: %s (%s)", model_type, experiment_type)
        return model, trainer

    def _resolve_category_from_experiment_type(self, experiment_type: str) -> str:
        mapping = {
            "classification": "classification",
            "regression": "regression",
            "forecasting": "regression",
            "anomaly_detection": "anomaly",
            "clustering": "clustering",
            "ranking": "classification",
            "dimensionality_reduction": "classification",
            "graph_learning": "classification",
        }
        return mapping.get(experiment_type, "classification")

    def get_supported_types(self) -> list[dict[str, Any]]:
        return self._registry.list_types()

    def validate_config(self, model_type: str, params: dict) -> list[str]:
        errors: list[str] = []
        try:
            entries = self._registry.get_entries(model_type)
            if not entries:
                errors.append(f"Unknown model type: {model_type}")
                return errors
            default_params = entries[0]["default_params"]
        except KeyError:
            errors.append(f"Unknown model type: {model_type}")
            return errors
        valid_param_names = set(default_params.keys()) if default_params else set()
        expected_types = {
            "random_state": (int, type(None)),
            "n_jobs": (int, type(None)),
            "max_iter": int,
            "n_estimators": int,
            "max_depth": (int, type(None)),
            "min_samples_split": (int, float),
            "learning_rate": float,
            "contamination": float,
            "eps": float,
            "verbose": (int, bool),
            "n_init": (int, str),
        }
        for key, value in params.items():
            if key in expected_types:
                expected = expected_types[key]
                if not isinstance(value, expected):
                    errors.append(
                        f"Parameter '{key}' expected type(s) {expected}, "
                        f"got {type(value).__name__}"
                    )
        logger.debug("validated config for %s: %d errors", model_type, len(errors))
        return errors


model_factory = ModelFactory()
