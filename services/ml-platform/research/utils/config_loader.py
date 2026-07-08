import json
import os
from pathlib import Path
from typing import Any

import yaml

from backend.shared.logging_config import get_logger
from research.config import ResearchConfigLoader

logger = get_logger(__name__)


class ConfigLoader:
    def __init__(self, config_dir: str | None = None):
        self._experiment_loader = ResearchConfigLoader(config_dir)

    def load_experiment(self, name_or_path: str) -> dict:
        return self._experiment_loader.load(name_or_path)

    def load_yaml(self, path: str) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    def load_json(self, path: str) -> dict:
        with open(path) as f:
            return json.load(f)

    def merge_configs(self, *configs: dict) -> dict:
        merged: dict = {}
        for cfg in configs:
            merged = self._deep_merge(merged, cfg)
        return merged

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = dict(base)
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = self._deep_merge(result[key], val)
            else:
                result[key] = val
        return result

    def resolve_env_vars(self, config: dict) -> dict:
        resolved = {}
        for key, val in config.items():
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                env_var = val[2:-1]
                default = None
                if ":-" in env_var:
                    env_var, default = env_var.split(":-", 1)
                resolved[key] = os.getenv(env_var, default)
            elif isinstance(val, dict):
                resolved[key] = self.resolve_env_vars(val)
            elif isinstance(val, list):
                resolved[key] = [
                    self.resolve_env_vars(item) if isinstance(item, dict) else item
                    for item in val
                ]
            else:
                resolved[key] = val
        return resolved
