from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger
from models import (
    QualityScoreResponse,
    QualityReportResponse,
    QualityDashboardResponse,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/ml/quality", tags=["ML Data Quality"])


@router.post("/score")
async def score_dataset(dataset_name: str = Query(...),
                         dataset_version: int = Query(1),
                         pool: asyncpg.Pool = Depends(get_pool)) -> QualityScoreResponse:
    report = await pool.fetchrow(
        "SELECT * FROM ml.quality_reports WHERE dataset_name = $1 AND dataset_version = $2 "
        "ORDER BY executed_at DESC LIMIT 1",
        dataset_name, dataset_version,
    )
    if not report:
        raise HTTPException(status_code=404, detail=f"No quality report for '{dataset_name}' v{dataset_version}")
    dims = report.get("dimensions") or {}
    dimension_scores = {
        "completeness": report.get("completeness_score") or dims.get("completeness", 0.0),
        "accuracy": report.get("accuracy_score") or dims.get("accuracy", 0.0),
        "consistency": report.get("consistency_score") or dims.get("consistency", 0.0),
        "timeliness": report.get("timeliness_score") or dims.get("timeliness", 0.0),
        "uniqueness": report.get("uniqueness_score") or dims.get("uniqueness", 0.0),
        "validity": report.get("validity_score") or dims.get("validity", 0.0),
    }
    return QualityScoreResponse(
        overall_score=report["overall_score"] or 0.0,
        dimension_scores=dimension_scores,
        details={"report_uuid": str(report["uuid"]), "status": report["status"]},
    )


@router.get("/reports")
async def list_quality_reports(
    dataset_name: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions: list[str] = []
    params: list = []
    if dataset_name:
        conditions.append(f"dataset_name = ${len(params) + 1}")
        params.append(dataset_name)
    where = " AND ".join(conditions) if conditions else "TRUE"
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.quality_reports WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.quality_reports WHERE {where} ORDER BY executed_at DESC "
        f"LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/reports/{dataset_name}/{version}")
async def get_quality_report(dataset_name: str, version: int,
                              pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM ml.quality_reports WHERE dataset_name = $1 AND dataset_version = $2 "
        "ORDER BY executed_at DESC LIMIT 1",
        dataset_name, version,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Quality report not found for '{dataset_name}' v{version}")
    return dict(row)


@router.post("/reports/compare")
async def compare_quality_reports(dataset_name: str = Query(...),
                                   versions: str = Query(...),
                                   pool: asyncpg.Pool = Depends(get_pool)) -> list[dict[str, Any]]:
    version_list = [int(v.strip()) for v in versions.split(",")]
    rows = []
    for v in version_list:
        row = await pool.fetchrow(
            "SELECT * FROM ml.quality_reports WHERE dataset_name = $1 AND dataset_version = $2 "
            "ORDER BY executed_at DESC LIMIT 1",
            dataset_name, v,
        )
        if row:
            rows.append(dict(row))
    return rows


@router.get("/dashboard")
async def quality_dashboard(
    dataset_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict[str, Any]]:
    if dataset_name:
        rows = await pool.fetch(
            "SELECT * FROM ml.quality_dashboard WHERE dataset_name = $1 ORDER BY snapshot_date DESC LIMIT $2",
            dataset_name, limit,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM ml.quality_dashboard ORDER BY snapshot_date DESC LIMIT $1", limit,
        )
    return [dict(r) for r in rows]


@router.get("/dashboard/trend/{dimension}")
async def quality_dimension_trend(
    dimension: str,
    dataset_name: str | None = Query(None),
    limit: int = Query(30, ge=1, le=365),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict[str, Any]]:
    score_col = f"{dimension}_score"
    if dataset_name:
        rows = await pool.fetch(
            f"SELECT snapshot_date, {score_col} AS metric_value, overall_score FROM ml.quality_dashboard "
            f"WHERE dataset_name = $1 ORDER BY snapshot_date DESC LIMIT $2",
            dataset_name, limit,
        )
    else:
        rows = await pool.fetch(
            f"SELECT snapshot_date, {score_col} AS metric_value, overall_score, dataset_name FROM ml.quality_dashboard "
            f"ORDER BY snapshot_date DESC LIMIT $1", limit,
        )
    return [dict(r) for r in rows]


@router.get("/dashboard/lowest")
async def quality_lowest_columns(
    dataset_name: str | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict[str, Any]]:
    if dataset_name:
        rows = await pool.fetch(
            "SELECT * FROM ml.quality_reports WHERE dataset_name = $1 AND overall_score IS NOT NULL "
            "ORDER BY overall_score ASC LIMIT $2",
            dataset_name, limit,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM ml.quality_reports WHERE overall_score IS NOT NULL "
            "ORDER BY overall_score ASC LIMIT $1", limit,
        )
    return [dict(r) for r in rows]


@router.get("/dashboard/summary")
async def quality_summary(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    total_reports = await pool.fetchval("SELECT COUNT(*) FROM ml.quality_reports")
    avg_score = await pool.fetchval("SELECT AVG(overall_score) FROM ml.quality_reports WHERE overall_score IS NOT NULL")
    total_datasets = await pool.fetchval("SELECT COUNT(DISTINCT dataset_name) FROM ml.quality_reports")
    return {
        "total_reports": total_reports or 0,
        "average_overall_score": round(float(avg_score), 4) if avg_score else 0.0,
        "total_datasets": total_datasets or 0,
    }


@router.get("/dashboard/issues")
async def quality_issues(
    dataset_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict[str, Any]]:
    if dataset_name:
        rows = await pool.fetch(
            "SELECT dataset_name, dataset_version, checks_json, failed_checks, warning_checks "
            "FROM ml.quality_reports WHERE dataset_name = $1 AND failed_checks > 0 "
            "ORDER BY executed_at DESC LIMIT $2",
            dataset_name, limit,
        )
    else:
        rows = await pool.fetch(
            "SELECT dataset_name, dataset_version, checks_json, failed_checks, warning_checks "
            "FROM ml.quality_reports WHERE failed_checks > 0 ORDER BY executed_at DESC LIMIT $1",
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/health")
async def quality_health():
    return {"status": "healthy", "service": "ML Data Quality", "timestamp": datetime.now(timezone.utc).isoformat()}
