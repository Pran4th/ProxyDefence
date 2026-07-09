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


class DatasetProfiler:
    @staticmethod
    def _entropy(series: pd.Series) -> float:
        counts = series.value_counts(dropna=True)
        if len(counts) == 0:
            return 0.0
        probs = counts / counts.sum()
        return float(-(probs * np.log2(probs)).sum())

    @staticmethod
    def _profile_column(df: pd.DataFrame, col: str) -> dict[str, Any]:
        col_data = df[col]
        non_null = col_data.dropna()
        profile: dict[str, Any] = {
            "dtype": str(col_data.dtype),
            "missing_count": int(col_data.isnull().sum()),
            "missing_rate": round(float(col_data.isnull().mean()), 6),
            "unique_count": int(col_data.nunique()),
            "cardinality": round(float(col_data.nunique() / max(len(col_data), 1)), 6),
        }

        entropy = None
        samples: list[Any] = []
        extra: dict[str, Any] = {}

        if pd.api.types.is_numeric_dtype(col_data) and not pd.api.types.is_bool_dtype(col_data):
            if len(non_null) > 0:
                extra.update({
                    "min": float(non_null.min()),
                    "max": float(non_null.max()),
                    "mean": float(non_null.mean()),
                    "std": float(non_null.std()) if len(non_null) > 1 else 0.0,
                    "p25": float(non_null.quantile(0.25)),
                    "p50": float(non_null.median()),
                    "p75": float(non_null.quantile(0.75)),
                })
            samples = [float(v) for v in non_null.head(5).tolist()]
        else:
            entropy = DatasetProfiler._entropy(col_data)
            samples = [str(v) for v in non_null.head(5).tolist()]

        profile["entropy"] = entropy
        profile["samples"] = samples
        profile["profile_json"] = extra
        return profile

    @staticmethod
    async def profile(df: pd.DataFrame, dataset_name: str, version: int) -> list[dict[str, Any]]:
        profiles = []
        try:
            pool = await _get_pool()
        except Exception as e:
            logger.warning("failed to connect for profiling persistence", dataset=dataset_name, error=str(e))
            pool = None

        for col in df.columns:
            p = DatasetProfiler._profile_column(df, col)
            p["column_name"] = col
            profiles.append(p)

            if pool:
                try:
                    await pool.execute(
                        """INSERT INTO ml.dataset_profiles
                           (dataset_name, dataset_version, column_name, dtype, missing_count,
                            missing_rate, unique_count, cardinality, entropy, samples, profile_json)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                           ON CONFLICT (dataset_name, dataset_version, column_name) DO UPDATE SET
                               dtype = EXCLUDED.dtype,
                               missing_count = EXCLUDED.missing_count,
                               missing_rate = EXCLUDED.missing_rate,
                               unique_count = EXCLUDED.unique_count,
                               cardinality = EXCLUDED.cardinality,
                               entropy = EXCLUDED.entropy,
                               samples = EXCLUDED.samples,
                               profile_json = EXCLUDED.profile_json""",
                        dataset_name, version, col, p["dtype"], p["missing_count"], p["missing_rate"],
                        p["unique_count"], p["cardinality"], p["entropy"],
                        json.dumps(p["samples"], default=str), json.dumps(p["profile_json"], default=str),
                    )
                except Exception as e:
                    logger.warning("failed to persist column profile", dataset=dataset_name, column=col, error=str(e))

        logger.info("profiling complete", dataset=dataset_name, version=version, columns=len(profiles))
        return profiles

    @staticmethod
    async def get_profile(dataset_name: str, version: int) -> list[dict[str, Any]]:
        pool = await _get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.dataset_profiles WHERE dataset_name = $1 AND dataset_version = $2 ORDER BY column_name",
            dataset_name, version,
        )
        results = []
        for r in rows:
            d = dict(r)
            for k in ("samples", "profile_json"):
                if isinstance(d.get(k), str):
                    d[k] = json.loads(d[k])
            results.append(d)
        return results

    @staticmethod
    async def get_column_profile(dataset_name: str, version: int, column: str) -> dict[str, Any] | None:
        pool = await _get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.dataset_profiles WHERE dataset_name = $1 AND dataset_version = $2 AND column_name = $3",
            dataset_name, version, column,
        )
        if not row:
            return None
        d = dict(row)
        for k in ("samples", "profile_json"):
            if isinstance(d.get(k), str):
                d[k] = json.loads(d[k])
        return d
