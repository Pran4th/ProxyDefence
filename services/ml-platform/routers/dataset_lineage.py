from typing import Any

from fastapi import APIRouter, HTTPException, Query

from datasets.lineage import DatasetLineage, DatasetProvenance

router = APIRouter(prefix="/api/v1/ml/datasets/lineage", tags=["ML Dataset Lineage"])


@router.get("/{name}/{version}")
async def get_lineage(name: str, version: int, depth: int = Query(5, ge=1, le=10)) -> dict[str, Any]:
    lineage = DatasetLineage()
    return await lineage.get_lineage_graph(name, version, depth)


@router.get("/{name}/{version}/parents")
async def get_parents(name: str, version: int) -> list[dict[str, Any]]:
    lineage = DatasetLineage()
    return await lineage.get_parents(name, version)


@router.get("/{name}/{version}/children")
async def get_children(name: str, version: int) -> list[dict[str, Any]]:
    lineage = DatasetLineage()
    return await lineage.get_children(name, version)


@router.get("/{name}/{version}/sources")
async def get_provenance(name: str, version: int) -> dict[str, Any]:
    provenance = DatasetProvenance()
    return await provenance.get_source_tree(name, version)


@router.get("/health")
async def lineage_health():
    return {"status": "healthy", "service": "Dataset Lineage"}
