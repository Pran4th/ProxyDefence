import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from models import FeatureDef, FeatureDefCreate, PaginatedResponse

router = APIRouter(prefix="/api/v1/ml/features", tags=["ML Features"])


@router.post("")
async def create_feature(body: FeatureDefCreate,
                         pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    valid_types = {"numerical", "categorical", "boolean", "timestamp", "geospatial",
                   "entity_statistics", "relationship_statistics", "historical_capacity",
                   "infrastructure", "embedding_reference", "graph_placeholder"}
    if body.feature_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"Invalid feature_type: {body.feature_type}")
    row = await pool.fetchrow(
        "INSERT INTO ml.feature_definitions (name, version, feature_type, description, transform_config, source_feature) "
        "VALUES ($1, 1, $2, $3, $4, $5) RETURNING uuid, name, version, feature_type, description, created_at",
        body.name, body.feature_type, body.description,
        json.dumps(body.transform_config) if body.transform_config else '{}',
        body.source_feature,
    )
    return dict(row)


@router.get("")
async def list_features(
    feature_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions = ["is_active = TRUE"]
    params: list = []
    if feature_type:
        conditions.append(f"feature_type = ${len(params) + 1}")
        params.append(feature_type)
    where = " AND ".join(conditions)
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.feature_definitions WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.feature_definitions WHERE {where} ORDER BY name, version DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/{uuid}")
async def get_feature(uuid: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow("SELECT * FROM ml.feature_definitions WHERE uuid = $1", uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Feature not found")
    return dict(row)


@router.post("/{uuid}/versions")
async def create_feature_version(uuid: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    existing = await pool.fetchrow("SELECT * FROM ml.feature_definitions WHERE uuid = $1", uuid)
    if not existing:
        raise HTTPException(status_code=404, detail="Feature not found")
    max_ver = await pool.fetchval("SELECT MAX(version) FROM ml.feature_definitions WHERE name = $1", existing["name"])
    new_ver = (max_ver or 0) + 1
    row = await pool.fetchrow(
        "INSERT INTO ml.feature_definitions (name, version, feature_type, description, transform_config, source_feature) "
        "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
        existing["name"], new_ver, existing["feature_type"], existing["description"],
        json.dumps(existing["transform_config"]) if existing["transform_config"] else '{}',
        existing["source_feature"],
    )
    return dict(row) if row else {}
