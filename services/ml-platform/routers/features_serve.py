from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import FeatureServeRequest, FeatureServeResponse
from feature_store.pipeline import get_feature_pipeline
from feature_store.cache import get_feature_cache

router = APIRouter(prefix="/api/v1/ml/features/serve", tags=["ML Feature Serving"])


@router.post("/batch")
async def serve_features(body: FeatureServeRequest) -> dict[str, Any]:
    pipeline = get_feature_pipeline()
    cache = get_feature_cache()
    try:
        features = await pipeline.compute_features(
            entity_type=body.entity_type,
            entity_ids=body.entity_ids,
            feature_version=body.feature_version,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature computation failed: {str(e)}")

    missing = [eid for eid in body.entity_ids if eid not in features]
    return {
        "features": features,
        "feature_version": body.feature_version or "latest",
        "total_returned": len(features),
        "total_requested": len(body.entity_ids),
        "missing": missing if missing else None,
        "from_cache": False,
        "cache_hit_rate": cache.hit_rate,
    }


@router.get("/{entity_type}/{entity_id}")
async def get_feature_vector(
    entity_type: str,
    entity_id: str,
    feature_version: int | None = Query(None),
) -> dict[str, Any]:
    pipeline = get_feature_pipeline()
    features = await pipeline.get_features(entity_type, entity_id, feature_version)
    if features is None:
        raise HTTPException(status_code=404, detail=f"Features not found for {entity_type}/{entity_id}")
    return {"entity_type": entity_type, "entity_id": entity_id, "features": features}


@router.post("/refresh")
async def refresh_features(entity_type: str | None = Query(None)) -> dict:
    pipeline = get_feature_pipeline()
    await pipeline.refresh_all(entity_type)
    return {"status": "refreshed", "entity_type": entity_type or "all"}


@router.get("/cache/stats")
async def cache_stats() -> dict:
    cache = get_feature_cache()
    return {
        "size": cache.size,
        "hit_rate": cache.hit_rate,
        "capacity": cache.capacity,
    }


@router.get("/health")
async def serve_health():
    return {"status": "healthy", "service": "Feature Serving"}
