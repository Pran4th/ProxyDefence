from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import PaginatedResponse
from datasets.statistics import DatasetStatistics
from datasets.profiling import DatasetProfiler
from datasets.hashing import DatasetHasher, DatasetManifest

router = APIRouter(prefix="/api/v1/ml/datasets/profiling", tags=["ML Dataset Profiling"])


@router.get("/statistics/{name}/{version}")
async def get_statistics(name: str, version: int) -> dict[str, Any]:
    stats = await DatasetStatistics.get_stats(name, version)
    if not stats:
        raise HTTPException(status_code=404, detail="Statistics not found")
    return stats


@router.get("/health/{name}/{version}")
async def get_health_score(name: str, version: int) -> dict[str, Any]:
    return await DatasetStatistics.get_health_score(name, version)


@router.get("/profile/{name}/{version}")
async def get_profile(name: str, version: int) -> list[dict[str, Any]]:
    profiles = await DatasetProfiler.get_profile(name, version)
    if not profiles:
        raise HTTPException(status_code=404, detail="Profiles not found")
    return profiles


@router.get("/profile/{name}/{version}/{column}")
async def get_column_profile(name: str, version: int, column: str) -> dict[str, Any]:
    profile = await DatasetProfiler.get_column_profile(name, version, column)
    if not profile:
        raise HTTPException(status_code=404, detail="Column profile not found")
    return profile


@router.get("/manifest/{name}/{version}")
async def get_manifest(name: str, version: int) -> list[dict[str, Any]]:
    manifest = await DatasetManifest.get_manifest(name, version)
    return manifest


@router.post("/manifest/{name}/{version}/verify")
async def verify_manifest(name: str, version: int) -> dict[str, Any]:
    return await DatasetManifest.verify(name, version)


@router.get("/health")
async def profiling_health():
    return {"status": "healthy", "service": "Dataset Profiling"}
