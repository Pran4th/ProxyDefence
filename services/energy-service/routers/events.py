import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from db import get_pool
from models import ASSET_TYPE_BY_TABLE, ENERGY_JSON_COLUMNS, ENTITY_TABLE_NAMES, EVENT_WRITABLE_COLUMNS, VALID_ASSET_TYPES

router = APIRouter(prefix="/api/v1/energy", tags=["Energy Events"])


@router.get("/{table}/{entity_uuid}/events")
async def get_entity_events(
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

    events = await pool.fetch(
        "SELECT * FROM energy.infrastructure_events WHERE entity_type = $1 AND entity_id = $2 ORDER BY occurred_at DESC",
        asset_type,
        row["id"],
    )
    return [dict(e) for e in events]


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def create_event(
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    required = ["entity_type", "entity_id", "event_type"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=422, detail=f"Missing required field: {field}")
    invalid = sorted(set(body) - EVENT_WRITABLE_COLUMNS)
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown or read-only fields: {', '.join(invalid)}")
    if body["entity_type"] not in VALID_ASSET_TYPES:
        raise HTTPException(status_code=422, detail="Invalid event asset type")
    for key in ENERGY_JSON_COLUMNS & body.keys():
        if isinstance(body[key], (dict, list)):
            body[key] = json.dumps(body[key])

    columns = ", ".join(body.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(body)))
    sql = f"INSERT INTO energy.infrastructure_events ({columns}) VALUES ({placeholders}) RETURNING *"
    row = await pool.fetchrow(sql, *body.values())
    return dict(row) if row else {}
