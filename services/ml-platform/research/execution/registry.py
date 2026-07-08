from datetime import datetime, timezone
from typing import Any, Callable

from backend.shared.logging_config import get_logger
from research.execution.errors import ConfigurationError, StageNotFoundError
from research.execution.stage import StageResult, StageStatus

logger = get_logger(__name__)

DEFAULT_STAGE_ORDER: list[str] = [
    "dataset",
    "validation",
    "preprocessing",
    "feature_engineering",
    "feature_selection",
    "cross_validation",
    "hyperparameter_search",
    "training",
    "evaluation",
    "explainability",
    "export",
    "artifact_registration",
    "model_registration",
    "experiment_completion",
]

StageHandler = Callable[[dict, Any], StageResult]


def _make_default_handler(stage_type: str) -> StageHandler:
    def handler(config: dict, context: Any) -> StageResult:
        now = datetime.now(timezone.utc)
        stage_name = f"{stage_type}_stage"
        errors: list[str] = []
        output: dict[str, Any] = {"config_validated": True}

        if stage_type == "dataset":
            if "name" not in config:
                errors.append("Dataset stage requires 'name' in config")
            output["dataset_name"] = config.get("name", "unknown")
            output["target_column"] = config.get("target_column")
            output["test_size"] = config.get("test_size", 0.2)

        elif stage_type == "validation":
            required_keys = ["name"]
            for key in required_keys:
                if key not in config:
                    errors.append(f"Validation stage requires '{key}' in config")
            output["validation_schema"] = config.get("schema", {})

        elif stage_type == "preprocessing":
            output["steps"] = config.get("steps", [])
            output["scaling"] = config.get("scaling", "standard")

        elif stage_type == "feature_engineering":
            output["feature_count"] = config.get("feature_count", 0)
            output["generated_features"] = config.get("generated_features", [])

        elif stage_type == "feature_selection":
            output["method"] = config.get("method", "variance_threshold")
            output["selected_features"] = config.get("selected_features", [])

        elif stage_type == "cross_validation":
            output["folds"] = config.get("folds", 5)
            output["stratify"] = config.get("stratify", True)

        elif stage_type == "hyperparameter_search":
            output["method"] = config.get("method", "grid_search")
            output["param_grid"] = config.get("param_grid", {})

        elif stage_type == "training":
            output["model_type"] = config.get("type", "xgboost")
            output["parameters"] = config.get("parameters", {})

        elif stage_type == "evaluation":
            output["metrics"] = config.get("metrics", ["accuracy", "f1"])

        elif stage_type == "explainability":
            output["methods"] = config.get("methods", ["shap"])

        elif stage_type == "export":
            output["format"] = config.get("format", "joblib")
            output["register"] = config.get("register", False)

        elif stage_type == "artifact_registration":
            output["artifact_paths"] = config.get("artifact_paths", [])

        elif stage_type == "model_registration":
            output["stage"] = config.get("stage", "development")

        elif stage_type == "experiment_completion":
            output["summary"] = config.get("summary", {})

        if errors:
            raise ConfigurationError(f"{stage_type}: {'; '.join(errors)}")

        logger.info("default handler completed for stage type: %s", stage_type)
        return StageResult(
            stage_name=stage_name,
            stage_type=stage_type,
            status=StageStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            duration_ms=0.0,
            metrics={},
            output_data=output,
            error=None,
            metadata={"handler": "default", "stage_type": stage_type},
        )

    return handler


class StageRegistry:
    def __init__(self):
        self._handlers: dict[str, StageHandler] = {}

    def register(self, stage_type: str, handler: StageHandler) -> None:
        self._handlers[stage_type] = handler
        logger.debug("registered handler for stage type: %s", stage_type)

    def get(self, stage_type: str) -> StageHandler:
        handler = self._handlers.get(stage_type)
        if handler is None:
            raise StageNotFoundError(f"No handler registered for stage type: {stage_type}")
        return handler

    def list_types(self) -> list[str]:
        return list(self._handlers.keys())

    def remove(self, stage_type: str) -> None:
        if stage_type in self._handlers:
            del self._handlers[stage_type]
            logger.debug("removed handler for stage type: %s", stage_type)

    def get_default_stages(self) -> list[str]:
        return list(DEFAULT_STAGE_ORDER)


stage_registry = StageRegistry()

for _st in DEFAULT_STAGE_ORDER:
    stage_registry.register(_st, _make_default_handler(_st))
