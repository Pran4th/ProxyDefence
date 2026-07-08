from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from quality.scorer import QualityDimension, QualityScorer

logger = get_logger(__name__)


class QualityReporter:
    def __init__(self):
        self._default_scorer = QualityScorer()

    async def generate_report(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        version: int,
        scorer: QualityScorer | None = None,
        **kwargs,
    ) -> dict:
        s = scorer or self._default_scorer
        results = await s.score_all(df, **kwargs)

        dimension_scores = results["dimension_scores"]
        dimension_details = results["dimension_details"]
        overall = results["overall_score"]

        per_column_quality = self._compute_per_column_quality(df, dimension_details)
        issues = self._identify_issues(dimension_scores, dimension_details, per_column_quality)

        report = {
            "metadata": {
                "dataset_name": dataset_name,
                "dataset_version": version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "row_count": len(df),
                "column_count": len(df.columns),
            },
            "dimension_scores": {
                dim: {
                    "score": dimension_scores[dim],
                    "details": dimension_details.get(dim, {}),
                }
                for dim in dimension_scores
            },
            "overall_score": overall,
            "per_column_quality": per_column_quality,
            "issues": issues,
            "summary": self._build_summary(dimension_scores, overall, issues),
        }

        report["total_checks"] = sum(
            len(v.get("per_column_validity", {})) + len(v.get("per_column", {}))
            for v in dimension_details.values() if isinstance(v, dict)
        )
        report["passed_checks"] = len([i for i in issues if i["severity"] != "critical"])
        report["failed_checks"] = len([i for i in issues if i["severity"] == "critical"])
        report["warning_checks"] = len([i for i in issues if i["severity"] == "warning"])

        logger.info("quality report generated for %s v%d: overall=%.4f", dataset_name, version, overall)
        return report

    async def report_to_dataframe(self, report: dict) -> pd.DataFrame:
        rows = []
        meta = report.get("metadata", {})
        dim_scores = report.get("dimension_scores", {})

        for dim, info in dim_scores.items():
            rows.append({
                "dataset_name": meta.get("dataset_name"),
                "dataset_version": meta.get("dataset_version"),
                "report_timestamp": meta.get("timestamp"),
                "dimension": dim,
                "score": info.get("score"),
                "row_count": meta.get("row_count"),
                "column_count": meta.get("column_count"),
            })

        overall_row = {
            "dataset_name": meta.get("dataset_name"),
            "dataset_version": meta.get("dataset_version"),
            "report_timestamp": meta.get("timestamp"),
            "dimension": "overall",
            "score": report.get("overall_score"),
            "row_count": meta.get("row_count"),
            "column_count": meta.get("column_count"),
        }
        rows.append(overall_row)

        return pd.DataFrame(rows)

    async def compare_reports(self, report_a: dict, report_b: dict) -> dict:
        scores_a = {
            dim: info["score"]
            for dim, info in report_a.get("dimension_scores", {}).items()
        }
        scores_a["overall"] = report_a.get("overall_score")

        scores_b = {
            dim: info["score"]
            for dim, info in report_b.get("dimension_scores", {}).items()
        }
        scores_b["overall"] = report_b.get("overall_score")

        deltas = {}
        all_dims = set(scores_a.keys()) | set(scores_b.keys())
        for dim in sorted(all_dims):
            sa = scores_a.get(dim, 0.0)
            sb = scores_b.get(dim, 0.0)
            deltas[dim] = {
                "before": sa,
                "after": sb,
                "delta": round(sb - sa, 6),
                "direction": "improved" if sb > sa else ("degraded" if sb < sa else "unchanged"),
            }

        meta_a = report_a.get("metadata", {})
        meta_b = report_b.get("metadata", {})

        return {
            "report_a": {
                "dataset_name": meta_a.get("dataset_name"),
                "dataset_version": meta_a.get("dataset_version"),
                "timestamp": meta_a.get("timestamp"),
            },
            "report_b": {
                "dataset_name": meta_b.get("dataset_name"),
                "dataset_version": meta_b.get("dataset_version"),
                "timestamp": meta_b.get("timestamp"),
            },
            "deltas": deltas,
            "issues_delta": {
                "a_total_issues": len(report_a.get("issues", [])),
                "b_total_issues": len(report_b.get("issues", [])),
                "new_issues": [
                    i for i in report_b.get("issues", [])
                    if i not in report_a.get("issues", [])
                ],
                "resolved_issues": [
                    i for i in report_a.get("issues", [])
                    if i not in report_b.get("issues", [])
                ],
            },
        }

    async def generate_summary(self, reports: list[dict]) -> dict:
        if not reports:
            return {
                "report_count": 0,
                "datasets_covered": [],
                "average_scores": {},
                "overall_summary": "no reports",
            }

        dimension_keys = [QualityDimension.COMPLETENESS, QualityDimension.CONSISTENCY,
                          QualityDimension.UNIQUENESS, QualityDimension.TIMELINESS,
                          QualityDimension.VALIDITY, QualityDimension.INTEGRITY]
        scores_by_dim: dict[str, list[float]] = {d: [] for d in dimension_keys}
        overall_scores: list[float] = []
        datasets_covered: set[str] = set()
        all_issues: list[dict] = []
        versions: list[int] = []

        for report in reports:
            meta = report.get("metadata", {})
            datasets_covered.add(meta.get("dataset_name", "unknown"))
            overall_scores.append(report.get("overall_score", 0.0))
            all_issues.extend(report.get("issues", []))
            if meta.get("dataset_version"):
                versions.append(meta["dataset_version"])

            for dim in dimension_keys:
                dim_info = report.get("dimension_scores", {}).get(dim, {})
                scores_by_dim[dim].append(dim_info.get("score", 0.0))

        averages = {}
        for dim, scores in scores_by_dim.items():
            if scores:
                arr = np.array(scores)
                averages[dim] = {
                    "mean": round(float(arr.mean()), 6),
                    "min": round(float(arr.min()), 6),
                    "max": round(float(arr.max()), 6),
                    "std": round(float(arr.std()), 6) if len(scores) > 1 else 0.0,
                }
            else:
                averages[dim] = {"mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}

        overall_arr = np.array(overall_scores) if overall_scores else np.array([0.0])
        critical_count = sum(1 for i in all_issues if i.get("severity") == "critical")
        warning_count = sum(1 for i in all_issues if i.get("severity") == "warning")
        info_count = sum(1 for i in all_issues if i.get("severity") == "info")

        return {
            "report_count": len(reports),
            "datasets_covered": sorted(datasets_covered),
            "version_range": {
                "min": min(versions) if versions else None,
                "max": max(versions) if versions else None,
            },
            "average_scores": averages,
            "overall_average": round(float(overall_arr.mean()), 6),
            "overall_min": round(float(overall_arr.min()), 6),
            "overall_max": round(float(overall_arr.max()), 6),
            "overall_std": round(float(overall_arr.std()), 6) if len(overall_scores) > 1 else 0.0,
            "total_issues": len(all_issues),
            "issues_breakdown": {
                "critical": critical_count,
                "warning": warning_count,
                "info": info_count,
            },
        }

    # ── Internal helpers ──────────────────────────────────────────

    def _compute_per_column_quality(self, df: pd.DataFrame, dimension_details: dict) -> dict[str, Any]:
        completeness_details = dimension_details.get(QualityDimension.COMPLETENESS, {})
        validity_details = dimension_details.get(QualityDimension.VALIDITY, {})

        per_column = {}
        for col in df.columns:
            comp = completeness_details.get("per_column", {}).get(col, {})
            valid = validity_details.get("per_column_validity", {}).get(col, {})

            comp_score = comp.get("completeness", 1.0)
            valid_score = valid.get("valid_rate", 1.0)
            avg_quality = round((comp_score + valid_score) / 2.0, 6)

            per_column[col] = {
                "dtype": str(df[col].dtype),
                "completeness": comp_score,
                "validity": valid_score,
                "average_quality": avg_quality,
                "missing": comp.get("missing", 0),
                "total": comp.get("total", len(df)),
            }
        return per_column

    def _identify_issues(
        self,
        dimension_scores: dict[str, float],
        dimension_details: dict[str, Any],
        per_column_quality: dict[str, Any],
    ) -> list[dict]:
        issues = []

        for dim, score in dimension_scores.items():
            if score < 0.5:
                severity = "critical"
            elif score < 0.8:
                severity = "warning"
            else:
                severity = "info"

            if score < 0.95:
                issues.append({
                    "severity": severity,
                    "dimension": dim,
                    "column": None,
                    "description": f"{dim} score is {score:.4f}",
                    "suggestion": self._suggestion_for_dimension(dim),
                })

        for col, info in per_column_quality.items():
            if info.get("completeness", 1.0) < 0.5:
                issues.append({
                    "severity": "critical",
                    "dimension": QualityDimension.COMPLETENESS,
                    "column": col,
                    "description": f"column '{col}' has {info.get('missing', 0)} missing values "
                                   f"(rate: {1.0 - info['completeness']:.2%})",
                    "suggestion": "impute missing values or investigate data source",
                })
            elif info.get("validity", 1.0) < 0.5:
                issues.append({
                    "severity": "critical",
                    "dimension": QualityDimension.VALIDITY,
                    "column": col,
                    "description": f"column '{col}' has high invalid rate ({1.0 - info['validity']:.2%})",
                    "suggestion": "check data type constraints and validation rules",
                })

        completeness_details = dimension_details.get(QualityDimension.COMPLETENESS, {})
        per_col_comp = completeness_details.get("per_column", {})
        high_missing = [c for c, info in per_col_comp.items()
                        if isinstance(info, dict) and info.get("completeness", 1.0) < 0.9]
        if high_missing:
            for col in high_missing[:5]:
                issues.append({
                    "severity": "warning",
                    "dimension": QualityDimension.COMPLETENESS,
                    "column": col,
                    "description": f"column '{col}' has >10% missing data",
                    "suggestion": "review collection pipeline for this field",
                })

        consistency_details = dimension_details.get(QualityDimension.CONSISTENCY, {})
        inconsistencies = consistency_details.get("inconsistencies", {})
        for col in inconsistencies:
            issues.append({
                "severity": "warning",
                "dimension": QualityDimension.CONSISTENCY,
                "column": col,
                "description": f"column '{col}' has type/format inconsistencies",
                "suggestion": "normalize column to a single type or format",
            })

        return issues

    @staticmethod
    def _build_summary(dimension_scores: dict[str, float], overall: float, issues: list) -> str:
        n_critical = sum(1 for i in issues if i["severity"] == "critical")
        n_warning = sum(1 for i in issues if i["severity"] == "warning")
        n_info = sum(1 for i in issues if i["severity"] == "info")

        best_dim = max(dimension_scores, key=dimension_scores.get) if dimension_scores else "none"
        worst_dim = min(dimension_scores, key=dimension_scores.get) if dimension_scores else "none"

        rating = "excellent" if overall >= 0.95 else "good" if overall >= 0.85 else "fair" if overall >= 0.7 else "poor"

        return (
            f"Overall data quality: {overall:.4f} ({rating}). "
            f"Best dimension: {best_dim} ({dimension_scores.get(best_dim, 0):.4f}), "
            f"worst dimension: {worst_dim} ({dimension_scores.get(worst_dim, 0):.4f}). "
            f"Issues: {n_critical} critical, {n_warning} warning, {n_info} info."
        )

    @staticmethod
    def _suggestion_for_dimension(dim: str) -> str:
        suggestions = {
            QualityDimension.COMPLETENESS: "investigate missing data sources or impute values",
            QualityDimension.CONSISTENCY: "standardize data types and formats across columns",
            QualityDimension.UNIQUENESS: "remove or merge duplicate records",
            QualityDimension.TIMELINESS: "check data freshness and update frequency",
            QualityDimension.VALIDITY: "review validation rules and data collection pipeline",
            QualityDimension.INTEGRITY: "fix referential constraint violations",
        }
        return suggestions.get(dim, "review data quality")
