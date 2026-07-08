from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger
from models import (
    ConnectorConfigRequest,
    ConnectorFetchRequest,
    ConnectorSchemaResponse,
    ConnectorValidationResponse,
    ConnectorListResponse,
    ConnectorCheckpointResponse,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/ml/connectors", tags=["ML Connectors"])

VALID_CONNECTOR_TYPES = {
    "rest_api", "csv", "excel", "json", "parquet", "geojson",
    "sql", "postgresql", "elasticsearch", "kafka", "s3", "ftp",
    "http_archive", "zip", "tar", "gzip",
}


@router.post("/register", status_code=201)
async def register_connector(body: ConnectorConfigRequest,
                             pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    if body.connector_type not in VALID_CONNECTOR_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid connector_type: {body.connector_type}")
    existing = await pool.fetchrow(
        "SELECT uuid FROM ml.connector_definitions WHERE name = $1 AND is_active = TRUE",
        body.name,
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Connector '{body.name}' already exists")
    row = await pool.fetchrow(
        "INSERT INTO ml.connector_definitions (name, connector_type, description, config_schema, metadata) "
        "VALUES ($1, $2, $3, $4::jsonb, $5::jsonb) RETURNING uuid, name, connector_type, description, created_at",
        body.name, body.connector_type, body.description or None,
        body.config or {}, {**body.auth_config, **body.rate_limit_config, **body.retry_config},
    )
    return dict(row)


@router.get("")
async def list_connectors(
    connector_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions = ["is_active = TRUE"]
    params: list = []
    if connector_type:
        conditions.append(f"connector_type = ${len(params) + 1}")
        params.append(connector_type)
    where = " AND ".join(conditions)
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.connector_definitions WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.connector_definitions WHERE {where} ORDER BY name LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/{name}")
async def get_connector(name: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM ml.connector_definitions WHERE name = $1 AND is_active = TRUE", name,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")
    return dict(row)


@router.post("/{name}/discover-schema")
async def discover_schema(name: str, pool: asyncpg.Pool = Depends(get_pool)) -> ConnectorSchemaResponse:
    conn = await pool.fetchrow(
        "SELECT * FROM ml.connector_definitions WHERE name = $1 AND is_active = TRUE", name,
    )
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")
    schemas = await pool.fetch(
        "SELECT * FROM ml.connector_schemas WHERE connector_name = $1 AND is_active = TRUE", name,
    )
    columns = []
    for s in schemas:
        fields = s.get("fields_json") or []
        columns.extend(fields if isinstance(fields, list) else [])
    return ConnectorSchemaResponse(
        columns=columns,
        connector_name=name,
        schema_version=1,
        row_estimate=None,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/{name}/validate")
async def validate_connector(name: str, pool: asyncpg.Pool = Depends(get_pool)) -> ConnectorValidationResponse:
    conn = await pool.fetchrow(
        "SELECT * FROM ml.connector_definitions WHERE name = $1 AND is_active = TRUE", name,
    )
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")
    errors = []
    warnings = []
    if not conn.get("config_schema") or conn["config_schema"] == {}:
        warnings.append("No configuration defined")
    return ConnectorValidationResponse(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        metadata={"connector_type": conn["connector_type"]},
    )


@router.post("/{name}/fetch")
async def fetch_connector_data(name: str, body: ConnectorFetchRequest,
                                pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    conn = await pool.fetchrow(
        "SELECT * FROM ml.connector_definitions WHERE name = $1 AND is_active = TRUE", name,
    )
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")
    return {
        "connector_name": name,
        "batch_size": body.batch_size,
        "max_records": body.max_records,
        "preview": True,
        "rows_sampled": 0,
        "message": "Dry-run fetch completed (no data actually retrieved)",
    }


@router.get("/{name}/checkpoints")
async def get_connector_checkpoints(name: str,
                                     pool: asyncpg.Pool = Depends(get_pool)) -> list[dict[str, Any]]:
    conn = await pool.fetchrow(
        "SELECT uuid FROM ml.connector_definitions WHERE name = $1 AND is_active = TRUE", name,
    )
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")
    rows = await pool.fetch(
        "SELECT * FROM ml.connector_checkpoints WHERE connector_name = $1 ORDER BY checkpoint_key",
        name,
    )
    return [dict(r) for r in rows]


@router.get("/types")
async def list_connector_types() -> list[str]:
    return sorted(VALID_CONNECTOR_TYPES)


@router.get("/health")
async def connectors_health():
    return {"status": "healthy", "service": "ML Connectors", "timestamp": datetime.now(timezone.utc).isoformat()}
