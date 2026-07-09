import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
import asyncpg

from db import get_pool
from models import CATALOG_JSON_COLUMNS, CATALOG_WRITABLE_COLUMNS, ENTITY_TABLE_NAMES, BulkImportResult
from parsers.json_parser import JsonParser
from parsers.csv_parser import CsvParser
from parsers.geojson_parser import GeoJsonParser

router = APIRouter(prefix="/api/v1/energy", tags=["Energy Bulk"])

PARSERS = {
    "json": JsonParser,
    "csv": CsvParser,
    "geojson": GeoJsonParser,
}


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    item = dict(row)
    for key in CATALOG_JSON_COLUMNS & item.keys():
        if isinstance(item[key], str):
            try:
                item[key] = json.loads(item[key])
            except json.JSONDecodeError:
                pass
    return item


def _detect_format(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "json"
    if ext in ("json", "geojson"):
        return ext
    return ext


@router.post("/bulk/import")
async def bulk_import(
    file: UploadFile = File(...),
    pool: asyncpg.Pool = Depends(get_pool),
) -> BulkImportResult:
    content = await file.read()
    text = content.decode("utf-8")
    fmt = _detect_format(file.filename or "data.json")

    parser_cls = PARSERS.get(fmt)
    if not parser_cls:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    try:
        records = parser_cls().parse(text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not records:
        return BulkImportResult(created=0, updated=0)

    table = records[0].get("_table")
    if not table or table not in ENTITY_TABLE_NAMES:
        raise HTTPException(status_code=400, detail="Each record must include '_table' field with a valid entity type")

    created = 0
    updated = 0
    errors: list[str] = []

    for i, record in enumerate(records):
        try:
            _table = record.pop("_table", table)
            if _table not in ENTITY_TABLE_NAMES:
                raise ValueError(f"Unknown entity type in record '_table': {_table}")
            invalid = sorted(set(record) - CATALOG_WRITABLE_COLUMNS)
            if invalid:
                raise ValueError(f"Unknown or read-only fields: {', '.join(invalid)}")
            t = f"energy.{_table}"
            record["updated_by"] = "bulk_import"
            for key in CATALOG_JSON_COLUMNS & record.keys():
                if isinstance(record[key], (dict, list)):
                    record[key] = json.dumps(record[key])
            slug = record.get("slug", record.get("name", f"import-{i}")).lower().replace(" ", "-")

            existing = await pool.fetchrow(
                f"SELECT id FROM {t} WHERE slug = $1",
                slug,
            )
            if existing:
                set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(record.keys()))
                sql = f"UPDATE {t} SET {set_clause}, version = version + 1, updated_at = NOW() WHERE id = $1"
                await pool.execute(sql, existing["id"], *record.values())
                updated += 1
            else:
                record["slug"] = slug
                columns = ", ".join(record.keys())
                placeholders = ", ".join(f"${i+1}" for i in range(len(record)))
                sql = f"INSERT INTO {t} ({columns}) VALUES ({placeholders})"
                await pool.execute(sql, *record.values())
                created += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    return BulkImportResult(created=created, updated=updated, errors=errors)


@router.get("/bulk/export")
async def bulk_export(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    result = {}
    for table in ENTITY_TABLE_NAMES:
        rows = await pool.fetch(
            f"SELECT * FROM energy.{table} WHERE is_deleted = FALSE ORDER BY name"
        )
        result[table] = [_row_to_dict(r) for r in rows]
    return result
