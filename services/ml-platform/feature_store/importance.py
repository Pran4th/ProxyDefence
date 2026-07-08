from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)


class FeatureImportance:
    @staticmethod
    async def compute_tree_importance(model, feature_names: list[str],
                                       model_name: str, model_version: int,
                                       model_version_uuid: str | None = None) -> list[dict[str, Any]]:
        if not hasattr(model, "feature_importances_"):
            logger.warning("model does not have feature_importances_")
            return []

        importances = model.feature_importances_
        total = importances.sum() or 1
        normalized = importances / total

        pool = await get_pool()
        results = []
        for rank, (name, score) in enumerate(
            sorted(zip(feature_names, normalized), key=lambda x: -x[1])
        ):
            row = await pool.fetchrow(
                "INSERT INTO ml.feature_importance (model_version_uuid, model_name, model_version, "
                "feature_name, importance_score, importance_type, rank) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *",
                model_version_uuid, model_name, model_version,
                name, round(float(score), 6), "tree_based", rank + 1,
            )
            results.append(dict(row))

        logger.info("feature importance computed for %s v%d (%d features)",
                     model_name, model_version, len(results))
        return results

    @staticmethod
    async def compute_permutation_importance(model, X: pd.DataFrame, y: pd.Series,
                                              feature_names: list[str],
                                              model_name: str, model_version: int,
                                              n_repeats: int = 5,
                                              model_version_uuid: str | None = None) -> list[dict[str, Any]]:
        from sklearn.inspection import permutation_importance
        result = permutation_importance(model, X, y, n_repeats=n_repeats, random_state=42, n_jobs=-1)
        importances = result.importances_mean
        total = np.abs(importances).sum() or 1
        normalized = np.abs(importances) / total

        pool = await get_pool()
        results = []
        for rank, (name, score, std) in enumerate(
            sorted(zip(feature_names, normalized, result.importances_std), key=lambda x: -x[1])
        ):
            row = await pool.fetchrow(
                "INSERT INTO ml.feature_importance (model_version_uuid, model_name, model_version, "
                "feature_name, importance_score, importance_type, rank) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *",
                model_version_uuid, model_name, model_version,
                name, round(float(score), 6), "permutation", rank + 1,
            )
            results.append(dict(row))

        return results

    @staticmethod
    async def get_importance(model_name: str, model_version: int,
                              importance_type: str | None = None,
                              limit: int = 50) -> list[dict[str, Any]]:
        pool = await get_pool()
        conditions = ["model_name = $1", "model_version = $2"]
        params: list[Any] = [model_name, model_version]
        if importance_type:
            conditions.append(f"importance_type = ${len(params) + 1}")
            params.append(importance_type)
        where = " AND ".join(conditions)
        params.append(limit)
        rows = await pool.fetch(
            f"SELECT * FROM ml.feature_importance WHERE {where} ORDER BY rank ASC LIMIT ${len(params)}",
            *params,
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def get_top_features(model_name: str, model_version: int,
                                n: int = 10) -> list[dict[str, Any]]:
        return await FeatureImportance.get_importance(model_name, model_version, limit=n)
