from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from dataset_factory.normalized import ISO_COUNTRY_MAP

logger = get_logger(__name__)

_URL_PATTERN = re.compile(
    r"^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b"
    r"(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$"
)
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_ISO_DT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$"
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass
class CleaningAction:
    action_name: str
    column: str
    records_affected: int
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_name": self.action_name,
            "column": self.column,
            "records_affected": self.records_affected,
            "description": self.description,
            "details": self.details,
        }


@dataclass
class CleaningReport:
    dataset_name: str
    version: int
    before_shape: tuple[int, int]
    after_shape: tuple[int, int] = (0, 0)
    actions: list[CleaningAction] = field(default_factory=list)
    before_stats: dict[str, Any] = field(default_factory=dict)
    after_stats: dict[str, Any] = field(default_factory=dict)
    quarantined_records: int = 0
    quarantine_path: str = ""
    warnings: list[str] = field(default_factory=list)
    timestamp: str = ""

    def add_action(self, action: CleaningAction):
        self.actions.append(action)

    def summary(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "before_rows": self.before_shape[0],
            "before_columns": self.before_shape[1],
            "after_rows": self.after_shape[0],
            "after_columns": self.after_shape[1],
            "rows_removed": self.before_shape[0] - self.after_shape[0],
            "total_actions": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
            "quarantined_records": self.quarantined_records,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }


