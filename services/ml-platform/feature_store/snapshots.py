import json
from datetime import datetime, timezone
from typing import Any

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)


class FeatureSnapshots:
    @staticmethod
    async def create_snapshot(feature_version: int, entity_type: str, entity_id: str,
                               snapshot_data: dict[str, Any],
                               snapshot_label: str | None = None,
                               snapshot_type: str = "scheduled") -> dict[str, Any]:
        pool = await get_pool()
        row = await pool.fetchrow(
            "INSERT INTO ml.feature_snapshots (feature_version, entity_type, entity_id, "
            "snapshot_data, snapshot_label, snapshot_type) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            feature_version, entity_type, entity_id,
            json.dumps(snapshot_data), snapshot_label, snapshot_type,
        )
        logger.debug("feature snapshot created for %s/%s", entity_type, entity_id)
        return dict(row)

    @staticmethod
    async def get_snapshots(entity_type: str, entity_id: str,
                             feature_version: int | None = None,
                             limit: int = 50) -> list[dict[str, Any]]:
        pool = await get_pool()
        if feature_version:
            rows = await pool.fetch(
                "SELECT * FROM ml.feature_snapshots WHERE entity_type = $1 AND entity_id = $2 "
                "AND feature_version = $3 ORDER BY created_at DESC LIMIT $4",
                entity_type, entity_id, feature_version, limit,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM ml.feature_snapshots WHERE entity_type = $1 AND entity_id = $2 "
                "ORDER BY created_at DESC LIMIT $3",
                entity_type, entity_id, limit,
            )
        return [dict(r) for r in rows]

    @staticmethod
    async def get_snapshot_by_uuid(uuid: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM ml.feature_snapshots WHERE uuid = $1", uuid)
        return dict(row) if row else None

    @staticmethod
    async def get_latest(entity_type: str, entity_id: str,
                          feature_version: int | None = None) -> dict[str, Any] | None:
        pool = await get_pool()
        if feature_version:
            row = await pool.fetchrow(
                "SELECT * FROM ml.feature_snapshots WHERE entity_type = $1 AND entity_id = $2 "
                "AND feature_version = $3 ORDER BY created_at DESC LIMIT 1",
                entity_type, entity_id, feature_version,
            )
        else:
            row = await pool.fetchrow(
                "SELECT * FROM ml.feature_snapshots WHERE entity_type = $1 AND entity_id = $2 "
                "ORDER BY created_at DESC LIMIT 1",
                entity_type, entity_id,
            )
        return dict(row) if row else None

    @staticmethod
    async def diff(uuid_a: str, uuid_b: str) -> dict[str, Any]:
        pool = await get_pool()
        a = await pool.fetchrow("SELECT * FROM ml.feature_snapshots WHERE uuid = $1", uuid_a)
        b = await pool.fetchrow("SELECT * FROM ml.feature_snapshots WHERE uuid = $1", uuid_b)
        if not a or not b:
            raise ValueError("Both snapshots must exist")

        data_a = json.loads(a["snapshot_data"]) if isinstance(a["snapshot_data"], str) else a["snapshot_data"]
        data_b = json.loads(b["snapshot_data"]) if isinstance(b["snapshot_data"], str) else b["snapshot_data"]

        all_keys = set(data_a.keys()) | set(data_b.keys())
        changes = {}
        for k in all_keys:
            va = data_a.get(k)
            vb = data_b.get(k)
            if va != vb:
                changes[k] = {"from": va, "to": vb}

        return {
            "snapshot_a": {"uuid": uuid_a, "created_at": a["created_at"]},
            "snapshot_b": {"uuid": uuid_b, "created_at": b["created_at"]},
            "changed_features": len(changes),
            "changes": changes,
        }
