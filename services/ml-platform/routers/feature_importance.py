from typing import Any

from fastapi import APIRouter, HTTPException, Query

from feature_store.importance import FeatureImportance

router = APIRouter(prefix="/api/v1/ml/features/importance", tags=["ML Feature Importance"])


@router.get("/{model_name}/{model_version}")
async def get_importance(model_name: str, model_version: int,
                           importance_type: str | None = Query(None),
                           limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    importance = await FeatureImportance.get_importance(
        model_name, model_version, importance_type, limit,
    )
    return importance


@router.get("/{model_name}/{model_version}/top")
async def get_top_features(model_name: str, model_version: int,
                             n: int = Query(10, ge=1, le=100)) -> list[dict[str, Any]]:
    importance = await FeatureImportance.get_top_features(model_name, model_version, n)
    return importance


@router.get("/health")
async def importance_health():
    return {"status": "healthy", "service": "Feature Importance"}
