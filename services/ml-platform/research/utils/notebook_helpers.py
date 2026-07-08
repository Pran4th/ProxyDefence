import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from config import DATASET_DIR, REPORT_DIR, ARTIFACT_DIR
from research.utils.seed import SeedManager
from research.utils.experiment_logger import ExperimentLogger

logger = get_logger(__name__)


class NotebookHelpers:
    @staticmethod
    def load_dataset(name: str, version: int | None = None, split: str = "train") -> pd.DataFrame:
        if version:
            path = Path(DATASET_DIR) / name / f"v{version}" / f"{split}.parquet"
        else:
            versions = sorted((Path(DATASET_DIR) / name).iterdir()) if (Path(DATASET_DIR) / name).exists() else []
            path = versions[-1] / f"{split}.parquet" if versions else Path()
        if path.exists():
            return pd.read_parquet(path)
        raise FileNotFoundError(f"Dataset not found: {path}")

    @staticmethod
    def load_metadata(name: str, version: int | None = None) -> dict:
        if version:
            path = Path(DATASET_DIR) / name / f"v{version}" / "metadata.json"
        else:
            versions = sorted((Path(DATASET_DIR) / name).iterdir()) if (Path(DATASET_DIR) / name).exists() else []
            path = versions[-1] / "metadata.json" if versions else Path()
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    @staticmethod
    def get_config_path(name: str) -> str | None:
        path = Path(f"research/configs/{name}.yaml")
        if path.exists():
            return str(path)
        path = Path(f"research/configs/{name}.json")
        return str(path) if path.exists() else None

    @staticmethod
    def describe_dataframe(df: pd.DataFrame, name: str = "DataFrame") -> dict:
        info = {
            "name": name,
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
            "missing_values": {c: int(df[c].isnull().sum()) for c in df.columns},
            "missing_rate": {c: round(float(df[c].isnull().mean()), 4) for c in df.columns},
            "unique_values": {c: int(df[c].nunique()) for c in df.columns},
        }
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            info["numeric_stats"] = df[numeric_cols].describe().to_dict()
        return info

    @staticmethod
    def log_to_file(logger_name: str, data: dict, output_dir: str | None = None):
        out_dir = Path(output_dir or REPORT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{logger_name}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("notebook log saved to %s", path)
        return str(path)
