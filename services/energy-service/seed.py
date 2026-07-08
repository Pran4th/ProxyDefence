import json
import os
from datetime import datetime
from pathlib import Path

import asyncpg

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

SEED_DIR = Path(__file__).parent / "seed_data"

# Maps asset_type in seed JSON to actual table name
ASSET_TYPE_TO_TABLE = {
    "port": "ports",
    "oil_field": "oil_fields",
    "gas_field": "gas_fields",
    "pipeline": "pipelines",
    "refinery": "refineries",
    "power_plant": "power_plants",
    "storage_facility": "storage_facilities",
    "strategic_petroleum_reserve": "strategic_petroleum_reserves",
    "import_corridor": "import_corridors",
    "shipping_route": "shipping_routes",
    "supplier": "suppliers",
    "location": "locations",
    "organization": "organizations",
}
TABLE_TO_ASSET_TYPE = {v: k for k, v in ASSET_TYPE_TO_TABLE.items()}

INSERT_ORDER = [
    "locations",
    "organizations",
    "commodities",
    "ports",
    "oil_fields",
    "gas_fields",
    "pipelines",
    "refineries",
    "power_plants",
    "storage_facilities",
    "strategic_petroleum_reserves",
    "import_corridors",
    "shipping_routes",
    "suppliers",
]

RELATIONS = ["relationships", "events", "capacity_history"]

SLUG_ENTITY_MAP: dict[str, dict[str, int]] = {}
UUID_MAP: dict[str, str] = {}


def _load_json(filename: str) -> list[dict]:
    path = SEED_DIR / filename
    if not path.exists():
        logger.warning("Seed file not found: %s", filename)
        return []
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        logger.warning("Seed file %s is not a list, skipping", filename)
        return []
    return data


def _slug_set(records: list[dict]) -> set[str]:
    return {r["slug"] for r in records if "slug" in r}


async def _upsert_locations(pool: asyncpg.Pool, records: list[dict]):
    for rec in records:
        parent_slug = rec.pop("parent_location_slug", None)
        parent_uuid = UUID_MAP.get(parent_slug) if parent_slug else None
        if parent_uuid:
            rec["parent_location_id"] = parent_uuid

        existing = await pool.fetchval(
            "SELECT id FROM energy.locations WHERE slug = $1", rec["slug"]
        )
        if existing:
            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(rec.keys()))
            await pool.execute(
                f"UPDATE energy.locations SET {set_clause}, version = version + 1, updated_at = NOW() WHERE id = $1",
                existing,
                *rec.values(),
            )
            row = await pool.fetchrow("SELECT id, uuid FROM energy.locations WHERE id = $1", existing)
        else:
            cols = ", ".join(rec.keys())
            ph = ", ".join(f"${i+1}" for i in range(len(rec)))
            row = await pool.fetchrow(
                f"INSERT INTO energy.locations ({cols}) VALUES ({ph}) RETURNING id, uuid",
                *rec.values(),
            )
        UUID_MAP[rec["slug"]] = str(row["uuid"])
        SLUG_ENTITY_MAP.setdefault("locations", {})[rec["slug"]] = row["id"]


async def _upsert_orgs(pool: asyncpg.Pool, records: list[dict]):
    for rec in records:
        country_slug = rec.pop("country_slug", None)
        if country_slug:
            rec["country_id"] = UUID_MAP.get(country_slug)

        existing = await pool.fetchval(
            "SELECT id FROM energy.organizations WHERE slug = $1", rec["slug"]
        )
        if existing:
            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(rec.keys()))
            await pool.execute(
                f"UPDATE energy.organizations SET {set_clause}, version = version + 1, updated_at = NOW() WHERE id = $1",
                existing,
                *rec.values(),
            )
            row = await pool.fetchrow("SELECT id, uuid FROM energy.organizations WHERE id = $1", existing)
        else:
            cols = ", ".join(rec.keys())
            ph = ", ".join(f"${i+1}" for i in range(len(rec)))
            row = await pool.fetchrow(
                f"INSERT INTO energy.organizations ({cols}) VALUES ({ph}) RETURNING id, uuid",
                *rec.values(),
            )
        UUID_MAP[rec["slug"]] = str(row["uuid"])
        SLUG_ENTITY_MAP.setdefault("organizations", {})[rec["slug"]] = row["id"]


async def _upsert_entities(pool: asyncpg.Pool, table: str, records: list[dict]):
    """Generic upsert for entities with location_slug and org_slug resolution."""
    for rec in records:
        loc_slug = rec.pop("location_slug", None)
        if loc_slug:
            rec["location_id"] = UUID_MAP.get(loc_slug)
        org_slug = rec.pop("org_slug", None)
        if org_slug:
            rec["organization_id"] = SLUG_ENTITY_MAP.get("organizations", {}).get(org_slug)
        origin_port = rec.pop("origin_port_slug", None)
        if origin_port:
            rec["origin_port_id"] = SLUG_ENTITY_MAP.get("ports", {}).get(origin_port)
        dest_port = rec.pop("destination_port_slug", None)
        if dest_port:
            rec["destination_port_id"] = SLUG_ENTITY_MAP.get("ports", {}).get(dest_port)
        origin_loc = rec.pop("origin_location_slug", None)
        if origin_loc:
            rec["origin_location_id"] = UUID_MAP.get(origin_loc)
        dest_loc = rec.pop("destination_location_slug", None)
        if dest_loc:
            rec["destination_location_id"] = UUID_MAP.get(dest_loc)

        existing = await pool.fetchval(
            f"SELECT id FROM energy.{table} WHERE slug = $1", rec["slug"]
        )
        if existing:
            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(rec.keys()))
            await pool.execute(
                f"UPDATE energy.{table} SET {set_clause}, version = version + 1, updated_at = NOW() WHERE id = $1",
                existing,
                *rec.values(),
            )
            row = await pool.fetchrow(f"SELECT id FROM energy.{table} WHERE id = $1", existing)
        else:
            cols = ", ".join(rec.keys())
            ph = ", ".join(f"${i+1}" for i in range(len(rec)))
            try:
                row = await pool.fetchrow(
                    f"INSERT INTO energy.{table} ({cols}) VALUES ({ph}) RETURNING id",
                    *rec.values(),
                )
            except Exception as e:
                logger.error("Failed to insert into %s slug=%s: %s", table, rec.get("slug"), e)
                raise
        SLUG_ENTITY_MAP.setdefault(table, {})[rec["slug"]] = row["id"]


