from typing import Any

import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

VALID_FEATURE_TYPES = {
    "numerical", "categorical", "boolean", "timestamp",
    "geospatial", "entity_statistics", "relationship_statistics",
    "historical_capacity", "infrastructure",
    "embedding_reference", "graph_placeholder",
}


class FeatureRegistry:
    def __init__(self, pool: asyncpg.Pool | None = None):
        self._pool = pool

    async def _pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def create(self, name: str, feature_type: str, description: str | None = None,
                     transform_config: dict | None = None, source_feature: str | None = None) -> dict[str, Any]:
        if feature_type not in VALID_FEATURE_TYPES:
            raise ValueError(f"Invalid feature_type: {feature_type}. Valid: {sorted(VALID_FEATURE_TYPES)}")
        pool = await get_pool()
        row = await pool.fetchrow(
            "INSERT INTO ml.feature_definitions (name, version, feature_type, description, transform_config, source_feature) "
            "VALUES ($1, 1, $2, $3, $4, $5) RETURNING uuid, name, version, feature_type, description, created_at",
            name, feature_type, description, transform_config or {}, source_feature,
        )
        logger.info("feature created", name=name, type=feature_type)
        return dict(row)

    async def list(self, feature_type: str | None = None, active_only: bool = True, limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        pool = await get_pool()
        conditions = ["1=1"]
        params: list = []
        if feature_type:
            conditions.append(f"feature_type = ${len(params) + 1}")
            params.append(feature_type)
        if active_only:
            conditions.append("is_active = TRUE")
        where = " AND ".join(conditions)
        count = await pool.fetchval(f"SELECT COUNT(*) FROM ml.feature_definitions WHERE {where}", *params)
        params.append(limit)
        params.append(offset)
        rows = await pool.fetch(
            f"SELECT * FROM ml.feature_definitions WHERE {where} ORDER BY name, version DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
            *params,
        )
        return [dict(r) for r in rows], count or 0

    async def get(self, uuid: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM ml.feature_definitions WHERE uuid = $1", uuid)
        return dict(row) if row else None

    async def get_by_name(self, name: str, version: int | None = None) -> dict[str, Any] | None:
        pool = await get_pool()
        if version:
            row = await pool.fetchrow(
                "SELECT * FROM ml.feature_definitions WHERE name = $1 AND version = $2", name, version
            )
        else:
            row = await pool.fetchrow(
                "SELECT * FROM ml.feature_definitions WHERE name = $1 ORDER BY version DESC LIMIT 1", name
            )
        return dict(row) if row else None

    async def create_version(self, uuid: str) -> dict[str, Any] | None:
        pool = await get_pool()
        existing = await pool.fetchrow("SELECT * FROM ml.feature_definitions WHERE uuid = $1", uuid)
        if not existing:
            return None
        max_ver = await pool.fetchval(
            "SELECT MAX(version) FROM ml.feature_definitions WHERE name = $1", existing["name"]
        )
        new_ver = (max_ver or 0) + 1
        row = await pool.fetchrow(
            "INSERT INTO ml.feature_definitions (name, version, feature_type, description, transform_config, source_feature) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            existing["name"], new_ver, existing["feature_type"], existing["description"],
            existing["transform_config"], existing["source_feature"],
        )
        logger.info("feature version created", name=existing["name"], version=new_ver)
        return dict(row) if row else None

    async def deactivate(self, uuid: str) -> bool:
        pool = await get_pool()
        result = await pool.execute("UPDATE ml.feature_definitions SET is_active = FALSE WHERE uuid = $1", uuid)
        return "UPDATE 1" in result
