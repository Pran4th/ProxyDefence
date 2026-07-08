import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from config import ENERGY_SERVICE_URL
from db import get_pool
from feature_store.cache import get_feature_cache
from feature_store.registry import FeatureRegistry
from feature_store.builders import EnergyServiceDataLoader

logger = get_logger(__name__)


class FeaturePipeline:
    def __init__(self):
        self._registry = FeatureRegistry()
        self._cache = get_feature_cache()
        self._loader = EnergyServiceDataLoader(ENERGY_SERVICE_URL)

    async def compute_features(self, entity_type: str, entity_ids: list[str] | None = None,
                               feature_version: int | None = None) -> dict[str, dict[str, Any]]:
        tables = self._loader.fetch_all()
        df = self._loader.build_feature_matrix(tables)

        all_defs, _ = await self._registry.list(active_only=True)
        if not all_defs:
            logger.warning("no feature definitions found")
            return {}

        version = feature_version or max(d.get("version", 1) for d in all_defs)
        active = [d for d in all_defs if d.get("version", 1) == version or d.get("is_active")]
        from feature_store.builders import FeatureBuilder
        builder = FeatureBuilder(self._registry)
        feature_df = await builder.compute_all(active, df)

        result: dict[str, dict[str, Any]] = {}
        id_col = "uuid" if "uuid" in df.columns else df.columns[0]
        for idx in range(len(df)):
            eid = str(df.iloc[idx].get(id_col, f"row_{idx}"))
            if entity_ids and eid not in entity_ids:
                continue
            row_features: dict[str, Any] = {}
            for col in feature_df.columns:
                val = feature_df.iloc[idx][col]
                if isinstance(val, (np.integer,)):
                    val = int(val)
                elif isinstance(val, (np.floating,)):
                    val = float(val)
                elif isinstance(val, pd.Timestamp):
                    val = val.isoformat()
                row_features[col] = val
            result[eid] = row_features
            self._cache.set(entity_type, eid, version, row_features)

        pool = await get_pool()
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        for eid, feats in result.items():
            await pool.execute(
                "INSERT INTO ml.feature_vectors (entity_type, entity_id, feature_version, vector, expires_at) "
                "VALUES ($1, $2, $3, $4, $5) "
                "ON CONFLICT (entity_type, entity_id, feature_version) "
                "DO UPDATE SET vector = $4, computed_at = NOW(), expires_at = $5",
                entity_type, eid, version, json.dumps(feats), expires,
            )

        logger.info("computed features for %d entities (v%d)", len(result), version)
        return result

    async def get_features(self, entity_type: str, entity_id: str,
                           feature_version: int | None = None) -> dict[str, Any] | None:
        if feature_version is None:
            pool = await get_pool()
            row = await pool.fetchval(
                "SELECT MAX(feature_version) FROM ml.feature_vectors WHERE entity_type = $1 AND entity_id = $2",
                entity_type, entity_id,
            )
            feature_version = row or 1

        cached = self._cache.get(entity_type, entity_id, feature_version)
        if cached is not None:
            return cached

        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT vector FROM ml.feature_vectors "
            "WHERE entity_type = $1 AND entity_id = $2 AND feature_version = $3",
            entity_type, entity_id, feature_version,
        )
        if row:
            data = dict(json.loads(row["vector"]))
            self._cache.set(entity_type, entity_id, feature_version, data)
            return data

        return None

    async def refresh_all(self, entity_type: str | None = None):
        self._cache.invalidate(entity_type if entity_type else None)
        tables = self._loader.fetch_all()
        df = self._loader.build_feature_matrix(tables)
        all_defs, _ = await self._registry.list(active_only=True)
        version = max(d.get("version", 1) for d in all_defs) if all_defs else 1
        id_col = "uuid" if "uuid" in df.columns else df.columns[0]
        et = entity_type or "entity"
        for idx in range(len(df)):
            eid = str(df.iloc[idx].get(id_col, f"row_{idx}"))
            self._cache.invalidate(et, eid)


_feature_pipeline: FeaturePipeline | None = None


def get_feature_pipeline() -> FeaturePipeline:
    global _feature_pipeline
    if _feature_pipeline is None:
        _feature_pipeline = FeaturePipeline()
    return _feature_pipeline
