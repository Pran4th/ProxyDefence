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


_TABLE_BY_ASSET_TYPE = {v: k for k, v in ASSET_TYPE_BY_TABLE.items()}
# Tables with a location_id UUID FK to energy.locations (same pattern used by
# digital_twin/graph.py's _get_node_location) -- resolving through it gives a
# real country name instead of the opaque "refinery:5" style label the graph
# previously had no choice but to render.
_LOCATION_RESOLVABLE_TABLES = {
    "ports", "oil_fields", "gas_fields", "pipelines", "refineries",
    "power_plants", "storage_facilities", "strategic_petroleum_reserves", "suppliers",
}


async def _resolve_entity_names(
    pool: asyncpg.Pool, entity_refs: set[tuple[str, int]]
) -> dict[tuple[str, int], dict[str, Any]]:
    """Batch-resolve (asset_type, id) pairs to a real name + country. entity_relationships
    only stores type/id pairs, no name or location -- this is the only way to get either."""
    by_table: dict[str, list[int]] = {}
    for asset_type, entity_id in entity_refs:
        table = _TABLE_BY_ASSET_TYPE.get(asset_type)
        if table:
            by_table.setdefault(table, []).append(entity_id)

    result: dict[tuple[str, int], dict[str, Any]] = {}
    for table, ids in by_table.items():
        asset_type = ASSET_TYPE_BY_TABLE[table]
        if table == "locations":
            rows = await pool.fetch(
                "SELECT id, name FROM energy.locations WHERE id = ANY($1::bigint[])", ids
            )
            for r in rows:
                result[(asset_type, r["id"])] = {"name": r["name"], "country": r["name"]}
        elif table == "organizations":
            # organizations.country_id is a UUID FK to energy.locations.uuid
            # (not locations.id -- confirmed against the live schema).
            rows = await pool.fetch(
                """SELECT o.id, o.name, l.name AS country
                   FROM energy.organizations o
                   LEFT JOIN energy.locations l ON l.uuid = o.country_id
                   WHERE o.id = ANY($1::bigint[])""",
                ids,
            )
            for r in rows:
                result[(asset_type, r["id"])] = {"name": r["name"], "country": r["country"]}
        elif table in _LOCATION_RESOLVABLE_TABLES:
            rows = await pool.fetch(
                f"""SELECT t.id, t.name, l.name AS country
                    FROM energy.{table} t
                    LEFT JOIN energy.locations l ON l.uuid = t.location_id
                    WHERE t.id = ANY($1::bigint[])""",
                ids,
            )
            for r in rows:
                result[(asset_type, r["id"])] = {"name": r["name"], "country": r["country"]}
        else:
            rows = await pool.fetch(
                f"SELECT id, name FROM energy.{table} WHERE id = ANY($1::bigint[])", ids
            )
            for r in rows:
                result[(asset_type, r["id"])] = {"name": r["name"], "country": None}
    return result


@router.get("/graph/network")
async def get_network_graph(
    pool: asyncpg.Pool = Depends(get_pool),
    limit: int = Query(500, ge=1, le=5000),
) -> dict[str, Any]:
    rows = await pool.fetch(
        "SELECT * FROM energy.entity_relationships WHERE valid_to IS NULL ORDER BY created_at DESC LIMIT $1",
        limit,
    )

    refs: set[tuple[str, int]] = set()
    for r in rows:
        refs.add((r["source_entity_type"], r["source_entity_id"]))
        refs.add((r["target_entity_type"], r["target_entity_id"]))
    names = await _resolve_entity_names(pool, refs) if refs else {}

    relationships = []
    for r in rows:
        d = dict(r)
        src = names.get((r["source_entity_type"], r["source_entity_id"]), {})
        tgt = names.get((r["target_entity_type"], r["target_entity_id"]), {})
        d["source_name"] = src.get("name")
        d["source_country"] = src.get("country")
        d["target_name"] = tgt.get("name")
        d["target_country"] = tgt.get("country")
        relationships.append(d)

    return {"relationships": relationships}
