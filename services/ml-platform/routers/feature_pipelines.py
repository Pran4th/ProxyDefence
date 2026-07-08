from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger
from models import (
    FeaturePipelineDefinitionCreate,
    FeaturePipelineRunResponse,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/ml/features/pipelines", tags=["ML Feature Pipelines"])


@router.post("", status_code=201)
async def define_feature_pipeline(body: FeaturePipelineDefinitionCreate,
                                   pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    existing = await pool.fetchrow(
        "SELECT uuid FROM ml.feature_pipelines WHERE name = $1 AND is_active = TRUE", body.name,
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Feature pipeline '{body.name}' already exists")
    row = await pool.fetchrow(
        "INSERT INTO ml.feature_pipelines (name, description, pipeline_type, transform_steps, metadata) "
        "VALUES ($1, $2, 'standard', $3::jsonb, $4::jsonb) RETURNING uuid, name, description, version, is_active, created_at",
        body.name, body.description or None,
        body.steps,
        {"input_columns": body.input_columns, "output_columns": body.output_columns, "tags": body.tags},
    )
    return dict(row)


@router.get("")
async def list_feature_pipelines(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    total = await pool.fetchval("SELECT COUNT(*) FROM ml.feature_pipelines WHERE is_active = TRUE")
    rows = await pool.fetch(
        "SELECT * FROM ml.feature_pipelines WHERE is_active = TRUE ORDER BY name LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/{name}")
async def get_feature_pipeline(name: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM ml.feature_pipelines WHERE name = $1 AND is_active = TRUE", name,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Feature pipeline '{name}' not found")
    return dict(row)


@router.get("/{name}/versions/{version}")
async def get_feature_pipeline_version(name: str, version: int,
                                        pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM ml.feature_pipelines WHERE name = $1 AND version = $2", name, version,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Feature pipeline '{name}' version {version} not found")
    return dict(row)


@router.post("/{name}/execute")
async def execute_feature_pipeline(name: str,
                                    pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    pipeline = await pool.fetchrow(
        "SELECT * FROM ml.feature_pipelines WHERE name = $1 AND is_active = TRUE", name,
    )
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Feature pipeline '{name}' not found")
    run = await pool.fetchrow(
        "INSERT INTO ml.feature_pipeline_runs (pipeline_name, pipeline_version, run_status, trigger_type) "
        "VALUES ($1, $2, 'running', 'manual') RETURNING uuid, pipeline_name, pipeline_version, run_status, created_at",
        pipeline["name"], pipeline["version"],
    )
    return dict(run)


@router.post("/{name}/execute/incremental")
async def execute_incremental_feature_pipeline(name: str,
                                                pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    pipeline = await pool.fetchrow(
        "SELECT * FROM ml.feature_pipelines WHERE name = $1 AND is_active = TRUE", name,
    )
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Feature pipeline '{name}' not found")
    run = await pool.fetchrow(
        "INSERT INTO ml.feature_pipeline_runs (pipeline_name, pipeline_version, run_status, trigger_type) "
        "VALUES ($1, $2, 'running', 'incremental') RETURNING uuid, pipeline_name, pipeline_version, run_status, created_at",
        pipeline["name"], pipeline["version"],
    )
    return dict(run)


@router.get("/{name}/runs")
async def list_feature_pipeline_runs(
    name: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    pipeline = await pool.fetchrow(
        "SELECT uuid FROM ml.feature_pipelines WHERE name = $1 AND is_active = TRUE", name,
    )
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Feature pipeline '{name}' not found")
    total = await pool.fetchval(
        "SELECT COUNT(*) FROM ml.feature_pipeline_runs WHERE pipeline_name = $1", name,
    )
    rows = await pool.fetch(
        "SELECT * FROM ml.feature_pipeline_runs WHERE pipeline_name = $1 "
        "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        name, limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/runs/{uuid}")
async def get_feature_pipeline_run(uuid: str,
                                    pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow("SELECT * FROM ml.feature_pipeline_runs WHERE uuid = $1", uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Feature pipeline run not found")
    return dict(row)


@router.get("/health")
async def feature_pipelines_health():
    return {"status": "healthy", "service": "ML Feature Pipelines", "timestamp": datetime.now(timezone.utc).isoformat()}
