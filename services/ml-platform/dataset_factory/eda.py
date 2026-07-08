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
class EDAReport:
    dataset_name: str
    version: int
    summary: dict[str, Any] = field(default_factory=dict)
    column_statistics: dict[str, Any] = field(default_factory=dict)
    target_distribution: dict[str, Any] = field(default_factory=dict)
    feature_distributions: dict[str, Any] = field(default_factory=dict)
    correlation_matrix: list[list[float]] = field(default_factory=list)
    correlation_features: list[str] = field(default_factory=list)
    country_distribution: dict[str, int] = field(default_factory=dict)
    organization_frequency: dict[str, int] = field(default_factory=dict)
    entity_frequency: dict[str, int] = field(default_factory=dict)
    theme_frequency: dict[str, int] = field(default_factory=dict)
    temporal_analysis: dict[str, Any] = field(default_factory=dict)
    seasonality: dict[str, Any] = field(default_factory=dict)
    trend_analysis: dict[str, Any] = field(default_factory=dict)
    geospatial_distribution: dict[str, Any] = field(default_factory=dict)
    class_imbalance: dict[str, Any] = field(default_factory=dict)
    feature_importance_baseline: dict[str, float] = field(default_factory=dict)
    mutual_information: dict[str, float] = field(default_factory=dict)
    categorical_cardinality: dict[str, int] = field(default_factory=dict)
    null_heatmap: dict[str, Any] = field(default_factory=dict)
    data_drift_baseline: dict[str, Any] = field(default_factory=dict)
    html_output_path: str = ""
    notebook_output_path: str = ""
    timestamp: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "summary": self.summary,
            "column_statistics": self.column_statistics,
            "target_distribution": self.target_distribution,
            "feature_distributions": self.feature_distributions,
            "correlation_features": self.correlation_features,
            "correlation_matrix_shape": [len(self.correlation_matrix), len(self.correlation_matrix[0])] if self.correlation_matrix else [0, 0],
            "country_distribution": self.country_distribution,
            "organization_frequency": self.organization_frequency,
            "entity_frequency": self.entity_frequency,
            "theme_frequency": self.theme_frequency,
            "temporal_analysis": self.temporal_analysis,
            "seasonality": self.seasonality,
            "trend_analysis": self.trend_analysis,
            "geospatial_distribution": self.geospatial_distribution,
            "class_imbalance": self.class_imbalance,
            "categorical_cardinality": self.categorical_cardinality,
            "null_heatmap": self.null_heatmap,
            "data_drift_baseline": self.data_drift_baseline,
            "feature_importance_baseline": self.feature_importance_baseline,
            "mutual_information": self.mutual_information,
            "html_output_path": self.html_output_path,
            "notebook_output_path": self.notebook_output_path,
            "timestamp": self.timestamp,
            "warnings": self.warnings,
        }


