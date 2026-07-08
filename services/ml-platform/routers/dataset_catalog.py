from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import PaginatedResponse
from datasets.catalog import DatasetCatalog

router = APIRouter(prefix="/api/v1/ml/datasets/catalog", tags=["ML Dataset Catalog"])


@router.post("/register")
async def register_dataset(name: str, dataset_type: str,
                            description: str | None = Query(None),
                            category: str | None = Query(None),
                            tags: str | None = Query(None),
                            owner: str | None = Query(None),
                            source: str | None = Query(None)) -> dict[str, Any]:
    catalog = DatasetCatalog()
    try:
        result = await catalog.register(
            name=name, dataset_type=dataset_type,
            description=description, category=category,
            tags=tags.split(",") if tags else None,
            owner=owner, source=source,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.get("")
async def search_catalog(
    query: str | None = Query(None),
    dataset_type: str | None = Query(None),
    category: str | None = Query(None),
    tag: str | None = Query(None),
    owner: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse:
    catalog = DatasetCatalog()
    items, total = await catalog.search(
        query=query, dataset_type=dataset_type,
        category=category, tag=tag, owner=owner,
        limit=limit, offset=offset,
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{name}")
async def get_dataset_entry(name: str) -> dict[str, Any]:
    catalog = DatasetCatalog()
    result = await catalog.get(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found in catalog")
    return result


@router.get("/types")
async def list_types() -> list[str]:
    catalog = DatasetCatalog()
    return await catalog.list_types()


@router.get("/categories")
async def list_categories() -> list[str]:
    catalog = DatasetCatalog()
    return await catalog.list_categories()


@router.put("/{name}/tags")
async def update_tags(name: str, tags: str = Query(...)) -> dict[str, Any]:
    catalog = DatasetCatalog()
    result = await catalog.update_tags(name, tags.split(","))
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
    return result


@router.delete("/{name}")
async def deactivate_dataset(name: str) -> dict:
    catalog = DatasetCatalog()
    result = await catalog.deactivate(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
    return {"status": "deactivated", "name": name}


@router.get("/health")
async def catalog_health():
    return {"status": "healthy", "service": "Dataset Catalog"}
