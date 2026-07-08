import json
import os
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR
from db import get_pool
from registry.model_registry import ModelRegistry

logger = get_logger(__name__)


class PlatformImporter:
    def __init__(self):
        self._registry = ModelRegistry()

    async def import_export(self, export_path: str, model_name: str | None = None,
                            stage: str = "development") -> dict[str, Any] | None:
        export_dir = Path(export_path)
        if not export_dir.exists():
            raise FileNotFoundError(f"Export path not found: {export_path}")

        config_path = export_dir / "config.json"
        model_path = export_dir / "model.joblib"
        if not config_path.exists():
            raise FileNotFoundError(f"config.json not found in {export_path}")

        with open(config_path) as f:
            config = json.load(f)

        if not model_path.exists():
            raise FileNotFoundError(f"model.joblib not found in {export_path}")

        name = model_name or config.get("model_name", "unnamed_model")
        model_type = config.get("model_type", "xgboost")
        metrics = config.get("metrics", {})
        parameters = config.get("parameters", {})
        feature_version = config.get("feature_version")
        dataset_version = config.get("dataset_version")
        run_id = config.get("run_id")
        experiment_id = config.get("experiment_id")

        artifacts_dir = Path(ARTIFACT_DIR) / "imported" / name
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        import shutil
        dest_path = artifacts_dir / f"v_{model_path.name}"
        shutil.copy2(str(model_path), str(dest_path))

        model_record = await self._registry.register(
            name=name,
            model_type=model_type,
            metrics=metrics,
            parameters=parameters,
            feature_version=feature_version,
            dataset_version=dataset_version,
            mlflow_run_id=run_id,
            artifact_path=str(artifacts_dir),
            file_path=str(dest_path),
        )

        if stage and stage != "development":
            await self._registry.transition(model_record["uuid"], stage)

        logger.info("research model imported: %s v%d (%s)", name, model_record["version"], stage)
        return {
            "model_version_uuid": model_record["uuid"],
            "model_name": name,
            "model_version": model_record["version"],
            "stage": stage,
            "file_path": str(dest_path),
        }
