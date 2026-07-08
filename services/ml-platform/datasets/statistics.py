from __future__ import annotations

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DatasetStatistics:
    @staticmethod
    async def compute(
        df: pd.DataFrame, dataset_name: str, version: int,
    ) -> dict:
        stats = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_bytes": int(df.memory_usage(deep=True).sum()),
            "missing_cells": int(df.isnull().sum().sum()),
            "total_cells": df.size,
            "duplicate_count": int(df.duplicated().sum()),
            "duplicate_rate": round(float(df.duplicated().mean()), 6),
            "missing_rate": round(float(df.isnull().mean().mean()), 6),
            "numerical_columns": int(len(df.select_dtypes(include=[np.number]).columns)),
            "categorical_columns": int(len(df.select_dtypes(include=["object", "category"]).columns)),
            "boolean_columns": int(len(df.select_dtypes(include=["bool"]).columns)),
            "datetime_columns": int(len(df.select_dtypes(include=["datetime64"]).columns)),
            "stats_json": {},
        }
        logger.info(
            "statistics computed",
            dataset=dataset_name,
            version=version,
            rows=stats["row_count"],
            cols=stats["column_count"],
        )
        return stats
