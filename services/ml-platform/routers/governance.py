from typing import Any

from fastapi import APIRouter, HTTPException, Query

from db import get_pool
from models import GovernanceAction, ScheduleConfig, PaginatedResponse

router = APIRouter(prefix="/api/v1/ml/governance", tags=["ML Governance"])


@router.post("/audit/{model_uuid}")
async def record_action(model_uuid: str, body: GovernanceAction) -> dict[str, Any]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT uuid FROM ml.model_versions WHERE uuid = $1", model_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Model version not found")
    result = await pool.fetchrow(
        "INSERT INTO ml.model_governance (model_version_uuid, action, actor, reason, metadata) "
        "VALUES ($1, $2, $3, $4, $5) RETURNING uuid, action, actor, created_at",
        model_uuid, body.action, body.actor, body.reason,
        body.metadata if body.metadata else {},
    )
    return dict(result)


@router.get("/audit/{model_uuid}")
async def get_audit_trail(
    model_uuid: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse:
    pool = await get_pool()
    total = await pool.fetchval(
        "SELECT COUNT(*) FROM ml.model_governance WHERE model_version_uuid = $1", model_uuid,
    )
    rows = await pool.fetch(
        "SELECT * FROM ml.model_governance WHERE model_version_uuid = $1 "
        "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        model_uuid, limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.post("/schedules")
async def create_schedule(body: ScheduleConfig) -> dict[str, Any]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO ml.training_schedules (model_name, cron_expression, config) "
        "VALUES ($1, $2, $3) RETURNING uuid, model_name, cron_expression, is_active, created_at",
        body.model_name, body.cron_expression, body.config,
    )
    return dict(row)


@router.get("/schedules")
async def list_schedules(
    model_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse:
    pool = await get_pool()
    conditions = ["1=1"]
    params: list = []
    if model_name:
        conditions.append(f"model_name = ${len(params) + 1}")
        params.append(model_name)
    where = " AND ".join(conditions)
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.training_schedules WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.training_schedules WHERE {where} ORDER BY created_at DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.put("/schedules/{uuid}/toggle")
async def toggle_schedule(uuid: str) -> dict[str, Any]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE ml.training_schedules SET is_active = NOT is_active, updated_at = NOW() "
        "WHERE uuid = $1 RETURNING *", uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return dict(row)


@router.get("/health")
async def governance_health():
    return {"status": "healthy", "service": "ML Governance"}
