from typing import Any

import asyncpg
import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)


class DatasetExplorer:
    @staticmethod
    def overview(df: pd.DataFrame) -> dict[str, Any]:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns
        datetime_cols = df.select_dtypes(include=["datetime64"]).columns
        bool_cols = df.select_dtypes(include=["bool"]).columns

        return {
            "shape": list(df.shape),
            "total_cells": df.size,
            "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
            "column_types": {
                "numerical": len(numeric_cols),
                "categorical": len(categorical_cols),
                "datetime": len(datetime_cols),
                "boolean": len(bool_cols),
            },
            "missing_summary": {
                "total_missing": int(df.isnull().sum().sum()),
                "missing_rate": round(float(df.isnull().mean().mean()), 4),
            },
            "duplicate_count": int(df.duplicated().sum()),
            "head": df.head(5).to_dict(orient="records"),
        }

    @staticmethod
    def missing_analysis(df: pd.DataFrame, threshold: float = 0.0) -> pd.DataFrame:
        missing = pd.DataFrame({
            "column": df.columns,
            "missing_count": df.isnull().sum().values,
            "missing_rate": df.isnull().mean().values,
            "dtype": [str(df[c].dtype) for c in df.columns],
        })
        if threshold > 0:
            missing = missing[missing["missing_rate"] >= threshold]
        return missing.sort_values("missing_rate", ascending=False)

    @staticmethod
    def duplicate_analysis(df: pd.DataFrame) -> dict[str, Any]:
        dups = df.duplicated()
        total = dups.sum()
        if total == 0:
            return {"duplicate_count": 0, "duplicate_rate": 0.0}
        dup_rows = df[dups]
        return {
            "duplicate_count": int(total),
            "duplicate_rate": round(total / len(df), 6),
            "sample_duplicates": dup_rows.head(5).to_dict(orient="records"),
        }


class FeatureExplorer:
    @staticmethod
    def analyze_numeric(series: pd.Series) -> dict[str, Any]:
        valid = series.dropna()
        result: dict[str, Any] = {
            "dtype": str(series.dtype),
            "count": len(valid),
            "missing": int(series.isnull().sum()),
            "missing_rate": round(float(series.isnull().mean()), 4),
            "unique": int(series.nunique()),
        }
        if len(valid) > 0:
            result.update({
                "mean": round(float(valid.mean()), 4),
                "std": round(float(valid.std()), 4),
                "min": round(float(valid.min()), 4),
                "max": round(float(valid.max()), 4),
                "median": round(float(valid.median()), 4),
                "skew": round(float(valid.skew()), 4),
                "kurtosis": round(float(valid.kurtosis()), 4),
                "p1": round(float(valid.quantile(0.01)), 4),
                "p99": round(float(valid.quantile(0.99)), 4),
                "iqr": round(float(valid.quantile(0.75) - valid.quantile(0.25)), 4),
            })
        return result

    @staticmethod
    def analyze_categorical(series: pd.Series) -> dict[str, Any]:
        valid = series.dropna()
        vc = valid.value_counts()
        result = {
            "dtype": str(series.dtype),
            "count": len(valid),
            "missing": int(series.isnull().sum()),
            "missing_rate": round(float(series.isnull().mean()), 4),
            "unique": int(series.nunique()),
            "top_value": str(vc.index[0]) if len(vc) > 0 else None,
            "top_frequency": round(float(vc.iloc[0] / len(valid)), 4) if len(valid) > 0 else 0,
            "value_counts": {str(k): int(v) for k, v in vc.head(10).items()},
        }
        if len(valid) > 0:
            from scipy import stats as scipy_stats
            probs = vc / len(valid)
            result["entropy"] = round(float(-(probs * np.log2(probs + 1e-10)).sum()), 4)
        return result


