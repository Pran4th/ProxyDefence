import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
import asyncpg

from db import get_pool
from models import ASSET_TYPE_BY_TABLE, ENERGY_JSON_COLUMNS, ENTITY_TABLE_NAMES, RELATIONSHIP_WRITABLE_COLUMNS, VALID_ASSET_TYPES

router = APIRouter(prefix="/api/v1/energy", tags=["Energy Relationships"])


@router.get("/{table}/{entity_uuid}/relationships")
async def get_entity_relationships(
    table: str,
    entity_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict[str, Any]]:
    if table not in ENTITY_TABLE_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown entity: {table}")
    asset_type = ASSET_TYPE_BY_TABLE.get(table)
    if not asset_type:
        return []

    id_sql = f"SELECT id FROM energy.{table} WHERE uuid = $1"
    row = await pool.fetchrow(id_sql, entity_uuid)
    if not row:
        raise HTTPException(status_code=404, detail=f"{table} not found")
    entity_id = row["id"]

    related = await pool.fetch(
        """
        SELECT * FROM energy.entity_relationships
        WHERE (source_entity_type = $1 AND source_entity_id = $2)
           OR (target_entity_type = $1 AND target_entity_id = $2)
        ORDER BY created_at DESC
        """,
        asset_type,
        entity_id,
    )
    return [dict(r) for r in related]


@router.post("/relationships", status_code=status.HTTP_201_CREATED)
async def create_relationship(
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    required = ["source_entity_type", "source_entity_id", "target_entity_type", "target_entity_id", "relationship_type"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=422, detail=f"Missing required field: {field}")
    invalid = sorted(set(body) - RELATIONSHIP_WRITABLE_COLUMNS)
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown or read-only fields: {', '.join(invalid)}")
    if body["source_entity_type"] not in VALID_ASSET_TYPES or body["target_entity_type"] not in VALID_ASSET_TYPES:
        raise HTTPException(status_code=422, detail="Invalid relationship asset type")
    for key in ENERGY_JSON_COLUMNS & body.keys():
        if isinstance(body[key], (dict, list)):
            body[key] = json.dumps(body[key])

    columns = ", ".join(body.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(body)))
    sql = f"INSERT INTO energy.entity_relationships ({columns}) VALUES ({placeholders}) RETURNING *"
    row = await pool.fetchrow(sql, *body.values())
    return dict(row) if row else {}


@router.get("/graph/network")
async def get_network_graph(
    pool: asyncpg.Pool = Depends(get_pool),
    limit: int = Query(500, ge=1, le=5000),
) -> dict[str, Any]:
    rows = await pool.fetch(
        "SELECT * FROM energy.entity_relationships WHERE valid_to IS NULL ORDER BY created_at DESC LIMIT $1",
        limit,
    )
    return {"relationships": [dict(r) for r in rows]}
