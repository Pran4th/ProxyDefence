from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureValidationResult:
    feature_name: str
    data_type: str = ""
    null_percentage: float = 0.0
    expected_range: list[float] | None = None
    actual_min: float | None = None
    actual_max: float | None = None
    unique_values: int = 0
    cardinality: float = 0.0
    variance: float = 0.0
    correlation_with_target: float | None = None
    mutual_information: float | None = None
    drift_baseline: dict[str, Any] = field(default_factory=dict)
    leakage_flag: bool = False
    importance_placeholder: float = 0.0
    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    distribution: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "data_type": self.data_type,
            "null_percentage": self.null_percentage,
            "expected_range": self.expected_range,
            "actual_min": self.actual_min,
            "actual_max": self.actual_max,
            "unique_values": self.unique_values,
            "cardinality": self.cardinality,
            "variance": self.variance,
            "correlation_with_target": self.correlation_with_target,
            "mutual_information": self.mutual_information,
            "leakage_flag": self.leakage_flag,
            "passed": self.passed,
            "warnings": self.warnings,
        }


class FeatureValidator:
    def __init__(self, null_threshold: float = 0.5, cardinality_threshold: float = 0.95,
                 variance_threshold: float = 1e-10):
        self._null_threshold = null_threshold
        self._cardinality_threshold = cardinality_threshold
        self._variance_threshold = variance_threshold

    def validate(self, df: pd.DataFrame, target_column: str | None = None,
                 feature_configs: list[dict[str, Any]] | None = None) -> dict[str, FeatureValidationResult]:
        config_map = {}
        if feature_configs:
            for fc in feature_configs:
                if "name" in fc:
                    config_map[fc["name"]] = fc

        results = {}
        for col in df.columns:
            if col == target_column:
                continue
            result = self._validate_feature(df, col, target_column, config_map.get(col, {}))
            results[col] = result
            if not result.passed:
                logger.warning("feature '%s' failed validation: %s", col, "; ".join(result.warnings))

        n_total = len(results)
        n_passed = sum(1 for r in results.values() if r.passed)
        logger.info("feature validation: %d/%d passed", n_passed, n_total)
        return results

    def _validate_feature(self, df: pd.DataFrame, col: str, target: str | None,
                           config: dict[str, Any]) -> FeatureValidationResult:
        col_data = df[col].dropna()
        result = FeatureValidationResult(feature_name=col)
        result.data_type = str(df[col].dtype)

        null_pct = float(df[col].isnull().mean())
        result.null_percentage = round(null_pct, 6)
        if null_pct > self._null_threshold:
            result.warnings.append(f"null percentage {null_pct:.2%} exceeds threshold {self._null_threshold:.0%}")
            result.passed = False

        if "expected_range" in config and config["expected_range"]:
            result.expected_range = config["expected_range"]

        if pd.api.types.is_numeric_dtype(df[col].dtype) and not pd.api.types.is_bool_dtype(df[col].dtype):
            self._validate_numeric(col_data, result)
        else:
            self._validate_categorical(col_data, result)

        if target and target in df.columns and pd.api.types.is_numeric_dtype(df[col].dtype):
            try:
                valid = df[[col, target]].dropna()
                if len(valid) > 1:
                    corr = valid[col].corr(valid[target])
                    result.correlation_with_target = round(float(corr), 6)
                    if abs(corr) > 0.95:
                        result.warnings.append(f"near-perfect correlation with target: {corr:.4f}")
                        result.leakage_flag = True
            except Exception:
                pass

        if result.unique_values > 0:
            result.cardinality = round(result.unique_values / max(len(col_data), 1), 6)
            if result.cardinality > self._cardinality_threshold and len(col_data) > 100:
                if "id" not in col.lower() and "uuid" not in col.lower():
                    result.warnings.append(f"high cardinality: {result.cardinality:.2%}")

        return result

    def _validate_numeric(self, col_data: pd.Series, result: FeatureValidationResult):
        if len(col_data) == 0:
            result.warnings.append("empty column after dropping nulls")
            result.passed = False
            return
        result.actual_min = round(float(col_data.min()), 6)
        result.actual_max = round(float(col_data.max()), 6)
        result.unique_values = int(col_data.nunique())
        result.variance = round(float(col_data.var()), 6) if len(col_data) > 1 else 0.0
        if result.variance < self._variance_threshold:
            result.warnings.append(f"near-zero variance: {result.variance}")
            result.passed = False
        result.distribution = {
            "mean": round(float(col_data.mean()), 6),
            "std": round(float(col_data.std()), 6),
            "min": result.actual_min,
            "max": result.actual_max,
            "p25": round(float(col_data.quantile(0.25)), 6),
            "p50": round(float(col_data.median()), 6),
            "p75": round(float(col_data.quantile(0.75)), 6),
            "skew": round(float(col_data.skew()), 6),
            "kurtosis": round(float(col_data.kurtosis()), 6),
        }

    def _validate_categorical(self, col_data: pd.Series, result: FeatureValidationResult):
        if len(col_data) == 0:
            result.warnings.append("empty column after dropping nulls")
            result.passed = False
            return
        result.unique_values = int(col_data.nunique())
        vc = col_data.value_counts()
        result.distribution = {
            "top_values": {str(k): int(v) for k, v in vc.head(10).items()},
            "entropy": round(float(-(vc / len(col_data) * np.log2(vc / len(col_data) + 1e-10)).sum()), 6),
        }
