import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from db import get_pool
from filters import FilterParams
from models import CATALOG_JSON_COLUMNS, CATALOG_WRITABLE_COLUMNS, ENTITY_TABLE_NAMES, PaginatedResponse

router = APIRouter(prefix="/api/v1/energy", tags=["Energy Catalog"])


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    d = dict(row)
    for key in CATALOG_JSON_COLUMNS & d.keys():
        if isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                pass
    d.pop("id", None)
    return {"id": row["id"], **d}


def _safe_table(table: str) -> str:
    if table not in ENTITY_TABLE_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown entity: {table}")
    return f"energy.{table}"


def _validate_body_columns(body: dict[str, Any]) -> None:
    invalid = sorted(set(body) - CATALOG_WRITABLE_COLUMNS)
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown or read-only fields: {', '.join(invalid)}")


def _prepare_body(body: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(body)
    for key in CATALOG_JSON_COLUMNS & prepared.keys():
        if isinstance(prepared[key], (dict, list)):
            prepared[key] = json.dumps(prepared[key])
    return prepared


@router.get("/{table}")
async def list_entities(
    table: str,
    filters: FilterParams = Depends(),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    t = _safe_table(table)
    where, params = filters.build_where_clause(table)
    order = filters.build_order_clause(table)

    count_sql = f"SELECT COUNT(*) FROM {t} WHERE {where}"
    total = await pool.fetchval(count_sql, *params)

    params.append(filters.limit)
    params.append(filters.offset)
    data_sql = f"SELECT * FROM {t} WHERE {where} ORDER BY {order} LIMIT ${len(params)-1} OFFSET ${len(params)}"
    rows = await pool.fetch(data_sql, *params)

    return PaginatedResponse(
        items=[_row_to_dict(r) for r in rows],
        total=total or 0,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.get("/{table}/{entity_uuid}")
async def get_entity(
    table: str,
    entity_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    t = _safe_table(table)
    sql = f"SELECT * FROM {t} WHERE uuid = $1"
    row = await pool.fetchrow(sql, entity_uuid)
    if not row:
        raise HTTPException(status_code=404, detail=f"{table} not found")
    return _row_to_dict(row)


@router.post("/{table}", status_code=status.HTTP_201_CREATED)
async def create_entity(
    table: str,
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    t = _safe_table(table)
    _validate_body_columns(body)
    if not body:
        raise HTTPException(status_code=400, detail="No fields to insert")
    body = _prepare_body(body)
    columns = ", ".join(body.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(body)))
    returning = ["id", "uuid"] + list(body.keys())
    returning_str = ", ".join(returning)
    sql = f"INSERT INTO {t} ({columns}) VALUES ({placeholders}) RETURNING {returning_str}"
    row = await pool.fetchrow(sql, *body.values())
    if not row:
        raise HTTPException(status_code=500, detail="Insert failed")
    return _row_to_dict(row)


@router.put("/{table}/{entity_uuid}")
async def update_entity(
    table: str,
    entity_uuid: str,
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    t = _safe_table(table)
    _validate_body_columns(body)
    if not body:
        raise HTTPException(status_code=400, detail="No fields to update")
    body = _prepare_body(body)
    body["updated_by"] = body.get("updated_by", "api")
    set_clause = ", ".join(
        f"{k} = ${i+2}" for i, k in enumerate(body.keys())
    )
    sql = f"UPDATE {t} SET {set_clause}, version = version + 1, updated_at = NOW() WHERE uuid = $1 RETURNING *"
    row = await pool.fetchrow(sql, entity_uuid, *body.values())
    if not row:
        raise HTTPException(status_code=404, detail=f"{table} not found")
    return _row_to_dict(row)


@router.patch("/{table}/{entity_uuid}")
async def patch_entity(
    table: str,
    entity_uuid: str,
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    t = _safe_table(table)
    if not body:
        raise HTTPException(status_code=400, detail="No fields to update")
    _validate_body_columns(body)
    body = _prepare_body(body)
    body["updated_by"] = body.get("updated_by", "api")
    set_clause = ", ".join(
        f"{k} = ${i+2}" for i, k in enumerate(body.keys())
    )
    sql = f"UPDATE {t} SET {set_clause}, version = version + 1, updated_at = NOW() WHERE uuid = $1 RETURNING *"
    row = await pool.fetchrow(sql, entity_uuid, *body.values())
    if not row:
        raise HTTPException(status_code=404, detail=f"{table} not found")
    return _row_to_dict(row)


@router.delete("/{table}/{entity_uuid}")
async def soft_delete_entity(
    table: str,
    entity_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    t = _safe_table(table)
    sql = f"UPDATE {t} SET is_deleted = TRUE, deleted_at = NOW(), deleted_by = $2 WHERE uuid = $1 RETURNING id, uuid, is_deleted, deleted_at"
    row = await pool.fetchrow(sql, entity_uuid, "api")
    if not row:
        raise HTTPException(status_code=404, detail=f"{table} not found")
    return dict(row)
