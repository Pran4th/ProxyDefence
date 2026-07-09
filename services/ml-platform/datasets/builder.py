from __future__ import annotations

import uuid as uuidlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from config import DATASET_DIR
from datasets.loader import EnergyServiceLoader, MockDataLoader
from datasets.splitter import DatasetSplitter

logger = get_logger(__name__)


class DatasetBuilder:
    def __init__(self, loader: Any = None, splitter: DatasetSplitter | None = None):
        self._loader = loader or EnergyServiceLoader()
        self._splitter = splitter or DatasetSplitter()

    def _derive_target(self, df: pd.DataFrame, target_column: str) -> pd.DataFrame:
        if "criticality" in df.columns:
            cmap = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            df[target_column] = df["criticality"].map(cmap).fillna(1).astype(int)
        else:
            num_cols = df.select_dtypes(include=[np.number]).columns
            if len(num_cols) > 0:
                df[target_column] = pd.qcut(
                    df[num_cols].sum(axis=1) / max(len(num_cols), 1), 4, labels=[0, 1, 2, 3], duplicates="drop",
                ).astype(int)
            else:
                df[target_column] = 1
        return df

    async def build(
        self, name: str, target_column: str = "criticality_score",
        feature_names: list[str] | None = None,
    ) -> dict[str, Any]:
        df = self._loader.load()
        if df.empty:
            df = MockDataLoader().load()
            logger.info("DatasetBuilder: using synthetic data (%d records)", len(df))

        if target_column not in df.columns:
            df = self._derive_target(df, target_column)

        if feature_names:
            available = [c for c in feature_names if c in df.columns]
            cols = available + ([target_column] if target_column in df.columns else [])
            if cols:
                df = df[cols]

        X_train, X_val, X_test, y_train, y_val, y_test = self._splitter.split(df, target_column)

        version_dir = Path(DATASET_DIR) / name / "latest"
        version_dir.mkdir(parents=True, exist_ok=True)

        train_df = X_train.copy()
        train_df[target_column] = y_train.values
        val_df = X_val.copy()
        val_df[target_column] = y_val.values
        test_df = X_test.copy()
        test_df[target_column] = y_test.values

        for split_name, split_df in (("train", train_df), ("validation", val_df), ("test", test_df)):
            if not split_df.empty:
                split_df.to_parquet(version_dir / f"{split_name}.parquet", index=False)

        result_uuid = str(uuidlib.uuid4())
        feature_count = len(df.columns) - (1 if target_column in df.columns else 0)

        return {
            "uuid": result_uuid,
            "name": name,
            "version": 1,
            "path": str(version_dir),
            "total_records": len(df),
            "train_records": len(X_train),
            "val_records": len(X_val),
            "test_records": len(X_test),
            "target_column": target_column,
            "feature_count": feature_count,
            "splits": {"train": len(X_train), "validation": len(X_val), "test": len(X_test)},
        }
