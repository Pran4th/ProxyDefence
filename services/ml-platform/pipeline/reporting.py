import json
from typing import Any

import numpy as np
import pandas as pd


class ClassBalanceReport:
    def __init__(self, y: pd.Series):
        self._y = y

    def generate(self) -> dict[str, Any]:
        counts = self._y.value_counts().sort_index()
        total = len(self._y)
        majority = counts.max()
        return {
            "num_classes": len(counts),
            "class_counts": counts.to_dict(),
            "class_percentages": (counts / total * 100).round(2).to_dict(),
            "imbalance_ratios": {
                str(k): round(majority / v, 2) for k, v in counts.items()
            },
            "majority_class": int(counts.idxmax()),
            "minority_class": int(counts.idxmin()),
            "imbalance_ratio": round(majority / counts.min(), 2),
        }


class DataQualityReport:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def generate(self) -> dict[str, Any]:
        report = {}
        for col in self._df.columns:
            col_data = self._df[col]
            info: dict[str, Any] = {
                "dtype": str(col_data.dtype),
                "missing_count": int(col_data.isna().sum()),
                "missing_pct": round(col_data.isna().mean() * 100, 2),
                "unique_count": int(col_data.nunique()),
            }
            if pd.api.types.is_numeric_dtype(col_data):
                info.update({
                    "min": float(col_data.min()) if not col_data.isna().all() else None,
                    "max": float(col_data.max()) if not col_data.isna().all() else None,
                    "mean": float(col_data.mean()) if not col_data.isna().all() else None,
                    "std": float(col_data.std()) if not col_data.isna().all() else None,
                })
            report[col] = info
        return {
            "num_rows": len(self._df),
            "num_columns": len(self._df.columns),
            "total_cells": len(self._df) * len(self._df.columns),
            "total_missing": int(self._df.isna().sum().sum()),
            "overall_missing_pct": round(self._df.isna().mean().mean() * 100, 2),
            "columns": report,
        }


class FeatureCorrelationReport:
    def __init__(self, df: pd.DataFrame, threshold: float = 0.95):
        self._df = df
        self._threshold = threshold

    def generate(self) -> dict[str, Any]:
        numeric = self._df.select_dtypes(include=[np.number])
        if numeric.shape[1] < 2:
            return {"highly_correlated_pairs": [], "message": "not enough numeric columns"}
        corr = numeric.corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        pairs = [
            {"col1": col1, "col2": col2, "correlation": round(upper[col1][col2], 3)}
            for col2 in upper.columns for col1 in upper.index
            if not np.isnan(upper[col1][col2]) and upper[col1][col2] > self._threshold
        ]
        return {
            "highly_correlated_pairs": sorted(pairs, key=lambda x: -x["correlation"]),
            "threshold": self._threshold,
            "total_pairs_above_threshold": len(pairs),
        }
