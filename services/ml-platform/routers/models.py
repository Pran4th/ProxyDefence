from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from models import ModelVersion, ModelTransition, PaginatedResponse
from registry.model_registry import ModelRegistry

router = APIRouter(prefix="/api/v1/ml/models", tags=["ML Models"])


@router.post("", status_code=201)
async def register_model(body: ModelVersion,
                         pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    registry = ModelRegistry()
    result = await registry.register(
        name=body.name,
        model_type=body.model_type,
        metrics=body.metrics,
        parameters=body.parameters,
        feature_version=body.feature_version,
        dataset_version=body.dataset_version,
        mlflow_run_id=body.mlflow_run_id,
        artifact_path=body.artifact_path,
        file_path=body.file_path,
        git_commit_hash=body.git_commit_hash,
        execution_time_seconds=body.execution_time_seconds,
    )
    return result


@router.get("")
async def list_models(
    name: str | None = Query(None),
    stage: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions = ["1=1"]
    params: list = []
    if name:
        conditions.append(f"name = ${len(params) + 1}")
        params.append(name)
    if stage:
        conditions.append(f"stage = ${len(params) + 1}")
        params.append(stage)
    where = " AND ".join(conditions)
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.model_versions WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.model_versions WHERE {where} ORDER BY name, version DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/{uuid}")
async def get_model(uuid: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow("SELECT * FROM ml.model_versions WHERE uuid = $1", uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    return dict(row)


@router.put("/{uuid}/stage")
async def transition_model(uuid: str, body: ModelTransition,
                           pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    registry = ModelRegistry()
    try:
        result = await registry.transition(uuid, body.stage)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.get("/{name}/production")
async def get_production_model(name: str,
                               pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    registry = ModelRegistry()
    result = await registry.get_production(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"No production model for '{name}'")
    return result
