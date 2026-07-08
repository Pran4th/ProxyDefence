from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import PaginatedResponse
from datasets.validation import DatasetValidationPipeline, default_validators, full_validators
from datasets.statistics import DatasetStatistics
from datasets.hashing import DatasetManifest
from datasets.schema_registry import SchemaRegistry

router = APIRouter(prefix="/api/v1/ml/datasets/validation", tags=["ML Dataset Validation"])


@router.get("/validators")
async def list_validators(full: bool = Query(False)) -> list[dict[str, Any]]:
    validators = full_validators() if full else default_validators()
    return [{"name": name, "validator": v.__name__ if hasattr(v, "__name__") else type(v).__name__}
            for name, v in validators]


@router.get("/results")
async def get_validation_results(
    dataset_name: str = Query(...),
    dataset_version: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    pool = None
    try:
        from db import get_pool
        pool = await get_pool()
    except Exception:
        pass
    if pool:
        if dataset_version:
            rows = await pool.fetch(
                "SELECT * FROM ml.dataset_validations WHERE dataset_name = $1 AND dataset_version = $2 "
                "ORDER BY executed_at DESC LIMIT $3",
                dataset_name, dataset_version, limit,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM ml.dataset_validations WHERE dataset_name = $1 "
                "ORDER BY executed_at DESC LIMIT $2",
                dataset_name, limit,
            )
        return [dict(r) for r in rows]
    return []


@router.get("/health")
async def validate_health():
    return {"status": "healthy", "service": "Dataset Validation"}
