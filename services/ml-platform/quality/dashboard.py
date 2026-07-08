import json
from datetime import date, timedelta
from typing import Any

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)


class QualityDashboard:
    async def get_overall_quality(self, dataset_name: str | None = None) -> dict:
        pool = await get_pool()
        if dataset_name:
            row = await pool.fetchrow(
                "SELECT * FROM ml.quality_dashboard "
                "WHERE dataset_name = $1 "
                "ORDER BY snapshot_date DESC LIMIT 1",
                dataset_name,
            )
        else:
            row = await pool.fetchrow(
                "SELECT * FROM ml.quality_dashboard "
                "ORDER BY snapshot_date DESC LIMIT 1"
            )

        if not row:
            return {"found": False, "dataset_name": dataset_name}

        return self._row_to_metrics(dict(row))

    async def get_dimension_trend(self, dimension: str, dataset_name: str, days: int = 30) -> list[dict]:
        pool = await get_pool()
        cutoff = date.today() - timedelta(days=days)
        dimension_column = self._dimension_to_column(dimension)

        rows = await pool.fetch(
            f"SELECT snapshot_date, {dimension_column} AS score, "
            "overall_score, row_count "
            "FROM ml.quality_dashboard "
            "WHERE dataset_name = $1 AND snapshot_date >= $2 "
            "ORDER BY snapshot_date ASC",
            dataset_name, cutoff,
        )

        return [
            {
                "date": str(r["snapshot_date"]),
                "dimension": dimension,
                "score": r["score"],
                "overall_score": r["overall_score"],
                "row_count": r["row_count"],
            }
            for r in rows
        ]

    async def get_lowest_scoring_columns(self, dataset_name: str, version: int, n: int = 5) -> list[dict]:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT dimensions FROM ml.quality_reports "
            "WHERE dataset_name = $1 AND dataset_version = $2 "
            "ORDER BY executed_at DESC LIMIT 1",
            dataset_name, version,
        )

        if not row or not row["dimensions"]:
            return []

        dimensions = row["dimensions"]
        if isinstance(dimensions, str):
            dimensions = json.loads(dimensions)

        per_column_quality = {}
        completeness_per_col = dimensions.get("completeness", {}).get("details", {}).get("per_column", {})
        validity_per_col = dimensions.get("validity", {}).get("details", {}).get("per_column_validity", {})

        all_columns = set(completeness_per_col.keys()) | set(validity_per_col.keys())
        for col in all_columns:
            comp = completeness_per_col.get(col, {}).get("completeness", 1.0) if isinstance(completeness_per_col.get(col), dict) else 1.0
            valid = validity_per_col.get(col, {}).get("valid_rate", 1.0) if isinstance(validity_per_col.get(col), dict) else 1.0
            avg = round((comp + valid) / 2.0, 6)
            per_column_quality[col] = {"column": col, "completeness": comp, "validity": valid, "average": avg}

        sorted_cols = sorted(per_column_quality.values(), key=lambda x: x["average"])
        return sorted_cols[:n]

    async def get_quality_summary(self) -> dict:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT dataset_name, MAX(snapshot_date) AS latest_date, "
            "AVG(overall_score) AS avg_score, "
            "MIN(overall_score) AS min_score, "
            "MAX(overall_score) AS max_score, "
            "STDDEV(overall_score) AS std_score, "
            "COUNT(*) AS snapshot_count "
            "FROM ml.quality_dashboard "
            "GROUP BY dataset_name "
            "ORDER BY avg_score DESC"
        )

        latest = await pool.fetch(
            "SELECT DISTINCT ON (dataset_name) dataset_name, overall_score, "
            "completeness_score, consistency_score, uniqueness_score, "
            "timeliness_score, validity_score, snapshot_date "
            "FROM ml.quality_dashboard "
            "ORDER BY dataset_name, snapshot_date DESC"
        )

        distribution = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        for r in latest:
            score = r["overall_score"] or 0
            if score >= 0.95:
                distribution["excellent"] += 1
            elif score >= 0.85:
                distribution["good"] += 1
            elif score >= 0.7:
                distribution["fair"] += 1
            else:
                distribution["poor"] += 1

        datasets = []
        for r in rows:
            datasets.append({
                "dataset_name": r["dataset_name"],
                "latest_snapshot": str(r["latest_date"]) if r["latest_date"] else None,
                "avg_score": round(float(r["avg_score"]), 6) if r["avg_score"] else None,
                "min_score": round(float(r["min_score"]), 6) if r["min_score"] else None,
                "max_score": round(float(r["max_score"]), 6) if r["max_score"] else None,
                "std_score": round(float(r["std_score"]), 6) if r["std_score"] else None,
                "snapshot_count": r["snapshot_count"],
            })

        all_scores = [r["avg_score"] for r in rows if r["avg_score"] is not None]
        return {
            "dataset_count": len(rows),
            "overall_average_score": round(float(sum(all_scores) / len(all_scores)), 6) if all_scores else 0.0,
            "score_distribution": distribution,
            "datasets": datasets,
        }

    async def get_issues(self, dataset_name: str | None = None, severity: str | None = None) -> list[dict]:
        pool = await get_pool()
        params: list[Any] = []
        clauses = []

        if dataset_name:
            clauses.append(f"dataset_name = ${len(params) + 1}")
            params.append(dataset_name)

        if severity:
            clauses.append(f"checks_json->>'severity' = ${len(params) + 1}")
            params.append(severity)

        where = " AND ".join(clauses) if clauses else "TRUE"

        rows = await pool.fetch(
            f"SELECT dataset_name, dataset_version, executed_at, "
            "overall_score, dimensions, checks_json "
            "FROM ml.quality_reports "
            "WHERE {where} "
            "ORDER BY executed_at DESC "
            "LIMIT 100".replace("{where}", where),
            *params,
        )

        issues: list[dict] = []
        for r in rows:
            report_issues = self._extract_issues_from_report(dict(r))
            for issue in report_issues:
                issue["dataset_name"] = r["dataset_name"]
                issue["dataset_version"] = r["dataset_version"]
                issue["report_timestamp"] = str(r["executed_at"]) if r["executed_at"] else None
            issues.extend(report_issues)

        return issues[:100]

    async def snapshot_metrics(self, pool, metrics: dict) -> None:
        dashboard_name = metrics.get("dashboard_name", "default")
        dataset_name = metrics.get("dataset_name", "unknown")
        snapshot_date = metrics.get("snapshot_date", date.today())

        if isinstance(snapshot_date, str):
            snapshot_date = date.fromisoformat(snapshot_date)

        await pool.execute(
            "INSERT INTO ml.quality_dashboard "
            "(dashboard_name, dataset_name, snapshot_date, "
            "overall_score, completeness_score, accuracy_score, "
            "consistency_score, timeliness_score, uniqueness_score, "
            "validity_score, row_count, column_count, "
            "trend_direction, score_delta, alerts_count, "
            "critical_alerts, snapshot_data) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, "
            "$11, $12, $13, $14, $15, $16, $17::jsonb) "
            "ON CONFLICT (dashboard_name, dataset_name, snapshot_date) "
            "DO UPDATE SET "
            "overall_score = $4, completeness_score = $5, accuracy_score = $6, "
            "consistency_score = $7, timeliness_score = $8, uniqueness_score = $9, "
            "validity_score = $10, row_count = $11, column_count = $12, "
            "trend_direction = $13, score_delta = $14, alerts_count = $15, "
            "critical_alerts = $16, snapshot_data = $17::jsonb, "
            "created_at = NOW()",
            dashboard_name, dataset_name, snapshot_date,
            metrics.get("overall_score"),
            metrics.get("completeness_score"),
            metrics.get("accuracy_score"),
            metrics.get("consistency_score"),
            metrics.get("timeliness_score"),
            metrics.get("uniqueness_score"),
            metrics.get("validity_score"),
            metrics.get("row_count"),
            metrics.get("column_count"),
            metrics.get("trend_direction"),
            metrics.get("score_delta"),
            metrics.get("alerts_count", 0),
            metrics.get("critical_alerts", 0),
            json.dumps(metrics.get("snapshot_data", {})),
        )

        logger.info(
            "quality dashboard snapshot saved: %s/%s/%s score=%.4f",
            dashboard_name, dataset_name, snapshot_date,
            metrics.get("overall_score", 0),
        )

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _row_to_metrics(row: dict) -> dict:
        return {
            "found": True,
            "dataset_name": row.get("dataset_name"),
            "snapshot_date": str(row.get("snapshot_date")) if row.get("snapshot_date") else None,
            "overall_score": row.get("overall_score"),
            "completeness_score": row.get("completeness_score"),
            "accuracy_score": row.get("accuracy_score"),
            "consistency_score": row.get("consistency_score"),
            "timeliness_score": row.get("timeliness_score"),
            "uniqueness_score": row.get("uniqueness_score"),
            "validity_score": row.get("validity_score"),
            "row_count": row.get("row_count"),
            "column_count": row.get("column_count"),
            "trend_direction": row.get("trend_direction"),
            "score_delta": row.get("score_delta"),
            "alerts_count": row.get("alerts_count"),
            "critical_alerts": row.get("critical_alerts"),
        }

    @staticmethod
    def _dimension_to_column(dimension: str) -> str:
        mapping = {
            "completeness": "completeness_score",
            "consistency": "consistency_score",
            "uniqueness": "uniqueness_score",
            "timeliness": "timeliness_score",
            "validity": "validity_score",
            "accuracy": "accuracy_score",
        }
        return mapping.get(dimension, f"{dimension}_score")

    @staticmethod
    def _extract_issues_from_report(report: dict) -> list[dict]:
        issues = []
        dimensions = report.get("dimensions", {})
        if isinstance(dimensions, str):
            try:
                dimensions = json.loads(dimensions)
            except (json.JSONDecodeError, TypeError):
                dimensions = {}

        if not isinstance(dimensions, dict):
            return []

        for dim, info in dimensions.items():
            if not isinstance(info, dict):
                continue
            score = info.get("score", 1.0)
            if score < 0.95:
                issues.append({
                    "severity": "critical" if score < 0.5 else "warning",
                    "dimension": dim,
                    "score": score,
                    "description": f"{dim} score is {score:.4f}",
                })

        return issues