class CleaningPipeline:
    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._actions: list[CleaningAction] = []

    def clean(self, df: pd.DataFrame, dataset_name: str = "", version: int = 1,
              target_column: str | None = None) -> tuple[pd.DataFrame, CleaningReport]:
        report = CleaningReport(
            dataset_name=dataset_name,
            version=version,
            before_shape=df.shape,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        report.before_stats = self._compute_stats(df, "before")

        steps: list[tuple[str, Callable[[pd.DataFrame], pd.DataFrame], str]] = [
            ("remove_duplicates", self._remove_duplicates, "remove duplicate rows"),
            ("clean_whitespace", self._clean_whitespace, "strip/compress whitespace in string columns"),
            ("fix_utf8", self._fix_utf8, "repair malformed UTF-8 in string columns"),
            ("normalize_categoricals", self._normalize_categoricals, "lowercase/strip categorical values"),
            ("validate_countries", self._validate_countries, "validate and normalize country codes"),
            ("validate_coordinates", self._validate_coordinates, "validate lat/lng bounds"),
            ("validate_timestamps", self._validate_timestamps, "coerce and validate timestamps"),
            ("repair_malformed_urls", self._repair_malformed_urls, "fix malformed URL patterns"),
            ("handle_missing_values", self._handle_missing_values, "apply missing value strategies"),
            ("detect_outliers", self._detect_outliers, "flag IQR outliers"),
        ]

        for name, func, desc in steps:
            before_count = len(df)
            df = func(df)
            affected = before_count - len(df)
            removed = abs(df.isnull().sum().sum() - report.before_stats.get("total_missing", 0))
            if affected > 0 or removed > 0:
                action = CleaningAction(name, "*", affected, desc)
                self._actions.append(action)
                report.add_action(action)

        report.after_shape = df.shape
        report.after_stats = self._compute_stats(df, "after")

        logger.info("cleaning complete: %s -> %s rows (%d actions)",
                     report.before_shape[0], report.after_shape[0], len(report.actions))
        return df, report

    def _compute_stats(self, df: pd.DataFrame, label: str) -> dict[str, Any]:
        return {
            "rows": len(df),
            "cols": len(df.columns),
            "total_cells": df.size,
            "total_missing": int(df.isnull().sum().sum()),
            "missing_rate": round(float(df.isnull().sum().sum() / df.size), 6) if df.size > 0 else 0.0,
            "duplicate_count": int(df.duplicated().sum()),
            "duplicate_rate": round(float(df.duplicated().sum() / len(df)), 6) if len(df) > 0 else 0.0,
            "memory_bytes": int(df.memory_usage(deep=True).sum()),
        }

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates()
        if len(df) < before:
            logger.info("removed %d duplicate rows", before - len(df))
        return df

    def _clean_whitespace(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object"]).columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype(str).str.strip().replace(
                    r"\s+", " ", regex=True
                ).replace("nan", None).replace("None", None).replace("NaN", None)
        return df

    def _fix_utf8(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].apply(
                lambda x: x.encode("utf-8", errors="replace").decode("utf-8")
                if isinstance(x, str) else x
            )
        return df

    def _normalize_categoricals(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object", "category"]).columns:
            if df[col].nunique() < 0.5 * len(df):
                df[col] = df[col].astype(str).str.strip().str.lower().replace(
                    {"nan": None, "none": None, "null": None, "": None}
                )
                try:
                    df[col] = df[col].astype("category")
                except Exception:
                    pass
        return df

    def _validate_countries(self, df: pd.DataFrame) -> pd.DataFrame:
        country_keywords = ["country", "iso", "nation", "location_code", "iso_code"]
        for col in df.columns:
            col_lower = col.lower()
            if any(k in col_lower for k in country_keywords):
                df[col] = df[col].apply(
                    lambda x: ISO_COUNTRY_MAP.get(str(x).strip().lower(), x)
                    if pd.notna(x) else x
                )
        return df

    def _validate_coordinates(self, df: pd.DataFrame) -> pd.DataFrame:
        lat_cols = [c for c in df.columns if "lat" in c.lower() and c.lower() not in ("latitude",)]
        lng_cols = [c for c in df.columns if any(k in c.lower() for k in ("lon", "lng"))]
        if "latitude" in df.columns:
            lat_cols.append("latitude")
        if "longitude" in df.columns:
            lng_cols.append("longitude")

        for col in lat_cols + lng_cols:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col].dtype):
                threshold = 90 if col in lat_cols else 180
                df.loc[df[col].abs() > threshold, col] = None
        return df

    def _validate_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        ts_keywords = ["timestamp", "date", "time", "published", "created", "updated"]
        for col in df.columns:
            col_lower = col.lower()
            if any(k == col_lower or (k in col_lower and col_lower.endswith(k)) for k in ts_keywords):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass
        return df

    def _repair_malformed_urls(self, df: pd.DataFrame) -> pd.DataFrame:
        url_keywords = ["url", "link", "website", "source_url", "reference"]
        for col in df.columns:
            col_lower = col.lower()
            if any(k in col_lower for k in url_keywords):
                valid_mask = df[col].dropna().apply(
                    lambda x: bool(_URL_PATTERN.match(str(x))) if pd.notna(x) else True
                )
                invalid_idx = df[col].dropna().index[~valid_mask]
                if len(invalid_idx) > 0:
                    logger.info("flagged %d malformed URLs in column %s", len(invalid_idx), col)
        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        threshold = self._config.get("null_ratio_threshold", 0.5)
        high_missing = [c for c in df.columns if df[c].isnull().mean() > threshold]
        if high_missing:
            logger.info("dropping %d columns with >%.0f%% missing: %s",
                         len(high_missing), threshold * 100, high_missing[:5])
            df = df.drop(columns=high_missing)

        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype)]
        for col in numeric_cols:
            if df[col].isnull().any():
                df[col] = df[col].fillna(df[col].median())

        for col in df.select_dtypes(include=["object", "category"]).columns:
            if df[col].isnull().any():
                df[col] = df[col].fillna("unknown")

        return df

    def _detect_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        multiplier = self._config.get("outlier_iqr_multiplier", 3.0)
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype)
                        and not pd.api.types.is_bool_dtype(df[c].dtype)]
        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) < 4:
                continue
            q1, q3 = col_data.quantile(0.25), col_data.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - multiplier * iqr
            upper = q3 + multiplier * iqr
            outlier_mask = (df[col] < lower) | (df[col] > upper)
            n_outliers = outlier_mask.sum()
            if n_outliers > 0:
                df.loc[outlier_mask, col] = col_data.median()
                logger.debug("capped %d outliers in %s (IQR * %.1f)", n_outliers, col, multiplier)
        return df
