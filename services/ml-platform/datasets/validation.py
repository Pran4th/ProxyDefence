from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    passed: bool
    validation_type: str
    details: dict[str, Any] | None = None
    severity: str = "error"
    message: str = ""


def check_duplicates(df: pd.DataFrame) -> ValidationResult:
    dup_count = int(df.duplicated().sum())
    return ValidationResult(
        passed=dup_count == 0,
        validation_type="duplicates",
        details={"duplicate_count": dup_count},
        message=f"{dup_count} duplicate rows found" if dup_count else "No duplicates",
    )


def check_missing_values(df: pd.DataFrame, threshold: float = 0.1) -> ValidationResult:
    missing_rate = float(df.isnull().mean().mean())
    return ValidationResult(
        passed=missing_rate <= threshold,
        validation_type="missing_values",
        details={"missing_rate": round(missing_rate, 4)},
        message=f"Missing rate {missing_rate:.2%} exceeds threshold {threshold:.0%}" if missing_rate > threshold else "Missing rate OK",
    )


def check_outliers(df: pd.DataFrame, zscore_threshold: float = 3.0) -> ValidationResult:
    num_df = df.select_dtypes(include=[np.number])
    outlier_count = 0
    for col in num_df.columns:
        col_data = num_df[col].dropna()
        if len(col_data) > 0:
            std = max(float(col_data.std()), 1e-10)
            zs = np.abs((col_data - col_data.mean()) / std)
            outlier_count += int((zs > zscore_threshold).sum())
    n_total = int(num_df.size)
    outlier_rate = outlier_count / n_total if n_total > 0 else 0.0
    return ValidationResult(
        passed=outlier_rate <= 0.05,
        validation_type="outliers",
        details={"outlier_count": outlier_count, "outlier_rate": round(outlier_rate, 4)},
        message=f"{outlier_count} outliers ({outlier_rate:.1%})" if outlier_rate > 0.05 else "Outlier rate OK",
    )


def check_column_validity(df: pd.DataFrame) -> ValidationResult:
    invalid_cols = [c for c in df.columns if pd.api.types.is_interval_dtype(df[c])]
    return ValidationResult(
        passed=len(invalid_cols) == 0,
        validation_type="column_validity",
        details={"invalid_columns": invalid_cols},
    )


DEFAULT_VALIDATORS: list[tuple[str, Callable[[pd.DataFrame], ValidationResult]]] = [
    ("column_validity", check_column_validity),
    ("duplicates", check_duplicates),
    ("missing_values", check_missing_values),
    ("outliers", check_outliers),
]

FULL_VALIDATORS: list[tuple[str, Callable[[pd.DataFrame], ValidationResult]]] = DEFAULT_VALIDATORS[:]


def default_validators() -> list[tuple[str, Callable[[pd.DataFrame], ValidationResult]]]:
    return DEFAULT_VALIDATORS


def full_validators() -> list[tuple[str, Callable[[pd.DataFrame], ValidationResult]]]:
    return FULL_VALIDATORS


class DatasetValidationPipeline:
    def __init__(self):
        self._validators: list[tuple[str, Callable[[pd.DataFrame], ValidationResult]]] = []

    def add_validator(self, name: str, fn: Callable[[pd.DataFrame], ValidationResult]):
        self._validators.append((name, fn))

    async def validate(self, df: pd.DataFrame, dataset_name: str, version: int) -> dict[str, Any]:
        validators = self._validators or DEFAULT_VALIDATORS
        results = []
        for vname, vfunc in validators:
            try:
                r = vfunc(df)
                results.append({
                    "validation_type": r.validation_type,
                    "passed": r.passed,
                    "details": r.details or {},
                    "severity": r.severity,
                    "message": r.message,
                })
            except Exception as e:
                results.append({
                    "validation_type": vname,
                    "passed": False,
                    "details": {"error": str(e)},
                    "severity": "error",
                    "message": str(e),
                })
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        logger.info("validation complete", dataset=dataset_name, version=version, passed=passed, total=total)
        return {
            "dataset_name": dataset_name,
            "version": version,
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "results": results,
        }
