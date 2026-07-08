from __future__ import annotations

import uuid as uuid_mod
from pathlib import Path
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from datasets.loader import EnergyServiceLoader, MockDataLoader
from datasets.splitter import DatasetSplitter

logger = get_logger(__name__)


class DatasetBuilder:
    def __init__(self, loader: EnergyServiceLoader | None = None,
                 splitter: DatasetSplitter | None = None):
        self._loader = loader or EnergyServiceLoader()
        self._splitter = splitter or DatasetSplitter()

    async def build(self, name: str, target_column: str = "criticality_score",
                    feature_names: list[str] | None = None) -> dict[str, Any]:
        logger.info("building dataset", name=name, target=target_column)

        df = self._loader.load()
        if df.empty:
            df = MockDataLoader().load()
            logger.info("using synthetic data (%d records)", len(df))

        if target_column not in df.columns:
            if "criticality" in df.columns:
                cmap = {"low": 0, "medium": 1, "high": 2, "critical": 3}
                df[target_column] = df["criticality"].map(cmap).fillna(1).astype(int)
            else:
                df[target_column] = 1

        if feature_names:
            available = [c for c in feature_names if c in df.columns]
            missing = [c for c in feature_names if c not in df.columns]
            if missing:
                logger.warning("requested features not found: %s", missing)
            cols = available + ([target_column] if target_column in df.columns else [])
            if cols:
                df = df[cols]

        X_train, X_val, X_test, y_train, y_val, y_test = self._splitter.split(df, target_column)

        version = 1
        ds_uuid = str(uuid_mod.uuid4())
        version_dir = Path(f"datasets/{name}/v{version}")
        version_dir.mkdir(parents=True, exist_ok=True)

        def _save(split_df: pd.DataFrame, split_name: str):
            if not split_df.empty:
                f = split_df.copy()
                f[target_column] = y_train.values if split_name == "train" else (
                    y_val.values if split_name == "validation" else y_test.values)
                f.to_parquet(version_dir / f"{split_name}.parquet", index=False)

        _save(X_train, "train")
        _save(X_val, "validation")
        _save(X_test, "test")

        result = {
            "uuid": ds_uuid,
            "name": name,
            "version": version,
            "path": str(version_dir),
            "total_records": len(df),
            "train_records": len(X_train),
            "val_records": len(X_val),
            "test_records": len(X_test),
            "target_column": target_column,
            "feature_count": len(X_train.columns),
        }

        logger.info("dataset built", name=name, version=version, records=result["total_records"])
        return result
