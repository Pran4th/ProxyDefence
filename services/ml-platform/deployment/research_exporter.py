import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib

from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR

logger = get_logger(__name__)

EXPORT_CONFIG_SCHEMA = {
    "model_name": "str (required)",
    "model_type": "str: logistic_regression|decision_tree|random_forest|xgboost|lightgbm|catboost",
    "experiment_id": "str (required)",
    "run_id": "str (required)",
    "parameters": "dict",
    "metrics": "dict",
    "feature_version": "int (default 1)",
    "dataset_version": "int (default 1)",
    "tags": "dict",
    "description": "str",
}


class ResearchConfig:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self._data = json.load(f)
        self.model_name: str = self._data.get("model_name", "unnamed_model")
        self.model_type: str = self._data.get("model_type", "xgboost")
        self.experiment_id: str = self._data.get("experiment_id", "local")
        self.run_id: str = self._data.get("run_id", "local")
        self.parameters: dict = self._data.get("parameters", {})
        self.metrics: dict = self._data.get("metrics", {})
        self.feature_version: int = self._data.get("feature_version", 1)
        self.dataset_version: int = self._data.get("dataset_version", 1)
        self.tags: dict = self._data.get("tags", {})
        self.description: str = self._data.get("description", "")
        self._validate()

    def _validate(self):
        assert self.model_name, "model_name is required"
        assert self.experiment_id, "experiment_id is required"
        assert self.run_id, "run_id is required"

    def to_dict(self) -> dict:
        return dict(self._data)


class ResearchExporter:
    def __init__(self, output_dir: str = ""):
        self._output_dir = Path(output_dir or ARTIFACT_DIR) / "research_exports"

    def export(self, model: Any, config: ResearchConfig | dict) -> str:
        if isinstance(config, dict):
            cfg = config
        else:
            cfg = config.to_dict()

        model_name = cfg.get("model_name", "unnamed_model")
        run_id = cfg.get("run_id", "local")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        export_dir = self._output_dir / f"{model_name}_{run_id}_{timestamp}"
        export_dir.mkdir(parents=True, exist_ok=True)

        model_path = export_dir / "model.joblib"
        joblib.dump(model, str(model_path))

        config_path = export_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=2, default=str)

        readme_path = export_dir / "README.md"
        with open(readme_path, "w") as f:
            f.write(self._generate_readme(cfg, model_path))

        logger.info("research model exported to %s", export_dir)
        return str(export_dir)

    def _generate_readme(self, config: dict, model_path: Path) -> str:
        lines = [
            f"# {config.get('model_name', 'unnamed_model')}",
            f"**Type:** {config.get('model_type', 'unknown')}",
            f"**Experiment:** {config.get('experiment_id', 'N/A')}",
            f"**Run:** {config.get('run_id', 'N/A')}",
            f"**Exported:** {datetime.utcnow().isoformat()}Z",
            f"**Model File:** {model_path.name}",
            "",
        ]
        metrics = config.get("metrics", {})
        if metrics:
            lines.append("## Metrics")
            for k, v in metrics.items():
                lines.append(f"- {k}: {v}")
        params = config.get("parameters", {})
        if params:
            lines.append("## Parameters")
            for k, v in params.items():
                lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def list_exports(self) -> list[dict[str, Any]]:
        if not self._output_dir.exists():
            return []
        exports = []
        for d in sorted(self._output_dir.iterdir()):
            if d.is_dir():
                config_path = d / "config.json"
                model_path = d / "model.joblib"
                exports.append({
                    "path": str(d),
                    "name": d.name,
                    "has_config": config_path.exists(),
                    "has_model": model_path.exists(),
                    "exported_at": datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
                })
        return exports


def export_config_schema() -> dict:
    return EXPORT_CONFIG_SCHEMA