class CorrelationExplorer:
    @staticmethod
    def analyze(df: pd.DataFrame, method: str = "pearson") -> dict[str, Any]:
        numeric = df.select_dtypes(include=[np.number])
        if numeric.shape[1] < 2:
            return {"warning": "Need at least 2 numeric columns for correlation analysis"}

        corr = numeric.corr(method=method)
        corr_values = corr.values
        mask = ~np.eye(corr_values.shape[0], dtype=bool)
        flat_corr = corr_values[mask]

        corr_df = corr.where(mask).stack().reset_index()
        corr_df.columns = ["feature_a", "feature_b", "correlation"]
        corr_df["abs_correlation"] = corr_df["correlation"].abs()

        high_corr = corr_df[corr_df["abs_correlation"] > 0.8].sort_values("abs_correlation", ascending=False)

        result = {
            "method": method,
            "matrix_shape": list(corr.shape),
            "mean_abs_correlation": round(float(np.abs(flat_corr).mean()), 4),
            "max_correlation": round(float(np.abs(corr_values[~np.eye(corr_values.shape[0], dtype=bool)]).max()), 4),
            "high_correlations": high_corr.head(20).to_dict(orient="records"),
            "features_with_high_corr": list(set(
                list(high_corr["feature_a"].unique()) + list(high_corr["feature_b"].unique())
            )),
        }
        return result

    @staticmethod
    def mutual_information(df: pd.DataFrame, target_col: str) -> dict[str, float]:
        numeric = df.select_dtypes(include=[np.number])
        if target_col not in numeric.columns:
            return {}
        y = numeric[target_col].fillna(0)
        X = numeric.drop(columns=[target_col]).fillna(0)
        try:
            from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
            if y.nunique() > 10:
                mi = mutual_info_regression(X, y, random_state=42)
            else:
                mi = mutual_info_classif(X, y, random_state=42)
            return {col: round(float(mi[i]), 6) for i, col in enumerate(X.columns)}
        except Exception as e:
            logger.warning("mutual information computation failed: %s", e)
            return {}


class StatisticsExplorer:
    @staticmethod
    def summary(df: pd.DataFrame) -> dict[str, Any]:
        numeric = df.select_dtypes(include=[np.number])
        categorical = df.select_dtypes(include=["object", "category"])

        result = {
            "overview": DatasetExplorer.overview(df),
            "numeric_summary": numeric.describe().to_dict() if len(numeric.columns) > 0 else {},
            "categorical_summary": {
                col: {
                    "unique": int(df[col].nunique()),
                    "top": str(df[col].value_counts().index[0]) if df[col].nunique() > 0 else None,
                    "top_freq": int(df[col].value_counts().iloc[0]) if df[col].nunique() > 0 else 0,
                }
                for col in categorical.columns
            } if len(categorical.columns) > 0 else {},
        }
        return result


