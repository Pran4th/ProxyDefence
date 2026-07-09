from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from config import DATASET_DIR

logger = get_logger(__name__)


class SchemaRegistry:
    def __init__(self, base_dir: str | None = None):
        self._base_dir = Path(base_dir or DATASET_DIR) / "_schemas"

    @staticmethod
    def infer_schema(df: pd.DataFrame) -> dict[str, Any]:
        return {
            "columns": list(df.columns),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "shape": list(df.shape),
        }

    def register_schema(self, dataset_name: str, version: int, df: pd.DataFrame) -> dict[str, Any]:
        schema = self.infer_schema(df)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._base_dir / f"{dataset_name}_v{version}.json"
        path.write_text(json.dumps(schema, indent=2, default=str))
        logger.info("schema registered", dataset=dataset_name, version=version, columns=len(schema["columns"]))
        return schema

    def get_schema(self, dataset_name: str, version: int) -> dict[str, Any] | None:
        path = self._base_dir / f"{dataset_name}_v{version}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def compare_schemas(self, schema_a: dict[str, Any], schema_b: dict[str, Any]) -> dict[str, Any]:
        cols_a, cols_b = set(schema_a.get("columns", [])), set(schema_b.get("columns", []))
        added = sorted(cols_b - cols_a)
        removed = sorted(cols_a - cols_b)
        dtype_changes = {}
        for col in cols_a & cols_b:
            da = schema_a.get("dtypes", {}).get(col)
            db = schema_b.get("dtypes", {}).get(col)
            if da != db:
                dtype_changes[col] = {"from": da, "to": db}
        return {
            "compatible": not added and not removed and not dtype_changes,
            "added_columns": added,
            "removed_columns": removed,
            "dtype_changes": dtype_changes,
        }
