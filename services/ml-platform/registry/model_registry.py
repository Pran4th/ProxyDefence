import json
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)

VALID_STAGES = ["development", "validation", "staging", "production", "archived"]
VALID_TRANSITIONS = {
    "development": ["validation", "archived"],
    "validation": ["staging", "development", "archived"],
    "staging": ["production", "validation", "archived"],
    "production": ["staging", "archived"],
    "archived": [],
}


class ModelRegistry:
    async def _pool(self) -> asyncpg.Pool:
        return await get_pool()

    async def register(self, name: str, model_type: str, **metadata) -> dict[str, Any]:
        pool = await get_pool()
        existing = await pool.fetchval(
            "SELECT MAX(version) FROM ml.model_versions WHERE name = $1", name
        )
        version = (existing or 0) + 1

        row = await pool.fetchrow(
            "INSERT INTO ml.model_versions (name, version, model_type, stage, metrics, parameters, "
            "feature_version, dataset_version, mlflow_run_id, artifact_path, file_path, "
            "git_commit_hash, execution_time_seconds) "
            "VALUES ($1, $2, $3, 'development', $4, $5, $6, $7, $8, $9, $10, $11, $12) "
            "RETURNING uuid, name, version, model_type, stage, created_at",
            name, version, model_type,
            json.dumps(metadata.get("metrics", {})),
            json.dumps(metadata.get("parameters", {})),
            metadata.get("feature_version"),
            metadata.get("dataset_version"),
            metadata.get("mlflow_run_id"),
            metadata.get("artifact_path"),
            metadata.get("file_path"),
            metadata.get("git_commit_hash"),
            metadata.get("execution_time_seconds"),
        )
        logger.info("model registered", name=name, version=version)
        return dict(row)

    async def transition(self, uuid: str, new_stage: str) -> dict[str, Any] | None:
        pool = await get_pool()
        if new_stage not in VALID_STAGES:
            raise ValueError(f"Invalid stage: {new_stage}. Valid: {VALID_STAGES}")

        current = await pool.fetchrow("SELECT * FROM ml.model_versions WHERE uuid = $1", uuid)
        if not current:
            return None

        allowed = VALID_TRANSITIONS.get(current["stage"], [])
        if new_stage not in allowed:
            raise ValueError(
                f"Cannot transition from '{current['stage']}' to '{new_stage}'. "
                f"Allowed: {allowed}"
            )

        if new_stage == "production":
            await pool.execute(
                "UPDATE ml.model_versions SET stage = 'staging' "
                "WHERE name = $1 AND stage = 'production' AND uuid != $2",
                current["name"], uuid,
            )

        row = await pool.fetchrow(
            "UPDATE ml.model_versions SET stage = $1, updated_at = NOW() "
            "WHERE uuid = $2 RETURNING *",
            new_stage, uuid,
        )
        logger.info("model transitioned", name=current["name"], stage=new_stage)
        return dict(row)

    async def get(self, uuid: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM ml.model_versions WHERE uuid = $1", uuid)
        return dict(row) if row else None

    async def list(self, name: str | None = None, stage: str | None = None,
                   limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        pool = await get_pool()
        conditions = ["1=1"]
        params: list = []
        if name:
            conditions.append(f"name = ${len(params) + 1}")
            params.append(name)
        if stage:
            conditions.append(f"stage = ${len(params) + 1}")
            params.append(stage)
        where = " AND ".join(conditions)
        count = await pool.fetchval(f"SELECT COUNT(*) FROM ml.model_versions WHERE {where}", *params)
        params.append(limit)
        params.append(offset)
        rows = await pool.fetch(
            f"SELECT * FROM ml.model_versions WHERE {where} ORDER BY name, version DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
            *params,
        )
        return [dict(r) for r in rows], count or 0

    async def get_production(self, name: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.model_versions WHERE name = $1 AND stage = 'production' "
            "ORDER BY version DESC LIMIT 1",
            name,
        )
        return dict(row) if row else None

    async def get_latest(self, name: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.model_versions WHERE name = $1 ORDER BY version DESC LIMIT 1",
            name,
        )
        return dict(row) if row else None
