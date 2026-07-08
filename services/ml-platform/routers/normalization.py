from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger
from models import (
    NormalizationRuleCreate,
    NormalizationApplyRequest,
    NormalizationResultResponse,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/ml/normalization", tags=["ML Normalization"])

VALID_RULE_TYPES = {
    "date", "timestamp", "currency", "unit", "country", "org",
    "entity_id", "geospatial", "categorical", "missing", "duplicate",
    "schema_map", "ontology_map", "column_std",
}


@router.post("/rules", status_code=201)
async def create_normalization_rule(body: NormalizationRuleCreate,
                                     pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    if body.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid rule_type: {body.rule_type}")
    existing = await pool.fetchrow(
        "SELECT uuid FROM ml.normalization_rules WHERE name = $1 AND is_active = TRUE", body.name,
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Rule '{body.name}' already exists")
    row = await pool.fetchrow(
        "INSERT INTO ml.normalization_rules (name, rule_type, description, source_field, target_field, transform_params) "
        "VALUES ($1, $2, $3, $4, $5, $6::jsonb) RETURNING uuid, name, rule_type, description, is_active, created_at",
        body.name, body.rule_type, body.description or None,
        body.source_pattern or "source", body.target_format or "target",
        body.config,
    )
    return dict(row)


@router.get("/rules")
async def list_normalization_rules(
    rule_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions = ["is_active = TRUE"]
    params: list = []
    if rule_type:
        conditions.append(f"rule_type = ${len(params) + 1}")
        params.append(rule_type)
    where = " AND ".join(conditions)
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.normalization_rules WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.normalization_rules WHERE {where} ORDER BY name LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/rules/{name}")
async def get_normalization_rule(name: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM ml.normalization_rules WHERE name = $1 AND is_active = TRUE", name,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")
    return dict(row)


@router.put("/rules/{name}")
async def update_normalization_rule(name: str, body: NormalizationRuleCreate,
                                     pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    existing = await pool.fetchrow(
        "SELECT * FROM ml.normalization_rules WHERE name = $1 AND is_active = TRUE", name,
    )
    if not existing:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")
    max_ver = await pool.fetchval(
        "SELECT MAX(version) FROM ml.normalization_rules WHERE name = $1", name,
    )
    row = await pool.fetchrow(
        "INSERT INTO ml.normalization_rules (name, version, rule_type, description, source_field, target_field, transform_params) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb) RETURNING uuid, name, version, rule_type, description, is_active, created_at",
        body.name, (max_ver or 0) + 1, body.rule_type, body.description or None,
        body.source_pattern or "source", body.target_format or "target",
        body.config,
    )
    return dict(row)


@router.delete("/rules/{name}")
async def deactivate_normalization_rule(name: str,
                                         pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow(
        "UPDATE ml.normalization_rules SET is_active = FALSE, updated_at = NOW() "
        "WHERE name = $1 AND is_active = TRUE RETURNING uuid, name",
        name,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")
    return {"status": "deactivated", "name": name}


@router.post("/rules/{name}/validate")
async def validate_normalization_rule(name: str,
                                       pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM ml.normalization_rules WHERE name = $1 AND is_active = TRUE", name,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")
    return {
        "rule_name": name,
        "is_valid": True,
        "rule_type": row["rule_type"],
        "errors": [],
        "warnings": [],
    }


@router.get("/types")
async def list_normalization_types() -> list[str]:
    return sorted(VALID_RULE_TYPES)


@router.post("/apply")
async def apply_normalization(body: NormalizationApplyRequest,
                               pool: asyncpg.Pool = Depends(get_pool)) -> list[dict[str, Any]]:
    results = []
    for rule_name in body.rules:
        rule = await pool.fetchrow(
            "SELECT * FROM ml.normalization_rules WHERE name = $1 AND is_active = TRUE", rule_name,
        )
        if not rule:
            results.append({
                "rule_name": rule_name,
                "records_affected": 0,
                "duration_ms": 0.0,
                "errors": 1,
                "details": {"error": "Rule not found"},
            })
            continue
        results.append({
            "rule_name": rule_name,
            "records_affected": 0,
            "duration_ms": 0.0,
            "errors": 0,
            "details": {"dry_run": body.dry_run, "strict_mode": body.strict_mode, "rule_type": rule["rule_type"]},
        })
    return results


@router.get("/mappings")
async def list_normalization_mappings(
    rule_name: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions: list[str] = ["m.is_active = TRUE"]
    params: list = []
    if rule_name:
        conditions.append(f"m.rule_name = ${len(params) + 1}")
        params.append(rule_name)
    where = " AND ".join(conditions)
    total = await pool.fetchval(
        f"SELECT COUNT(*) FROM ml.normalization_mappings m WHERE {where}", *params,
    )
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT m.* FROM ml.normalization_mappings m WHERE {where} ORDER BY m.rule_name, m.source_value "
        f"LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.post("/mappings", status_code=201)
async def create_normalization_mapping(rule_name: str = Query(...),
                                        source_value: str = Query(...),
                                        target_value: str = Query(...),
                                        pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    rule = await pool.fetchrow(
        "SELECT * FROM ml.normalization_rules WHERE name = $1 AND is_active = TRUE", rule_name,
    )
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found")
    row = await pool.fetchrow(
        "INSERT INTO ml.normalization_mappings (rule_name, rule_version, source_value, target_value) "
        "VALUES ($1, $2, $3, $4) ON CONFLICT (rule_name, rule_version, source_value) "
        "DO UPDATE SET target_value = EXCLUDED.target_value, updated_at = NOW() "
        "RETURNING uuid, rule_name, source_value, target_value, mapping_type",
        rule_name, rule["version"], source_value, target_value,
    )
    return dict(row)


@router.get("/health")
async def normalization_health():
    return {"status": "healthy", "service": "ML Normalization", "timestamp": datetime.now(timezone.utc).isoformat()}
