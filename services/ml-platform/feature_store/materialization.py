import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.shared.logging_config import get_logger
from db import get_pool
from config import DATASET_DIR

logger = get_logger(__name__)


class FeatureMaterialization:
    def __init__(self, batch_size: int = 1000):
        self._batch_size = batch_size

    async def materialize_features(self, entity_type: str, feature_version: int,
                                    entity_ids: list[str] | None = None) -> dict[str, Any]:
        pool = await get_pool()
        conditions = ["entity_type = $1", "feature_version = $2"]
        params: list[Any] = [entity_type, feature_version]
        if entity_ids:
            conditions.append(f"entity_id = ANY(${len(params) + 1})")
            params.append(entity_ids)

        where = " AND ".join(conditions)
        rows = await pool.fetch(
            f"SELECT entity_id, vector FROM ml.feature_vectors WHERE {where}",
            *params,
        )

        materialized = {}
        for r in rows:
            vector = json.loads(r["vector"]) if isinstance(r["vector"], str) else r["vector"]
            materialized[r["entity_id"]] = vector

        import pandas as pd
        df = pd.DataFrame.from_dict(materialized, orient="index")
        df.index.name = "entity_id"

        from pathlib import Path
        import os
        output_dir = Path(DATASET_DIR) / "materialized" / entity_type / f"v{feature_version}"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "features.parquet"
        df.to_parquet(str(output_path))

        logger.info("materialized %d feature vectors for %s v%d at %s",
                     len(materialized), entity_type, feature_version, output_path)
        return {
            "entity_type": entity_type,
            "feature_version": feature_version,
            "entity_count": len(materialized),
            "feature_count": len(df.columns) if not df.empty else 0,
            "output_path": str(output_path),
            "columns": list(df.columns) if not df.empty else [],
        }

    async def get_materialization_status(self, entity_type: str,
                                           feature_version: int) -> dict[str, Any]:
        pool = await get_pool()
        count = await pool.fetchval(
            "SELECT COUNT(*) FROM ml.feature_vectors WHERE entity_type = $1 AND feature_version = $2",
            entity_type, feature_version,
        )
        has_expired = await pool.fetchval(
            "SELECT COUNT(*) FROM ml.feature_vectors WHERE entity_type = $1 AND feature_version = $2 "
            "AND (expires_at IS NOT NULL AND expires_at < NOW())",
            entity_type, feature_version,
        )
        return {
            "entity_type": entity_type,
            "feature_version": feature_version,
            "total_vectors": count or 0,
            "expired_vectors": has_expired or 0,
            "is_materialized": (count or 0) > 0,
        }
