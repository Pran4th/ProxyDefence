from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class QualityReport:
    dataset_name: str
    version: int

    overall_score: float = 0.0

    completeness: float = 0.0
    consistency: float = 0.0
    integrity: float = 0.0
    validity: float = 0.0
    uniqueness: float = 0.0
    timeliness: float = 0.0
    coverage: float = 0.0

    dimension_details: dict[str, Any] = field(default_factory=dict)
    confidence_distribution: dict[str, Any] = field(default_factory=dict)
    country_distribution: dict[str, int] = field(default_factory=dict)
    temporal_coverage: dict[str, Any] = field(default_factory=dict)
    source_coverage: dict[str, int] = field(default_factory=dict)
    relationship_coverage: dict[str, Any] = field(default_factory=dict)
    missing_value_report: dict[str, Any] = field(default_factory=dict)
    duplicate_report: dict[str, Any] = field(default_factory=dict)
    outlier_report: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "overall_score": self.overall_score,
            "dimension_scores": {
                "completeness": self.completeness,
                "consistency": self.consistency,
                "integrity": self.integrity,
                "validity": self.validity,
                "uniqueness": self.uniqueness,
                "timeliness": self.timeliness,
                "coverage": self.coverage,
            },
            "dimension_details": self.dimension_details,
            "confidence_distribution": self.confidence_distribution,
            "country_distribution": self.country_distribution,
            "temporal_coverage": self.temporal_coverage,
            "source_coverage": self.source_coverage,
            "relationship_coverage": self.relationship_coverage,
            "missing_value_report": self.missing_value_report,
            "duplicate_report": self.duplicate_report,
            "outlier_report": self.outlier_report,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }


