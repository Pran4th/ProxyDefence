from __future__ import annotations

import json
from typing import Any

import asyncpg
import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from backend.shared.settings import settings

logger = get_logger(__name__)

_pool: asyncpg.Pool | None = None


def _default_dsn() -> str:
    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{host}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(_default_dsn(), min_size=1, max_size=2)
    return _pool


class DatasetStatistics:
    @staticmethod
    async def compute(df: pd.DataFrame, dataset_name: str, version: int) -> dict[str, Any]:
        row_count = len(df)
        total_cells = int(df.size)
        duplicate_count = int(df.duplicated().sum())
        missing_cells = int(df.isnull().sum().sum())

        stats: dict[str, Any] = {
            "row_count": row_count,
            "column_count": len(df.columns),
            "memory_bytes": int(df.memory_usage(deep=True).sum()),
            "duplicate_count": duplicate_count,
            "missing_cells": missing_cells,
            "total_cells": total_cells,
            "duplicate_rate": round(duplicate_count / row_count, 6) if row_count else 0.0,
            "missing_rate": round(missing_cells / total_cells, 6) if total_cells else 0.0,
            "numerical_columns": int(len(df.select_dtypes(include=[np.number]).columns)),
            "categorical_columns": int(len(df.select_dtypes(include=["category"]).columns)),
            "boolean_columns": int(len(df.select_dtypes(include=["bool"]).columns)),
            "datetime_columns": int(len(df.select_dtypes(include=["datetime64"]).columns)),
            "text_columns": int(len(df.select_dtypes(include=["object"]).columns)),
        }

        try:
            pool = await _get_pool()
            await pool.execute(
                """INSERT INTO ml.dataset_statistics
                   (dataset_name, dataset_version, row_count, column_count, memory_bytes,
                    duplicate_count, missing_cells, total_cells, duplicate_rate, missing_rate,
                    numerical_columns, categorical_columns, boolean_columns, datetime_columns,
                    text_columns, stats_json)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                   ON CONFLICT (dataset_name, dataset_version) DO UPDATE SET
                       row_count = EXCLUDED.row_count,
                       column_count = EXCLUDED.column_count,
                       memory_bytes = EXCLUDED.memory_bytes,
                       duplicate_count = EXCLUDED.duplicate_count,
                       missing_cells = EXCLUDED.missing_cells,
                       total_cells = EXCLUDED.total_cells,
                       duplicate_rate = EXCLUDED.duplicate_rate,
                       missing_rate = EXCLUDED.missing_rate,
                       numerical_columns = EXCLUDED.numerical_columns,
                       categorical_columns = EXCLUDED.categorical_columns,
                       boolean_columns = EXCLUDED.boolean_columns,
                       datetime_columns = EXCLUDED.datetime_columns,
                       text_columns = EXCLUDED.text_columns,
                       stats_json = EXCLUDED.stats_json,
                       computed_at = now()""",
                dataset_name, version, stats["row_count"], stats["column_count"], stats["memory_bytes"],
                stats["duplicate_count"], stats["missing_cells"], stats["total_cells"],
                stats["duplicate_rate"], stats["missing_rate"], stats["numerical_columns"],
                stats["categorical_columns"], stats["boolean_columns"], stats["datetime_columns"],
                stats["text_columns"], json.dumps(stats, default=str),
            )
        except Exception as e:
            logger.warning("failed to persist dataset statistics", dataset=dataset_name, error=str(e))

        logger.info(
            "statistics computed", dataset=dataset_name, version=version,
            cols=stats["column_count"], rows=stats["row_count"],
        )
        return stats

    @staticmethod
    async def get_stats(dataset_name: str, version: int) -> dict[str, Any] | None:
        pool = await _get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.dataset_statistics WHERE dataset_name = $1 AND dataset_version = $2",
            dataset_name, version,
        )
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("stats_json"), str):
            d["stats_json"] = json.loads(d["stats_json"])
        return d

    @staticmethod
    async def get_health_score(dataset_name: str, version: int) -> dict[str, Any]:
        stats = await DatasetStatistics.get_stats(dataset_name, version)
        if not stats:
            return {
                "dataset_name": dataset_name, "dataset_version": version,
                "score": None, "error": "no statistics found",
            }

        missing_rate = stats.get("missing_rate") or 0.0
        duplicate_rate = stats.get("duplicate_rate") or 0.0
        row_count = stats.get("row_count") or 0
        total_cells = stats.get("total_cells") or 0

        score = 100.0
        if missing_rate > 0.05:
            score -= missing_rate * 100
        if duplicate_rate > 0.05:
            score -= duplicate_rate * 50
        if row_count < 100:
            score -= 20
        if total_cells == 0:
            score -= 50
        score = max(0.0, min(100.0, score))

        return {
            "dataset_name": dataset_name,
            "dataset_version": version,
            "score": round(score, 2),
            "missing_rate": missing_rate,
            "duplicate_rate": duplicate_rate,
            "row_count": row_count,
        }
