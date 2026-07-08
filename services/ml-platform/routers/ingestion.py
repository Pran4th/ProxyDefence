from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger
from models import (
    IngestionPipelineCreate,
    IngestionPipelineResponse,
    IngestionJobResponse,
    IngestionExecuteRequest,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/ml/ingestion", tags=["ML Ingestion"])


@router.post("/pipelines", status_code=201)
async def create_ingestion_pipeline(body: IngestionPipelineCreate,
                                     pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    existing = await pool.fetchrow(
        "SELECT uuid FROM ml.ingestion_pipelines WHERE name = $1 AND is_active = TRUE", body.name,
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Pipeline '{body.name}' already exists")
    row = await pool.fetchrow(
        "INSERT INTO ml.ingestion_pipelines (name, connector_name, pipeline_type, schedule_cron, transform_pipeline, is_active) "
        "VALUES ($1, $2, 'standard', $3, $4::jsonb, TRUE) RETURNING uuid, name, connector_name, schedule_cron, is_active, created_at",
        body.name, body.connector_name, body.schedule_expr, body.steps,
    )
    return dict(row)


@router.get("/pipelines")
async def list_ingestion_pipelines(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    total = await pool.fetchval("SELECT COUNT(*) FROM ml.ingestion_pipelines WHERE is_active = TRUE")
    rows = await pool.fetch(
        "SELECT * FROM ml.ingestion_pipelines WHERE is_active = TRUE ORDER BY name LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/pipelines/{uuid}")
async def get_ingestion_pipeline(uuid: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow("SELECT * FROM ml.ingestion_pipelines WHERE uuid = $1", uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return dict(row)


@router.post("/pipelines/{uuid}/execute")
async def execute_ingestion_pipeline(uuid: str, body: IngestionExecuteRequest,
                                      pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    pipeline = await pool.fetchrow("SELECT * FROM ml.ingestion_pipelines WHERE uuid = $1", uuid)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    job = await pool.fetchrow(
        "INSERT INTO ml.ingestion_jobs (pipeline_name, pipeline_version, job_status, trigger_type, config_override) "
        "VALUES ($1, $2, 'running', 'manual', $3::jsonb) RETURNING uuid, pipeline_name, job_status, created_at",
        pipeline["name"], pipeline["version"], body.params,
    )
    return dict(job)


@router.get("/jobs")
async def list_ingestion_jobs(
    status: str | None = Query(None),
    pipeline_name: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions: list[str] = []
    params: list = []
    if status:
        conditions.append(f"job_status = ${len(params) + 1}")
        params.append(status)
    if pipeline_name:
        conditions.append(f"pipeline_name = ${len(params) + 1}")
        params.append(pipeline_name)
    where = " AND ".join(conditions) if conditions else "TRUE"
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.ingestion_jobs WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.ingestion_jobs WHERE {where} ORDER BY created_at DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/jobs/{uuid}")
async def get_ingestion_job(uuid: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow("SELECT * FROM ml.ingestion_jobs WHERE uuid = $1", uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@router.get("/errors")
async def list_ingestion_errors(
    pipeline_name: str | None = Query(None),
    error_type: str | None = Query(None),
    unresolved: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions: list[str] = []
    params: list = []
    if pipeline_name:
        conditions.append(f"pipeline_name = ${len(params) + 1}")
        params.append(pipeline_name)
    if error_type:
        conditions.append(f"error_type = ${len(params) + 1}")
        params.append(error_type)
    if unresolved:
        conditions.append("is_resolved = FALSE")
    where = " AND ".join(conditions) if conditions else "TRUE"
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.ingestion_errors WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.ingestion_errors WHERE {where} ORDER BY created_at DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.post("/schedules", status_code=201)
async def create_ingestion_schedule(pipeline_name: str = Query(...),
                                     schedule_expr: str = Query(...),
                                     pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    pipeline = await pool.fetchrow(
        "SELECT * FROM ml.ingestion_pipelines WHERE name = $1 AND is_active = TRUE", pipeline_name,
    )
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_name}' not found")
    row = await pool.fetchrow(
        "UPDATE ml.ingestion_pipelines SET schedule_cron = $1, updated_at = NOW() "
        "WHERE uuid = $2 RETURNING uuid, name, schedule_cron",
        schedule_expr, pipeline["uuid"],
    )
    return dict(row)


@router.get("/schedules")
async def list_ingestion_schedules(
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        "SELECT uuid, name, schedule_cron, is_active FROM ml.ingestion_pipelines "
        "WHERE schedule_cron IS NOT NULL AND schedule_cron != '' ORDER BY name",
    )
    return [dict(r) for r in rows]


@router.get("/health")
async def ingestion_health():
    return {"status": "healthy", "service": "ML Ingestion", "timestamp": datetime.now(timezone.utc).isoformat()}