class EDAReportGenerator:
    def generate(self, df: pd.DataFrame, dataset_name: str, version: int,
                 target_column: str | None = None) -> EDAReport:
        report = EDAReport(
            dataset_name=dataset_name,
            version=version,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        report.summary = self._compute_summary(df)
        report.column_statistics = self._compute_column_statistics(df)
        report.target_distribution = self._compute_target_distribution(df, target_column)
        report.feature_distributions = self._compute_feature_distributions(df, target_column)
        report.correlation_matrix, report.correlation_features = self._compute_correlation(df, target_column)
        report.country_distribution = self._compute_country_distribution(df)
        report.organization_frequency = self._compute_org_frequency(df)
        report.entity_frequency = self._compute_entity_frequency(df)
        report.theme_frequency = self._compute_theme_frequency(df)
        report.temporal_analysis = self._compute_temporal_analysis(df)
        report.seasonality = self._compute_seasonality(df)
        report.trend_analysis = self._compute_trend_analysis(df)
        report.geospatial_distribution = self._compute_geospatial(df)
        report.class_imbalance = self._compute_class_imbalance(df, target_column)
        report.feature_importance_baseline = self._compute_feature_importance_baseline(df, target_column)
        report.mutual_information = self._compute_mutual_information(df, target_column)
        report.categorical_cardinality = self._compute_categorical_cardinality(df)
        report.null_heatmap = self._compute_null_heatmap(df)
        report.data_drift_baseline = self._compute_drift_baseline(df)

        logger.info("EDA report generated for %s v%d (%d features, %d rows)",
                     dataset_name, version, len(df.columns), len(df))
        return report

    def _compute_summary(self, df: pd.DataFrame) -> dict[str, Any]:
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "numerical_features": int(len([c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)])),
            "categorical_features": int(len([c for c in df.columns if pd.api.types.is_categorical_dtype(df[c].dtype) or df[c].dtype.name == "object"])),
            "datetime_features": int(len([c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c].dtype)])),
            "boolean_features": int(len([c for c in df.columns if pd.api.types.is_bool_dtype(df[c].dtype)])),
            "missing_cells": int(df.isnull().sum().sum()),
            "missing_rate": round(float(df.isnull().sum().sum() / df.size), 6) if df.size > 0 else 0.0,
            "duplicate_rows": int(df.duplicated().sum()),
            "memory_usage_mb": round(float(df.memory_usage(deep=True).sum() / 1024 / 1024), 4),
        }

    def _compute_column_statistics(self, df: pd.DataFrame) -> dict[str, Any]:
        stats = {}
        for col in df.columns:
            col_data = df[col].dropna()
            entry: dict[str, Any] = {
                "dtype": str(df[col].dtype),
                "missing": int(df[col].isnull().sum()),
                "missing_rate": round(float(df[col].isnull().mean()), 6),
                "unique": int(col_data.nunique()) if len(col_data) > 0 else 0,
            }
            if pd.api.types.is_numeric_dtype(df[col].dtype) and not pd.api.types.is_bool_dtype(df[col].dtype) and len(col_data) > 0:
                try:
                    entry.update({
                        "mean": round(float(col_data.mean()), 6),
                        "std": round(float(col_data.std()), 6),
                        "min": round(float(col_data.min()), 6),
                        "max": round(float(col_data.max()), 6),
                        "p25": round(float(col_data.quantile(0.25)), 6),
                        "p50": round(float(col_data.median()), 6),
                        "p75": round(float(col_data.quantile(0.75))),
                        "skew": round(float(col_data.skew()), 6),
                        "kurtosis": round(float(col_data.kurtosis()), 6),
                    })
                except Exception:
                    entry.update({
                        "mean": round(float(col_data.mean()), 6),
                        "std": round(float(col_data.std()), 6),
                        "min": round(float(col_data.min()), 6),
                        "max": round(float(col_data.max()), 6),
                    })
            elif df[col].dtype == "object" or df[col].dtype.name == "category":
                if len(col_data) > 0:
                    vc = col_data.value_counts()
                    entry.update({
                        "top_value": str(vc.index[0]),
                        "top_frequency": round(float(vc.iloc[0] / len(col_data)), 6),
                        "cardinality_ratio": round(float(col_data.nunique() / len(col_data)), 6),
                    })
            stats[col] = entry
        return stats

    def _compute_target_distribution(self, df: pd.DataFrame, target: str | None) -> dict[str, Any]:
        if not target or target not in df.columns:
            return {"note": "no target column specified"}
        col = df[target].dropna()
        if len(col) == 0:
            return {"note": "empty target column"}
        if col.dtype == "object" or col.nunique() < 20:
            counts = col.value_counts()
            probs = col.value_counts(normalize=True)
            return {
                "type": "categorical",
                "classes": int(col.nunique()),
                "counts": {str(k): int(v) for k, v in counts.items()},
                "proportions": {str(k): round(float(v), 4) for k, v in probs.items()},
                "entropy": round(float(-(probs * np.log2(probs + 1e-10)).sum()), 4),
                "imbalance_ratio": round(float(probs.max() / probs.min()), 4) if probs.min() > 0 else float("inf"),
            }
        return {
            "type": "continuous",
            "mean": round(float(col.mean()), 4),
            "std": round(float(col.std()), 4),
            "min": round(float(col.min()), 4),
            "max": round(float(col.max()), 4),
        }

    def _compute_feature_distributions(self, df: pd.DataFrame, target: str | None) -> dict[str, Any]:
        dists = {}
        num_cols_eda = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)]
        for col in num_cols_eda[:50]:
            col_data = df[col].dropna()
            if len(col_data) < 4:
                continue
            hist, edges = np.histogram(col_data, bins=10)
            dists[col] = {
                "histogram": hist.tolist(),
                "edges": [round(float(e), 4) for e in edges],
                "mean": round(float(col_data.mean()), 4),
                "std": round(float(col_data.std()), 4),
            }
        return dists

    def _compute_correlation(self, df: pd.DataFrame, target: str | None) -> tuple[list[list[float]], list[str]]:
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)]
        if len(num_cols) < 2:
            return [], []
        corr_df = df[num_cols].corr()
        return corr_df.values.tolist(), num_cols

    def _compute_country_distribution(self, df: pd.DataFrame) -> dict[str, int]:
        country_cols = [c for c in df.columns if any(k in c.lower() for k in
                       ("country", "iso_country", "nation", "location_code"))]
        for col in country_cols:
            if col in df.columns:
                counts = df[col].dropna().astype(str).value_counts().head(30).to_dict()
                return {str(k): int(v) for k, v in counts.items()}
        return {}

    def _compute_org_frequency(self, df: pd.DataFrame) -> dict[str, int]:
        org_cols = [c for c in df.columns if any(k in c.lower() for k in
                    ("organization", "org_", "organization_type"))]
        for col in org_cols:
            if col in df.columns:
                counts = df[col].dropna().astype(str).value_counts().head(30).to_dict()
                return {str(k): int(v) for k, v in counts.items()}
        return {}

    def _compute_entity_frequency(self, df: pd.DataFrame) -> dict[str, int]:
        entity_cols = [c for c in df.columns if any(k in c.lower() for k in
                       ("entity_type", "entity", "type"))]
        for col in entity_cols:
            if col in df.columns:
                counts = df[col].dropna().astype(str).value_counts().head(30).to_dict()
                return {str(k): int(v) for k, v in counts.items()}
        return {}

    def _compute_theme_frequency(self, df: pd.DataFrame) -> dict[str, int]:
        theme_cols = [c for c in df.columns if any(k in c.lower() for k in
                      ("theme", "tag", "category", "topic", "label"))]
        for col in theme_cols:
            if col in df.columns and df[col].dtype == "object":
                all_tags = df[col].dropna().astype(str).str.split(",")
                flat = [t.strip() for tags in all_tags for t in tags if t.strip()]
                if flat:
                    from collections import Counter
                    return dict(Counter(flat).most_common(30))
        return {}

    def _compute_temporal_analysis(self, df: pd.DataFrame) -> dict[str, Any]:
        time_cols = [c for c in df.columns if df[c].dtype in ("datetime64[ns]", "datetime64[ns, UTC]")]
        if not time_cols:
            return {"note": "no temporal columns"}
        col = time_cols[0]
        col_data = df[col].dropna()
        if len(col_data) < 2:
            return {"note": "insufficient temporal data"}
        return {
            "column": col,
            "min_date": str(col_data.min()),
            "max_date": str(col_data.max()),
            "range_days": (col_data.max() - col_data.min()).days,
            "records_per_year": col_data.dt.year.value_counts().sort_index().to_dict(),
            "records_per_month": col_data.dt.month.value_counts().sort_index().to_dict(),
            "records_per_dow": col_data.dt.dayofweek.value_counts().sort_index().to_dict(),
            "hourly_distribution": col_data.dt.hour.value_counts().sort_index().to_dict() if col_data.dt.hour.nunique() > 1 else {},
        }

    def _compute_seasonality(self, df: pd.DataFrame) -> dict[str, Any]:
        time_cols = [c for c in df.columns if df[c].dtype in ("datetime64[ns]", "datetime64[ns, UTC]")]
        if not time_cols:
            return {"note": "no temporal columns"}
        col = time_cols[0]
        col_data = df[col].dropna()
        if len(col_data) < 30:
            return {"note": "insufficient data for seasonality analysis"}
        return {
            "quarterly": col_data.dt.quarter.value_counts().sort_index().to_dict(),
            "monthly": col_data.dt.month.value_counts().sort_index().to_dict(),
            "weekly": col_data.dt.isocalendar().week.astype(int).value_counts().sort_index().head(20).to_dict(),
        }

    def _compute_trend_analysis(self, df: pd.DataFrame) -> dict[str, Any]:
        time_cols = [c for c in df.columns if df[c].dtype in ("datetime64[ns]", "datetime64[ns, UTC]")]
        if not time_cols:
            return {"note": "no temporal columns"}
        col = time_cols[0]
        col_data = df[col].dropna()
        if len(col_data) < 2:
            return {"note": "insufficient data"}
        counts_by_date = col_data.value_counts().sort_index()
        return {
            "column": col,
            "total_dates": len(counts_by_date),
            "max_daily_count": int(counts_by_date.max()),
            "min_daily_count": int(counts_by_date.min()),
            "mean_daily_count": round(float(counts_by_date.mean()), 2),
        }

    def _compute_geospatial(self, df: pd.DataFrame) -> dict[str, Any]:
        lat_cols = [c for c in df.columns if "latitude" in c.lower()]
        lng_cols = [c for c in df.columns if "longitude" in c.lower()]
        if not lat_cols or not lng_cols:
            return {"note": "no coordinate columns"}
        lat, lng = lat_cols[0], lng_cols[0]
        valid = df[[lat, lng]].dropna()
        if len(valid) == 0:
            return {"note": "no valid coordinates"}
        return {
            "latitude_column": lat,
            "longitude_column": lng,
            "points": len(valid),
            "lat_range": [round(float(valid[lat].min()), 4), round(float(valid[lat].max()), 4)],
            "lng_range": [round(float(valid[lng].min()), 4), round(float(valid[lng].max()), 4)],
        }

    def _compute_class_imbalance(self, df: pd.DataFrame, target: str | None) -> dict[str, Any]:
        if not target or target not in df.columns:
            return {"note": "no target column"}
        col = df[target].dropna()
        if col.nunique() < 2 or col.nunique() > 50:
            return {"note": "not a classification target"}
        probs = col.value_counts(normalize=True)
        return {
            "classes": col.nunique(),
            "majority_class": str(probs.index[0]),
            "majority_proportion": round(float(probs.iloc[0]), 4),
            "minority_class": str(probs.index[-1]),
            "minority_proportion": round(float(probs.iloc[-1]), 4),
            "imbalance_ratio": round(float(probs.iloc[0] / probs.iloc[-1]), 4) if probs.iloc[-1] > 0 else float("inf"),
            "balanced": bool(probs.iloc[0] < 0.8),
        }

    def _compute_feature_importance_baseline(self, df: pd.DataFrame, target: str | None) -> dict[str, float]:
        if not target or target not in df.columns:
            return {}
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)]
        if target in num_cols:
            num_cols.remove(target)
        if len(num_cols) < 2:
            return {}
        corr = df[num_cols + [target]].corr()[target].drop(target).abs()
        return {str(k): round(float(v), 4) for k, v in corr.sort_values(ascending=False).head(20).items()}

    def _compute_mutual_information(self, df: pd.DataFrame, target: str | None) -> dict[str, float]:
        if not target or target not in df.columns:
            return {}
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)]
        if target in num_cols:
            num_cols.remove(target)
        if len(num_cols) < 2:
            return {}
        result = {}
        y = df[target].fillna(0)
        for col in num_cols[:30]:
            x = df[col].fillna(0)
            try:
                from sklearn.feature_selection import mutual_info_regression
                mi = mutual_info_regression(x.values.reshape(-1, 1), y.values, random_state=42)
                result[col] = round(float(mi[0]), 6)
            except Exception:
                pass
        return dict(sorted(result.items(), key=lambda x: -x[1])[:20])

    def _compute_categorical_cardinality(self, df: pd.DataFrame) -> dict[str, int]:
        card = {}
        cat_cols = [c for c in df.columns if pd.api.types.is_categorical_dtype(df[c].dtype) or df[c].dtype.name == "object"]
        for col in cat_cols:
            n_unique = int(df[col].nunique())
            if n_unique > 1 and n_unique < 1000:
                card[col] = n_unique
        return card

    def _compute_null_heatmap(self, df: pd.DataFrame) -> dict[str, Any]:
        null_cols = {c: int(df[c].isnull().sum()) for c in df.columns if df[c].isnull().any()}
        return {
            "columns_with_nulls": len(null_cols),
            "null_counts": null_cols,
            "null_patterns": {
                col: round(df[col].isnull().mean(), 4)
                for col in null_cols
            },
        }

    def _compute_drift_baseline(self, df: pd.DataFrame) -> dict[str, Any]:
        baseline = {}
        num_cols_drift = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype) and not pd.api.types.is_bool_dtype(df[c].dtype)]
        for col in num_cols_drift:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                baseline[col] = {
                    "mean": round(float(col_data.mean()), 6),
                    "std": round(float(col_data.std()), 6),
                    "min": round(float(col_data.min()), 6),
                    "max": round(float(col_data.max()), 6),
                    "p25": round(float(col_data.quantile(0.25)), 6),
                    "p50": round(float(col_data.median()), 6),
                    "p75": round(float(col_data.quantile(0.75)), 6),
                    "n": len(col_data),
                }
        return {
            "feature_count": len(baseline),
            "baseline": baseline,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def generate_html(self, report: EDAReport) -> str:
        html_parts = [
            "<!DOCTYPE html><html><head>",
            "<meta charset='utf-8'><title>EDA Report: " + report.dataset_name + "</title>",
            "<style>",
            "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;",
            "margin:40px;background:#f8f9fa;color:#333}",
            "h1{color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px}",
            "h2{color:#333;margin-top:30px}",
            ".card{background:#fff;border-radius:8px;padding:20px;margin:16px 0;",
            "box-shadow:0 1px 3px rgba(0,0,0,0.12)}",
            ".stat{display:inline-block;margin:8px 24px 8px 0}",
            ".stat-label{font-size:12px;color:#666}",
            ".stat-value{font-size:20px;font-weight:600}",
            "table{border-collapse:collapse;width:100%}",
            "th,td{text-align:left;padding:8px 12px;border-bottom:1px solid #dee2e6}",
            "th{background:#f1f3f4;font-weight:500}",
            "tr:hover{background:#f8f9fa}",
            ".warn{color:#d93025;font-size:14px}",
            "</style></head><body>",
            "<h1>EDA Report: " + report.dataset_name + " v" + str(report.version) + "</h1>",
            "<p>Generated: " + report.timestamp + "</p>",
            "<div class='card'>",
            "<h2>Dataset Summary</h2>",
        ]
        s = report.summary
        for k, v in s.items():
            html_parts.append(f"<div class='stat'><div class='stat-label'>{k}</div><div class='stat-value'>{v}</div></div>")

        html_parts.append("</div><div class='card'><h2>Target Distribution</h2>")
        td = report.target_distribution
        if td:
            html_parts.append("<table><tr><th>Metric</th><th>Value</th></tr>")
            for k, v in td.items():
                if k in ("counts", "proportions"):
                    continue
                html_parts.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
            html_parts.append("</table>")

        if report.categorical_cardinality:
            html_parts.append("</div><div class='card'><h2>Categorical Cardinality</h2><table>")
            html_parts.append("<tr><th>Column</th><th>Unique Values</th></tr>")
            for col, n in sorted(report.categorical_cardinality.items(), key=lambda x: -x[1])[:30]:
                html_parts.append(f"<tr><td>{col}</td><td>{n}</td></tr>")
            html_parts.append("</table>")

        if report.correlation_features:
            html_parts.append("</div><div class='card'><h2>Correlation Matrix</h2>")
            html_parts.append(f"<p>Features: {len(report.correlation_features)}</p>")
            html_parts.append(f"<p>Matrix shape: {len(report.correlation_matrix)}x{len(report.correlation_matrix[0])}</p>")

        if report.class_imbalance and "imbalance_ratio" in report.class_imbalance:
            html_parts.append("</div><div class='card'><h2>Class Imbalance</h2><table>")
            for k, v in report.class_imbalance.items():
                html_parts.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
            html_parts.append("</table>")

        if report.warnings:
            html_parts.append("</div><div class='card'><h2>Warnings</h2>")
            for w in report.warnings:
                html_parts.append(f"<p class='warn'>{w}</p>")
        html_parts.append("</div></body></html>")
        return "\n".join(html_parts)