async def _insert_relationships(pool: asyncpg.Pool, records: list[dict]):
    for rec in records:
        src_slug = rec.pop("source_entity_slug")
        src_type = rec.pop("source_entity_type")
        tgt_slug = rec.pop("target_entity_slug")
        tgt_type = rec.pop("target_entity_type")
        table_src = ASSET_TYPE_TO_TABLE.get(src_type, src_type)
        table_tgt = ASSET_TYPE_TO_TABLE.get(tgt_type, tgt_type)
        rec["source_entity_type"] = src_type
        rec["target_entity_type"] = tgt_type
        rec["source_entity_id"] = SLUG_ENTITY_MAP.get(table_src, {}).get(src_slug)
        rec["target_entity_id"] = SLUG_ENTITY_MAP.get(table_tgt, {}).get(tgt_slug)
        if not rec["source_entity_id"] or not rec["target_entity_id"]:
            logger.warning("Skipping relationship: %s (%s) -> %s (%s)", src_slug, src_type, tgt_slug, tgt_type)
            continue
        cols = ", ".join(rec.keys())
        ph = ", ".join(f"${i+1}" for i in range(len(rec)))
        try:
            await pool.execute(
                f"INSERT INTO energy.entity_relationships ({cols}) VALUES ({ph}) ON CONFLICT DO NOTHING",
                *rec.values(),
            )
        except Exception as e:
            logger.error("Failed relationship: %s", e)


async def _insert_events(pool: asyncpg.Pool, records: list[dict]):
    for rec in records:
        slug = rec.pop("entity_slug")
        etype = rec.pop("entity_type")
        table = ASSET_TYPE_TO_TABLE.get(etype, etype)
        rec["entity_type"] = etype
        rec["entity_id"] = SLUG_ENTITY_MAP.get(table, {}).get(slug)
        if not rec["entity_id"]:
            logger.warning("Skipping event for %s (%s)", slug, etype)
            continue
        for ts_field in ("occurred_at", "resolved_at"):
            if ts_field in rec and isinstance(rec[ts_field], str):
                rec[ts_field] = datetime.fromisoformat(rec[ts_field].replace("Z", "+00:00"))
        cols = ", ".join(rec.keys())
        ph = ", ".join(f"${i+1}" for i in range(len(rec)))
        try:
            await pool.execute(
                f"INSERT INTO energy.infrastructure_events ({cols}) VALUES ({ph}) ON CONFLICT DO NOTHING",
                *rec.values(),
            )
        except Exception as e:
            logger.error("Failed event: %s", e)


async def _insert_capacity(pool: asyncpg.Pool, records: list[dict]):
    for rec in records:
        slug = rec.pop("entity_slug")
        etype = rec.pop("entity_type")
        table = ASSET_TYPE_TO_TABLE.get(etype, etype)
        rec["entity_type"] = etype
        rec["entity_id"] = SLUG_ENTITY_MAP.get(table, {}).get(slug)
        if not rec["entity_id"]:
            logger.warning("Skipping capacity for %s (%s)", slug, etype)
            continue
        if "recorded_at" in rec and isinstance(rec["recorded_at"], str):
            rec["recorded_at"] = datetime.fromisoformat(rec["recorded_at"].replace("Z", "+00:00"))
        cols = ", ".join(rec.keys())
        ph = ", ".join(f"${i+1}" for i in range(len(rec)))
        try:
            await pool.execute(
                f"INSERT INTO energy.capacity_history ({cols}) VALUES ({ph}) ON CONFLICT DO NOTHING",
                *rec.values(),
            )
        except Exception as e:
            logger.error("Failed capacity: %s", e)


async def load_seed_data(pool: asyncpg.Pool):
    """Idempotent seed data loader. Safe to re-run."""
    if os.getenv("ENERGY_LOAD_SEED") != "1":
        logger.info("ENERGY_LOAD_SEED not set, skipping seed data")
        return

    logger.info("Loading energy seed data...")

    for table in INSERT_ORDER:
        records = _load_json(f"{table}.json")
        if not records:
            continue
        if table == "locations":
            await _upsert_locations(pool, records)
        elif table == "organizations":
            await _upsert_orgs(pool, records)
        else:
            await _upsert_entities(pool, table, records)
        logger.info("  Seeded %s: %d records", table, len(records))

    for rel_file in RELATIONS:
        records = _load_json(f"{rel_file}.json")
        if not records:
            continue
        if rel_file == "relationships":
            await _insert_relationships(pool, records)
        elif rel_file == "events":
            await _insert_events(pool, records)
        elif rel_file == "capacity_history":
            await _insert_capacity(pool, records)
        logger.info("  Seeded %s: %d records", rel_file, len(records))

    logger.info("Seed data complete.")
