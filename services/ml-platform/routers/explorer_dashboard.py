from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger
from models import (
    ExplorerSearchRequest,
    ExplorerSearchResponse,
    SchemaTableResponse,
    ModelDetailResponse,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/ml/explorer", tags=["ML Explorer Dashboard"])


@router.post("/search")
async def explorer_search(body: ExplorerSearchRequest,
                           pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    results: list[dict] = []
    query = f"%{body.query}%"

    if body.resource_type in ("all", "dataset"):
        datasets = await pool.fetch(
            "SELECT uuid, name, version, total_records, created_at, 'dataset' AS resource_type "
            "FROM ml.datasets WHERE name ILIKE $1 LIMIT $2 OFFSET $3",
            query, body.limit, body.offset,
        )
        results.extend(dict(r) for r in datasets)

    if body.resource_type in ("all", "feature"):
        features = await pool.fetch(
            "SELECT uuid, name, version, feature_type, created_at, 'feature' AS resource_type "
            "FROM ml.feature_definitions WHERE name ILIKE $1 AND is_active = TRUE LIMIT $2 OFFSET $3",
            query, body.limit, body.offset,
        )
        results.extend(dict(r) for r in features)

    if body.resource_type in ("all", "model"):
        models = await pool.fetch(
            "SELECT uuid, name, version, model_type, stage, created_at, 'model' AS resource_type "
            "FROM ml.model_versions WHERE name ILIKE $1 LIMIT $2 OFFSET $3",
            query, body.limit, body.offset,
        )
        results.extend(dict(r) for r in models)

    if body.resource_type in ("all", "experiment"):
        exps = await pool.fetch(
            "SELECT uuid, name, experiment_type, status, created_at, 'experiment' AS resource_type "
            "FROM ml.experiments WHERE name ILIKE $1 LIMIT $2 OFFSET $3",
            query, body.limit, body.offset,
        )
        results.extend(dict(r) for r in exps)

    if body.resource_type in ("all", "pipeline"):
        pipelines = await pool.fetch(
            "SELECT uuid, name, version, pipeline_type, is_active, created_at, 'pipeline' AS resource_type "
            "FROM ml.feature_pipelines WHERE name ILIKE $1 AND is_active = TRUE LIMIT $2 OFFSET $3",
            query, body.limit, body.offset,
        )
        results.extend(dict(r) for r in pipelines)

    return {
        "items": results[: body.limit],
        "total": len(results),
        "resource_type": body.resource_type,
        "query": body.query,
    }


@router.get("/schema/tables")
async def list_schema_tables(pool: asyncpg.Pool = Depends(get_pool)) -> list[SchemaTableResponse]:
    schemas = ("ml", "energy", "public")
    tables = []
    for schema in schemas:
        rows = await pool.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = $1 AND table_type = 'BASE TABLE' ORDER BY table_name",
            schema,
        )
        for r in rows:
            count = await pool.fetchval(
                f"SELECT COUNT(*) FROM {schema}.{r['table_name']}",
            )
            col_count = await pool.fetchval(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = $1 AND table_name = $2",
                schema, r["table_name"],
            )
            tables.append(SchemaTableResponse(
                table_name=r["table_name"],
                schema_name=schema,
                column_count=col_count or 0,
                row_estimate=count or 0,
            ))
    return tables


@router.get("/schema/table/{table_name}")
async def get_table_schema(table_name: str,
                            schema_name: str = Query("ml"),
                            pool: asyncpg.Pool = Depends(get_pool)) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        "SELECT column_name, data_type, is_nullable, column_default, "
        "character_maximum_length, numeric_precision, numeric_scale "
        "FROM information_schema.columns "
        "WHERE table_schema = $1 AND table_name = $2 ORDER BY ordinal_position",
        schema_name, table_name,
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Table '{schema_name}.{table_name}' not found")
    return [dict(r) for r in rows]


@router.get("/datasets")
async def explore_datasets(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    total = await pool.fetchval("SELECT COUNT(*) FROM ml.datasets")
    rows = await pool.fetch(
        "SELECT * FROM ml.datasets ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/features")
async def explore_features(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    total = await pool.fetchval("SELECT COUNT(*) FROM ml.feature_definitions WHERE is_active = TRUE")
    rows = await pool.fetch(
        "SELECT * FROM ml.feature_definitions WHERE is_active = TRUE ORDER BY name LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/models")
async def explore_models(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    total = await pool.fetchval("SELECT COUNT(*) FROM ml.model_versions")
    rows = await pool.fetch(
        "SELECT * FROM ml.model_versions ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/experiments")
async def explore_experiments(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    total = await pool.fetchval("SELECT COUNT(*) FROM ml.experiments")
    rows = await pool.fetch(
        "SELECT * FROM ml.experiments ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/pipelines")
async def explorer_pipelines(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    total = await pool.fetchval("SELECT COUNT(*) FROM ml.feature_pipelines WHERE is_active = TRUE")
    rows = await pool.fetch(
        "SELECT * FROM ml.feature_pipelines WHERE is_active = TRUE ORDER BY name LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/artifacts")
async def explore_artifacts(
    artifact_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions: list[str] = []
    params: list = []
    if artifact_type:
        conditions.append(f"artifact_type = ${len(params) + 1}")
        params.append(artifact_type)
    where = " AND ".join(conditions) if conditions else "TRUE"
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.research_artifacts WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.research_artifacts WHERE {where} ORDER BY created_at DESC "
        f"LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/metadata/{resource_type}/{identifier}")
async def get_resource_metadata(resource_type: str, identifier: str,
                                 pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    table_map = {
        "dataset": "ml.datasets",
        "feature": "ml.feature_definitions",
        "model": "ml.model_versions",
        "experiment": "ml.experiments",
        "pipeline": "ml.feature_pipelines",
        "connector": "ml.connector_definitions",
        "quality_report": "ml.quality_reports",
        "artifact": "ml.research_artifacts",
    }
    table = table_map.get(resource_type)
    if not table:
        raise HTTPException(status_code=422, detail=f"Unknown resource_type: {resource_type}")
    row = await pool.fetchrow(
        f"SELECT * FROM {table} WHERE uuid = $1 OR name = $1 LIMIT 1", identifier,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"{resource_type} '{identifier}' not found")
    return dict(row)


@router.get("/health")
async def explorer_health():
    return {"status": "healthy", "service": "ML Explorer Dashboard", "timestamp": datetime.now(timezone.utc).isoformat()}
