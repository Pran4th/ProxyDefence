import json
import os
from pathlib import Path
from typing import Any

import yaml

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

RESEARCH_DIR = Path(os.getenv("RESEARCH_DIR", "./research"))


class ConfigValidationError(Exception):
    pass


class ResearchConfigLoader:
    def __init__(self, config_dir: str | None = None):
        self._config_dir = Path(config_dir or RESEARCH_DIR / "configs")
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def load(self, path: str) -> dict[str, Any]:
        p = Path(path)
        if not p.is_absolute():
            p = self._config_dir / p
        if not p.exists():
            raise FileNotFoundError(f"Config not found: {p}")
        ext = p.suffix.lower()
        with open(p) as f:
            if ext in (".yaml", ".yml"):
                config = yaml.safe_load(f)
            elif ext == ".json":
                config = json.load(f)
            else:
                raise ValueError(f"Unsupported config format: {ext}")
        return self._validate(config)

    def _validate(self, config: dict) -> dict:
        if "experiment" not in config:
            raise ConfigValidationError("Config must contain 'experiment' section")
        exp = config["experiment"]
        required = ["name", "type"]
        for r in required:
            if r not in exp:
                raise ConfigValidationError(f"Missing required field: experiment.{r}")
        return config

    def save(self, config: dict, name: str, format: str = "yaml") -> str:
        path = self._config_dir / f"{name}.{format}"
        with open(path, "w") as f:
            if format == "yaml":
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(config, f, indent=2)
        logger.info("config saved to %s", path)
        return str(path)

    def list_configs(self, config_type: str | None = None) -> list[dict[str, Any]]:
        configs = []
        for p in sorted(self._config_dir.glob("*.yaml")):
            cfg = {"name": p.stem, "path": str(p), "format": "yaml", "size": p.stat().st_size}
            try:
                data = self.load(str(p))
                exp = data.get("experiment", {})
                cfg["experiment_name"] = exp.get("name")
                cfg["experiment_type"] = exp.get("type")
                cfg["has_dataset"] = "dataset" in data
                cfg["has_model"] = "model" in data
            except Exception:
                cfg["valid"] = False
            configs.append(cfg)
        for p in sorted(self._config_dir.glob("*.json")):
            if {"path": str(p)} not in [{"path": str(c["path"])} for c in configs]:
                cfg = {"name": p.stem, "path": str(p), "format": "json", "size": p.stat().st_size}
                try:
                    data = self.load(str(p))
                    exp = data.get("experiment", {})
                    cfg["experiment_name"] = exp.get("name")
                    cfg["experiment_type"] = exp.get("type")
                except Exception:
                    cfg["valid"] = False
                configs.append(cfg)
        return configs

    @staticmethod
    def build_default_config(name: str, experiment_type: str = "classification") -> dict:
        return {
            "experiment": {
                "name": name,
                "type": experiment_type,
                "description": "",
                "author": "system",
                "random_seed": 42,
                "tags": [],
            },
            "dataset": {
                "name": "",
                "version": 1,
                "target_column": "",
                "test_size": 0.2,
                "val_size": 0.1,
                "feature_names": [],
            },
            "model": {
                "type": "xgboost",
                "parameters": {},
                "evaluation": {
                    "metrics": ["accuracy", "f1", "precision", "recall"],
                    "cross_validation": {"folds": 5, "stratify": True},
                },
            },
            "export": {
                "format": "joblib",
                "register": False,
                "stage": "development",
            },
        }
