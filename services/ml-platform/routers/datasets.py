from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from db import get_pool
from models import DatasetBuildRequest, DatasetBuildResponse, PaginatedResponse
from datasets.builder import DatasetBuilder
from datasets.loader import EnergyServiceLoader, MockDataLoader
from datasets.splitter import DatasetSplitter

router = APIRouter(prefix="/api/v1/ml/datasets", tags=["ML Datasets"])


@router.post("", status_code=201)
async def build_dataset(body: DatasetBuildRequest,
                        pool: asyncpg.Pool = Depends(get_pool)) -> DatasetBuildResponse:
    loader = EnergyServiceLoader()
    splitter = DatasetSplitter(
        test_size=body.test_size,
        val_size=body.val_size,
        random_seed=body.random_seed,
    )
    builder = DatasetBuilder(loader=loader, splitter=splitter)

    try:
        result = await builder.build(
            name=body.name,
            target_column=body.target_column,
            feature_names=body.feature_names if body.feature_names else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dataset build failed: {str(e)}")

    return DatasetBuildResponse(
        uuid=result["uuid"],
        name=result["name"],
        version=result["version"],
        path=result["path"],
        total_records=result["total_records"],
        splits={k: v for k, v in [
            ("train", result.get("train_records")), ("validation", result.get("val_records")),
            ("test", result.get("test_records")),
        ] if v is not None},
        target_column=result["target_column"],
        feature_count=result.get("feature_count", 0),
    )


@router.get("")
async def list_datasets(
    name: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PaginatedResponse:
    conditions = ["1=1"]
    params: list = []
    if name:
        conditions.append(f"name = ${len(params) + 1}")
        params.append(name)
    where = " AND ".join(conditions)
    total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.datasets WHERE {where}", *params)
    params.append(limit)
    params.append(offset)
    rows = await pool.fetch(
        f"SELECT * FROM ml.datasets WHERE {where} ORDER BY name, version DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return PaginatedResponse(items=[dict(r) for r in rows], total=total or 0, limit=limit, offset=offset)


@router.get("/{uuid}")
async def get_dataset(uuid: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    row = await pool.fetchrow("SELECT * FROM ml.datasets WHERE uuid = $1", uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dict(row)


_VALID_SPLITS = {"train", "val", "test"}


@router.get("/{uuid}/download")
async def download_dataset(uuid: str, split: str = Query("train"),
                           pool: asyncpg.Pool = Depends(get_pool)):
    if split not in _VALID_SPLITS:
        raise HTTPException(status_code=422, detail=f"Invalid split '{split}'. Must be one of: {sorted(_VALID_SPLITS)}")
    row = await pool.fetchrow("SELECT path, name, version FROM ml.datasets WHERE uuid = $1", uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")
    from fastapi.responses import FileResponse
    import os
    filepath = os.path.join(row["path"], f"{split}.parquet")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Split '{split}' not found")
    return FileResponse(filepath, media_type="application/octet-stream",
                        filename=f"{row['name']}_v{row['version']}_{split}.parquet")