class QualityReportGenerator:
    def __init__(self):
        self._weights = {
            "completeness": 0.20,
            "consistency": 0.15,
            "integrity": 0.15,
            "validity": 0.20,
            "uniqueness": 0.10,
            "timeliness": 0.10,
            "coverage": 0.10,
        }

    def generate(self, df: pd.DataFrame, dataset_name: str, version: int,
                 target_column: str | None = None) -> QualityReport:
        report = QualityReport(
            dataset_name=dataset_name,
            version=version,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        report.completeness = self._score_completeness(df, report)
        report.consistency = self._score_consistency(df, report)
        report.integrity = self._score_integrity(df, report)
        report.validity = self._score_validity(df, report)
        report.uniqueness = self._score_uniqueness(df, report)
        report.timeliness = self._score_timeliness(df, report)
        report.coverage = self._score_coverage(df, report)

        report.confidence_distribution = self._compute_confidence_distribution(df)
        report.country_distribution = self._compute_country_distribution(df)
        report.temporal_coverage = self._compute_temporal_coverage(df)
        report.source_coverage = self._compute_source_coverage(df)
        report.relationship_coverage = self._compute_relationship_coverage(df)
        report.missing_value_report = self._compute_missing_report(df)
        report.duplicate_report = self._compute_duplicate_report(df)
        report.outlier_report = self._compute_outlier_report(df)

        scores = {
            "completeness": report.completeness,
            "consistency": report.consistency,
            "integrity": report.integrity,
            "validity": report.validity,
            "uniqueness": report.uniqueness,
            "timeliness": report.timeliness,
            "coverage": report.coverage,
        }
        total_weight = sum(self._weights.get(k, 0.1) for k in scores)
        weighted = sum(s * self._weights.get(k, 0.1) for k, s in scores.items())
        report.overall_score = round(weighted / total_weight, 4) if total_weight > 0 else 0.0

        logger.info("quality report for %s v%d: overall=%.4f", dataset_name, version, report.overall_score)
        return report

    def _score_completeness(self, df: pd.DataFrame, report: QualityReport) -> float:
        if df.empty:
            return 0.0
        total_cells = df.size
        missing = int(df.isnull().sum().sum())
        per_column = {}
        for col in df.columns:
            col_missing = int(df[col].isnull().sum())
            per_column[col] = {
                "missing": col_missing,
                "total": len(df),
                "rate": round(col_missing / len(df), 6),
            }
        report.dimension_details["completeness"] = {
            "total_missing": missing,
            "total_cells": total_cells,
            "missing_rate": round(missing / total_cells, 6) if total_cells else 0.0,
            "per_column": per_column,
        }
        return round(1.0 - missing / total_cells, 6) if total_cells else 0.0

    def _score_consistency(self, df: pd.DataFrame, report: QualityReport) -> float:
        if df.empty:
            return 1.0
        issues = []
        for col in df.select_dtypes(include=["object"]).columns:
            col_data = df[col].dropna()
            if len(col_data) < 2:
                continue
            inferred = col_data.apply(type).value_counts(normalize=True)
            if len(inferred) > 1 and inferred.iloc[0] < 0.95:
                issues.append(col)
        report.dimension_details["consistency"] = {
            "inconsistent_columns": issues,
            "total_object_columns": len(df.select_dtypes(include=["object"]).columns),
        }
        n_obj = len(df.select_dtypes(include=["object"]).columns)
        return round(1.0 - len(issues) / max(n_obj, 1), 6) if n_obj else 1.0

    def _score_integrity(self, df: pd.DataFrame, report: QualityReport) -> float:
        ref_cols = [c for c in df.columns if c.endswith("_id") or c.endswith("_uuid")]
        violations = 0
        for col in ref_cols:
            if col != "id" and col in df.columns:
                violations += int(df[col].isnull().sum())
        report.dimension_details["integrity"] = {
            "reference_columns": len(ref_cols),
            "null_references": violations,
        }
        return round(1.0 - violations / max(df.size, 1), 6)

    def _score_validity(self, df: pd.DataFrame, report: QualityReport) -> float:
        if df.empty:
            return 1.0
        valid_total = 0
        checked_total = 0
        per_col = {}
        for col in df[[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)]].columns:
            col_data = df[col].dropna()
            if len(col_data) < 4:
                continue
            q1, q3 = col_data.quantile(0.25), col_data.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - 3.0 * iqr
            upper = q3 + 3.0 * iqr
            valid = ((col_data >= lower) & (col_data <= upper)).sum()
            valid_total += valid
            checked_total += len(col_data)
            pct = round(float(valid / len(col_data)), 6) if len(col_data) > 0 else 1.0
            if pct < 0.95:
                per_col[col] = {"valid": int(valid), "total": len(col_data), "valid_rate": pct}
        report.dimension_details["validity"] = {
            "valid_count": valid_total,
            "checked_count": checked_total,
            "columns_with_outliers": per_col,
        }
        return round(valid_total / max(checked_total, 1), 6)

    def _score_uniqueness(self, df: pd.DataFrame, report: QualityReport) -> float:
        if df.empty:
            return 1.0
        dups = int(df.duplicated().sum())
        rate = dups / len(df) if len(df) > 0 else 0
        report.dimension_details["uniqueness"] = {
            "duplicate_rows": dups,
            "duplicate_rate": round(rate, 6),
            "total_rows": len(df),
        }
        return round(1.0 - rate, 6)

    def _score_timeliness(self, df: pd.DataFrame, report: QualityReport) -> float:
        time_cols = [c for c in df.columns if df[c].dtype in ("datetime64[ns]", "datetime64[ns, UTC]")]
        if not time_cols:
            report.dimension_details["timeliness"] = {"note": "no datetime columns"}
            return 1.0
        col = time_cols[0]
        col_data = df[col].dropna()
        if len(col_data) == 0:
            return 0.5
        date_min = col_data.min()
        date_max = col_data.max()
        range_days = (date_max - date_min).days
        now = pd.Timestamp.now()
        staleness_days = (now - date_max).days if hasattr(now - date_max, "days") else 0
        staleness = max(0.0, 1.0 - staleness_days / 365.0)
        coverage = min(1.0, range_days / max(365, 1))
        report.dimension_details["timeliness"] = {
            "date_column": col,
            "date_min": str(date_min),
            "date_max": str(date_max),
            "range_days": range_days,
            "staleness_days": staleness_days,
            "staleness_score": round(staleness, 4),
            "coverage_score": round(coverage, 4),
        }
        return round(staleness * 0.6 + coverage * 0.4, 4)

    def _score_coverage(self, df: pd.DataFrame, report: QualityReport) -> float:
        n_cols = len(df.columns)
        n_rows = len(df)
        score = min(1.0, n_rows / 10000) * 0.5 + min(1.0, n_cols / 20) * 0.5
        report.dimension_details["coverage"] = {
            "row_count": n_rows,
            "column_count": n_cols,
            "row_score": round(min(1.0, n_rows / 10000), 4),
            "column_score": round(min(1.0, n_cols / 20), 4),
        }
        return round(score, 4)

    def _compute_confidence_distribution(self, df: pd.DataFrame) -> dict[str, Any]:
        conf_cols = [c for c in df.columns if "confid" in c.lower()]
        if not conf_cols:
            return {}
        col = conf_cols[0]
        col_data = df[col].dropna()
        if len(col_data) == 0:
            return {}
        return {
            "column": col,
            "mean": round(float(col_data.mean()), 4),
            "std": round(float(col_data.std()), 4),
            "min": round(float(col_data.min()), 4),
            "max": round(float(col_data.max()), 4),
            "buckets": {
                "0.0-0.2": int((col_data < 0.2).sum()),
                "0.2-0.4": int(((col_data >= 0.2) & (col_data < 0.4)).sum()),
                "0.4-0.6": int(((col_data >= 0.4) & (col_data < 0.6)).sum()),
                "0.6-0.8": int(((col_data >= 0.6) & (col_data < 0.8)).sum()),
                "0.8-1.0": int((col_data >= 0.8).sum()),
            },
        }

    def _compute_country_distribution(self, df: pd.DataFrame) -> dict[str, int]:
        country_cols = [c for c in df.columns if any(k in c.lower() for k in
                       ("country", "iso_"))]
        for col in country_cols:
            if col in df.columns:
                counts = df[col].dropna().value_counts().head(20).to_dict()
                return {str(k): int(v) for k, v in counts.items()}
        return {}

    def _compute_temporal_coverage(self, df: pd.DataFrame) -> dict[str, Any]:
        time_cols = [c for c in df.columns if df[c].dtype in ("datetime64[ns]", "datetime64[ns, UTC]")]
        if not time_cols:
            return {"note": "no temporal columns"}
        col = time_cols[0]
        col_data = df[col].dropna()
        if len(col_data) == 0:
            return {"note": "no temporal data"}
        return {
            "column": col,
            "min_date": str(col_data.min()),
            "max_date": str(col_data.max()),
            "range_days": (col_data.max() - col_data.min()).days,
            "total_records": len(col_data),
            "year_distribution": col_data.dt.year.value_counts().sort_index().head(20).to_dict(),
        }

    def _compute_source_coverage(self, df: pd.DataFrame) -> dict[str, int]:
        source_cols = [c for c in df.columns if c.lower() in ("source", "source_name",
                       "source_type", "data_source")]
        for col in source_cols:
            if col in df.columns:
                counts = df[col].dropna().value_counts().head(20).to_dict()
                return {str(k): int(v) for k, v in counts.items()}
        return {}

    def _compute_relationship_coverage(self, df: pd.DataFrame) -> dict[str, Any]:
        rel_cols = [c for c in df.columns if "relation" in c.lower() or "relationship" in c.lower()]
        if not rel_cols:
            return {"note": "no relationship columns"}
        result = {}
        for col in rel_cols:
            non_null = int(df[col].notna().sum())
            result[col] = {
                "non_null": non_null,
                "total": len(df),
                "coverage": round(non_null / len(df), 4) if len(df) > 0 else 0.0,
            }
        return result

    def _compute_missing_report(self, df: pd.DataFrame) -> dict[str, Any]:
        missing_cols = {}
        for col in df.columns:
            n_missing = int(df[col].isnull().sum())
            if n_missing > 0:
                missing_cols[col] = {
                    "count": n_missing,
                    "rate": round(n_missing / len(df), 6) if len(df) > 0 else 0.0,
                }
        return {
            "total_missing_cells": int(df.isnull().sum().sum()),
            "missing_rate": round(df.isnull().sum().sum() / df.size, 6) if df.size > 0 else 0.0,
            "columns_with_missing": len(missing_cols),
            "missing_by_column": missing_cols,
        }

    def _compute_duplicate_report(self, df: pd.DataFrame) -> dict[str, Any]:
        dups = int(df.duplicated().sum())
        return {
            "duplicate_rows": dups,
            "duplicate_rate": round(dups / len(df), 6) if len(df) > 0 else 0.0,
        }

    def _compute_outlier_report(self, df: pd.DataFrame) -> dict[str, Any]:
        outlier_cols = {}
        for col in df[[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)]].columns:
            col_data = df[col].dropna()
            if len(col_data) < 4:
                continue
            q1, q3 = col_data.quantile(0.25), col_data.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = int(((col_data < lower) | (col_data > upper)).sum())
            if outliers > 0:
                outlier_cols[col] = {
                    "count": outliers,
                    "rate": round(outliers / len(col_data), 6),
                }
        return {"columns_with_outliers": len(outlier_cols), "details": outlier_cols}
