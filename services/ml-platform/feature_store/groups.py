from typing import Any

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)

VALID_GROUP_TYPES = {"numerical", "categorical", "temporal", "geospatial", "text", "derived", "computed"}


class FeatureGroups:
    @staticmethod
    async def create_group(name: str, group_type: str, description: str | None = None,
                            metadata: dict | None = None) -> dict[str, Any]:
        if group_type not in VALID_GROUP_TYPES:
            raise ValueError(f"Invalid group_type: {group_type}. Valid: {sorted(VALID_GROUP_TYPES)}")
        pool = await get_pool()
        row = await pool.fetchrow(
            "INSERT INTO ml.feature_groups (name, description, group_type, metadata) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (name) DO UPDATE SET "
            "description = $2, group_type = $3, metadata = $4, updated_at = NOW() "
            "RETURNING uuid, name, group_type, created_at",
            name, description, group_type, metadata or {},
        )
        logger.info("feature group created", name=name, type=group_type)
        return dict(row)

    @staticmethod
    async def add_feature(group_name: str, feature_uuid: str, feature_name: str,
                           feature_version: int, priority: int = 0) -> dict[str, Any]:
        pool = await get_pool()
        group = await pool.fetchrow("SELECT uuid FROM ml.feature_groups WHERE name = $1", group_name)
        if not group:
            raise ValueError(f"Feature group not found: {group_name}")
        row = await pool.fetchrow(
            "INSERT INTO ml.feature_group_members (group_uuid, feature_uuid, feature_name, feature_version, priority) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (group_uuid, feature_uuid) DO UPDATE SET "
            "priority = $5 RETURNING *",
            group["uuid"], feature_uuid, feature_name, feature_version, priority,
        )
        return dict(row)

    @staticmethod
    async def get_group(name: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM ml.feature_groups WHERE name = $1", name)
        if not row:
            return None
        result = dict(row)
        members = await pool.fetch(
            "SELECT f.* FROM ml.feature_group_members fgm "
            "JOIN ml.feature_definitions f ON f.uuid = fgm.feature_uuid "
            "WHERE fgm.group_uuid = $1 ORDER BY fgm.priority",
            row["uuid"],
        )
        result["features"] = [dict(m) for m in members]
        return result

    @staticmethod
    async def list_groups(group_type: str | None = None) -> list[dict[str, Any]]:
        pool = await get_pool()
        if group_type:
            rows = await pool.fetch(
                "SELECT * FROM ml.feature_groups WHERE group_type = $1 AND is_active = TRUE ORDER BY name",
                group_type,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM ml.feature_groups WHERE is_active = TRUE ORDER BY name",
            )
        return [dict(r) for r in rows]

    @staticmethod
    async def remove_feature(group_name: str, feature_uuid: str) -> bool:
        pool = await get_pool()
        result = await pool.execute(
            "DELETE FROM ml.feature_group_members WHERE group_uuid = (SELECT uuid FROM ml.feature_groups WHERE name = $1) AND feature_uuid = $2",
            group_name, feature_uuid,
        )
        return "DELETE 1" in result

    @staticmethod
    async def deactivate_group(name: str) -> bool:
        pool = await get_pool()
        result = await pool.execute(
            "UPDATE ml.feature_groups SET is_active = FALSE, updated_at = NOW() WHERE name = $1", name,
        )
        return "UPDATE 1" in result