class SchemaExplorer:
    async def get_table_schema(self, table_name: str, schema: str = "ml", pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, "
            "numeric_precision, numeric_scale "
            "FROM information_schema.columns "
            "WHERE table_schema = $1 AND table_name = $2 "
            "ORDER BY ordinal_position",
            schema, table_name,
        )
        return {
            "table": f"{schema}.{table_name}",
            "columns": [dict(r) for r in rows],
            "column_count": len(rows),
        }

    async def get_all_tables(self, schema: str = "ml", pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT t.table_name, (SELECT count(*) FROM information_schema.columns c "
            "WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) AS column_count "
            "FROM information_schema.tables t "
            "WHERE t.table_schema = $1 AND t.table_type = 'BASE TABLE' "
            "ORDER BY t.table_name",
            schema,
        )
        return [dict(r) for r in rows]

    async def find_columns(self, name_pattern: str, schema: str = "ml", pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT table_schema, table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = $1 AND column_name ILIKE $2 "
            "ORDER BY table_name, ordinal_position",
            schema, f"%{name_pattern}%",
        )
        return [dict(r) for r in rows]

    async def get_table_statistics(self, table_name: str, schema: str = "ml", pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT reltuples::BIGINT AS row_count, "
            "pg_total_relation_size($1 || '.' || $2) AS total_size_bytes, "
            "pg_relation_size($1 || '.' || $2) AS table_size_bytes, "
            "pg_indexes_size($1 || '.' || $2) AS index_size_bytes "
            "FROM pg_class WHERE oid = ($1 || '.' || $2)::REGCLASS",
            schema, table_name,
        )
        return dict(row) if row else {}

    async def get_foreign_keys(self, table_name: str, schema: str = "ml", pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT kcu.column_name, "
            "ccu.table_schema AS foreign_schema, "
            "ccu.table_name AS foreign_table, "
            "ccu.column_name AS foreign_column, "
            "tc.constraint_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "AND tc.table_schema = $1 AND tc.table_name = $2",
            schema, table_name,
        )
        return [dict(r) for r in rows]

    async def get_indexes(self, table_name: str, schema: str = "ml", pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT i.relname AS index_name, "
            "a.attname AS column_name, "
            "ix.indisunique AS is_unique, "
            "ix.indisprimary AS is_primary, "
            "am.amname AS index_type "
            "FROM pg_index ix "
            "JOIN pg_class i ON i.oid = ix.indexrelid "
            "JOIN pg_class t ON t.oid = ix.indrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey) "
            "JOIN pg_am am ON i.relam = am.oid "
            "WHERE t.relname = $1 AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = $2) "
            "ORDER BY i.relname, a.attnum",
            table_name, schema,
        )
        return [dict(r) for r in rows]


class MetadataExplorer:
    async def get_dataset_metadata(self, dataset_name: str, version: int | None = None, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        if version is not None:
            row = await pool.fetchrow(
                "SELECT * FROM ml.datasets WHERE name = $1 AND version = $2", dataset_name, version,
            )
        else:
            row = await pool.fetchrow(
                "SELECT * FROM ml.datasets WHERE name = $1 ORDER BY version DESC LIMIT 1", dataset_name,
            )
        base = dict(row) if row else {}
        if base:
            stats_row = await pool.fetchrow(
                "SELECT * FROM ml.dataset_statistics WHERE dataset_name = $1 AND dataset_version = $2",
                base.get("name"), base.get("version"),
            )
            base["statistics"] = dict(stats_row) if stats_row else None
            card_row = await pool.fetchrow(
                "SELECT * FROM ml.dataset_cards WHERE dataset_name = $1", base.get("name"),
            )
            base["card"] = dict(card_row) if card_row else None
            validations = await pool.fetch(
                "SELECT * FROM ml.dataset_validations WHERE dataset_name = $1 AND dataset_version = $2",
                base.get("name"), base.get("version"),
            )
            base["validations"] = [dict(r) for r in validations]
        return base

    async def get_feature_metadata(self, feature_name: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        if feature_name:
            rows = await pool.fetch(
                "SELECT * FROM ml.feature_definitions WHERE name = $1 ORDER BY version DESC", feature_name,
            )
        else:
            rows = await pool.fetch("SELECT * FROM ml.feature_definitions ORDER BY name, version DESC")
        return [dict(r) for r in rows]

    async def get_model_metadata(self, model_name: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        if model_name:
            rows = await pool.fetch(
                "SELECT * FROM ml.model_versions WHERE name = $1 ORDER BY version DESC", model_name,
            )
        else:
            rows = await pool.fetch("SELECT * FROM ml.model_versions ORDER BY name, version DESC")
        return [dict(r) for r in rows]

    async def get_experiment_metadata(self, experiment_uuid: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        if experiment_uuid:
            rows = await pool.fetch(
                "SELECT * FROM ml.experiments WHERE uuid = $1 ORDER BY created_at DESC", experiment_uuid,
            )
        else:
            rows = await pool.fetch("SELECT * FROM ml.experiments ORDER BY created_at DESC")
        results = []
        for r in rows:
            rec = dict(r)
            runs = await pool.fetch(
                "SELECT uuid, run_name, run_number, status, metrics, params, duration_seconds, "
                "start_time, end_time, created_at FROM ml.experiment_runs WHERE experiment_uuid = $1 "
                "ORDER BY run_number", rec["uuid"],
            )
            rec["runs"] = [dict(rn) for rn in runs]
            results.append(rec)
        return results

    async def get_pipeline_metadata(self, pipeline_name: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        if pipeline_name:
            rows = await pool.fetch(
                "SELECT * FROM ml.feature_pipelines WHERE name = $1 ORDER BY version DESC", pipeline_name,
            )
        else:
            rows = await pool.fetch("SELECT * FROM ml.feature_pipelines ORDER BY name, version DESC")
        return [dict(r) for r in rows]

    async def get_quality_metadata(self, dataset_name: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        if dataset_name:
            rows = await pool.fetch(
                "SELECT * FROM ml.quality_reports WHERE dataset_name = $1 ORDER BY executed_at DESC", dataset_name,
            )
        else:
            rows = await pool.fetch("SELECT * FROM ml.quality_reports ORDER BY executed_at DESC")
        return [dict(r) for r in rows]


class PipelineExplorer:
    async def list_pipelines(self, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT fp.uuid, fp.name, fp.version, fp.description, fp.pipeline_type, "
            "fp.source_datasets, fp.target_feature_group, fp.schedule_cron, fp.is_active, "
            "fp.created_at, fp.updated_at, fp.created_by, "
            "(SELECT count(*) FROM ml.feature_pipeline_runs pr WHERE pr.pipeline_name = fp.name) AS run_count "
            "FROM ml.feature_pipelines fp ORDER BY fp.name, fp.version DESC",
        )
        return [dict(r) for r in rows]

    async def get_pipeline(self, name: str, version: int | None = None, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        if version is not None:
            row = await pool.fetchrow(
                "SELECT * FROM ml.feature_pipelines WHERE name = $1 AND version = $2", name, version,
            )
        else:
            row = await pool.fetchrow(
                "SELECT * FROM ml.feature_pipelines WHERE name = $1 ORDER BY version DESC LIMIT 1", name,
            )
        return dict(row) if row else {}

    async def get_pipeline_runs(self, name: str, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.feature_pipeline_runs WHERE pipeline_name = $1 ORDER BY started_at DESC NULLS LAST",
            name,
        )
        return [dict(r) for r in rows]

    async def get_pipeline_run(self, run_uuid: str, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.feature_pipeline_runs WHERE uuid = $1", run_uuid,
        )
        return dict(row) if row else {}

    async def get_failed_pipelines(self, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT pr.*, p.description FROM ml.feature_pipeline_runs pr "
            "JOIN ml.feature_pipelines p ON p.name = pr.pipeline_name AND p.version = pr.pipeline_version "
            "WHERE pr.run_status IN ('failed', 'error') "
            "ORDER BY pr.created_at DESC",
        )
        return [dict(r) for r in rows]

    async def get_pipeline_stats(self, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        total = await pool.fetchrow("SELECT count(*) AS total FROM ml.feature_pipelines")
        active = await pool.fetchrow("SELECT count(*) AS active FROM ml.feature_pipelines WHERE is_active = TRUE")
        runs = await pool.fetchrow(
            "SELECT count(*) AS total_runs, "
            "count(*) FILTER (WHERE run_status = 'completed') AS completed, "
            "count(*) FILTER (WHERE run_status = 'failed') AS failed, "
            "count(*) FILTER (WHERE run_status = 'running') AS running, "
            "coalesce(avg(duration_seconds) FILTER (WHERE run_status = 'completed'), 0) AS avg_duration_seconds "
            "FROM ml.feature_pipeline_runs",
        )
        return {
            "pipelines": dict(total).get("total", 0),
            "active_pipelines": dict(active).get("active", 0),
            "runs": dict(runs),
        }


class ExperimentExplorer:
    async def get_experiment_summary(self, experiment_uuid: str, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM ml.experiments WHERE uuid = $1", experiment_uuid)
        if not row:
            return {}
        exp = dict(row)
        runs = await pool.fetch(
            "SELECT uuid, run_name, run_number, status, metrics, params, duration_seconds, "
            "start_time, end_time, error_message FROM ml.experiment_runs "
            "WHERE experiment_uuid = $1 ORDER BY run_number", experiment_uuid,
        )
        run_dicts = [dict(r) for r in runs]
        completed = [r for r in run_dicts if r.get("status") == "completed"]
        best_run = None
        if completed:
            best_run = max(completed, key=lambda r: float(r.get("metrics", {}).get("f1", 0)))
            exp["best_run"] = best_run
        exp["run_count"] = len(run_dicts)
        exp["completed_count"] = len(completed)
        exp["failed_count"] = len([r for r in run_dicts if r.get("status") == "failed"])
        exp["runs"] = run_dicts
        return exp

    async def get_best_runs(self, metric: str = "f1", n: int = 5, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT er.*, e.name AS experiment_name FROM ml.experiment_runs er "
            "JOIN ml.experiments e ON e.uuid = er.experiment_uuid "
            "WHERE er.status = 'completed' AND er.metrics->>$1 IS NOT NULL "
            "ORDER BY (er.metrics->>$1)::DOUBLE PRECISION DESC LIMIT $2",
            metric, n,
        )
        return [dict(r) for r in rows]

    async def get_experiment_comparison(self, experiment_uuids: list[str], pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        experiments = []
        for uuid in experiment_uuids:
            summary = await self.get_experiment_summary(uuid, pool=pool)
            if summary:
                experiments.append(summary)
        metrics = {}
        for exp in experiments:
            for run in exp.get("runs", []):
                run_metrics = run.get("metrics", {})
                for k, v in run_metrics.items():
                    if k not in metrics:
                        metrics[k] = {}
                    if isinstance(v, (int, float)):
                        if exp["name"] not in metrics[k]:
                            metrics[k][exp["name"]] = []
                        metrics[k][exp["name"]].append(float(v))
        summary = {}
        for metric_name, exp_values in metrics.items():
            summary[metric_name] = {}
            for exp_name, values in exp_values.items():
                if values:
                    summary[metric_name][exp_name] = {
                        "mean": round(float(np.mean(values)), 4),
                        "std": round(float(np.std(values)), 4),
                        "max": round(float(max(values)), 4),
                        "min": round(float(min(values)), 4),
                    }
        return {"experiments": experiments, "comparison": summary}

    async def get_experiment_timeline(self, experiment_uuid: str, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT uuid, run_name, run_number, status, duration_seconds, "
            "start_time, end_time, created_at, metrics "
            "FROM ml.experiment_runs WHERE experiment_uuid = $1 "
            "ORDER BY run_number", experiment_uuid,
        )
        return [dict(r) for r in rows]

    async def get_experiment_params(self, experiment_uuid: str, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT run_number, run_name, params FROM ml.experiment_runs "
            "WHERE experiment_uuid = $1 ORDER BY run_number", experiment_uuid,
        )
        return [dict(r) for r in rows]

    async def get_experiment_metrics(self, experiment_uuid: str, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT run_number, run_name, metrics FROM ml.experiment_runs "
            "WHERE experiment_uuid = $1 AND status = 'completed' ORDER BY run_number", experiment_uuid,
        )
        all_metrics: dict[str, list[float]] = {}
        for r in rows:
            rec = dict(r)
            run_metrics = rec.get("metrics", {})
            if isinstance(run_metrics, dict):
                for k, v in run_metrics.items():
                    if isinstance(v, (int, float)):
                        if k not in all_metrics:
                            all_metrics[k] = []
                        all_metrics[k].append(float(v))
        distributions = {}
        for metric_name, values in all_metrics.items():
            if values:
                distributions[metric_name] = {
                    "count": len(values),
                    "mean": round(float(np.mean(values)), 4),
                    "std": round(float(np.std(values)), 4) if len(values) > 1 else 0.0,
                    "min": round(float(min(values)), 4),
                    "max": round(float(max(values)), 4),
                    "p25": round(float(np.percentile(values, 25)), 4),
                    "p50": round(float(np.median(values)), 4),
                    "p75": round(float(np.percentile(values, 75)), 4),
                }
        return {"distributions": distributions, "runs": [dict(r) for r in rows]}


class ArtifactExplorer:
    async def list_artifacts(self, experiment_uuid: str | None = None, run_uuid: str | None = None,
                              artifact_type: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        conditions = []
        params = []
        idx = 1
        if experiment_uuid:
            conditions.append(f"experiment_uuid = ${idx}")
            params.append(experiment_uuid)
            idx += 1
        if run_uuid:
            conditions.append(f"run_uuid = ${idx}")
            params.append(run_uuid)
            idx += 1
        if artifact_type:
            conditions.append(f"artifact_type = ${idx}")
            params.append(artifact_type)
            idx += 1
        where = " AND ".join(conditions) if conditions else "TRUE"
        rows = await pool.fetch(
            f"SELECT * FROM ml.research_artifacts WHERE {where} ORDER BY created_at DESC",
            *params,
        )
        return [dict(r) for r in rows]

    async def get_artifact(self, artifact_uuid: str, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.research_artifacts WHERE uuid = $1", artifact_uuid,
        )
        return dict(row) if row else {}

    async def get_artifact_types(self, pool: asyncpg.Pool | None = None) -> list[str]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT DISTINCT artifact_type FROM ml.research_artifacts ORDER BY artifact_type",
        )
        return [r["artifact_type"] for r in rows]

    async def get_artifact_stats(self, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT artifact_type, count(*) AS count, "
            "coalesce(sum(file_size), 0) AS total_bytes, "
            "coalesce(avg(file_size), 0) AS avg_bytes "
            "FROM ml.research_artifacts GROUP BY artifact_type ORDER BY artifact_type",
        )
        return {
            "total_artifacts": sum(r["count"] for r in rows),
            "total_bytes": sum(r["total_bytes"] for r in rows),
            "by_type": [dict(r) for r in rows],
        }

    async def get_recent_artifacts(self, n: int = 20, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.research_artifacts ORDER BY created_at DESC LIMIT $1", n,
        )
        return [dict(r) for r in rows]


class ModelExplorer:
    async def list_models(self, stage: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        if stage:
            rows = await pool.fetch(
                "SELECT * FROM ml.model_versions WHERE stage = $1::ml.model_stage "
                "ORDER BY name, version DESC", stage,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM ml.model_versions ORDER BY name, version DESC",
            )
        return [dict(r) for r in rows]

    async def get_model_detail(self, model_uuid: str, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.model_versions WHERE uuid = $1", model_uuid,
        )
        if not row:
            return {}
        result = dict(row)
        governance = await pool.fetch(
            "SELECT * FROM ml.model_governance WHERE model_version_uuid = $1 ORDER BY created_at DESC",
            model_uuid,
        )
        result["governance"] = [dict(g) for g in governance]
        importance = await pool.fetch(
            "SELECT * FROM ml.feature_importance WHERE model_version_uuid = $1 ORDER BY rank NULLS LAST",
            model_uuid,
        )
        result["feature_importance"] = [dict(i) for i in importance]
        return result

    async def get_model_versions(self, model_name: str, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.model_versions WHERE name = $1 ORDER BY version DESC", model_name,
        )
        return [dict(r) for r in rows]

    async def get_best_model(self, metric: str = "f1", pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.model_versions "
            "WHERE metrics->>$1 IS NOT NULL "
            "ORDER BY (metrics->>$1)::DOUBLE PRECISION DESC LIMIT 1",
            metric,
        )
        return dict(row) if row else {}

    async def get_model_lineage(self, model_uuid: str, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            pool = await get_pool()
        model = await pool.fetchrow("SELECT * FROM ml.model_versions WHERE uuid = $1", model_uuid)
        if not model:
            return {}
        mv = dict(model)
        dataset_name = mv.get("dataset_uuid")
        dataset_info = None
        if dataset_name:
            dataset_info = await pool.fetchrow(
                "SELECT * FROM ml.datasets WHERE uuid = $1", dataset_name,
            )
        features = await pool.fetch(
            "SELECT fi.* FROM ml.feature_importance fi WHERE fi.model_version_uuid = $1 "
            "ORDER BY fi.rank NULLS LAST", model_uuid,
        )
        return {
            "model": mv,
            "dataset": dict(dataset_info) if dataset_info else None,
            "features": [dict(f) for f in features],
        }

    async def get_model_governance(self, model_uuid: str, pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.model_governance WHERE model_version_uuid = $1 ORDER BY created_at DESC",
            model_uuid,
        )
        return [dict(r) for r in rows]

    async def get_model_performance_trend(self, model_name: str, metric: str = "f1", pool: asyncpg.Pool | None = None) -> list[dict]:
        if pool is None:
            pool = await get_pool()
        rows = await pool.fetch(
            "SELECT name, version, stage, metrics->>$1 AS metric_value, training_date, created_at "
            "FROM ml.model_versions "
            "WHERE name = $2 AND metrics->>$1 IS NOT NULL "
            "ORDER BY version",
            metric, model_name,
        )
        return [dict(r) for r in rows]
