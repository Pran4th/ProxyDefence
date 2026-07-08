from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import PaginatedResponse
from research.leaderboard import Leaderboard, RankingEntry

router = APIRouter(prefix="/api/v1/ml/research/leaderboard", tags=["ML Research Leaderboard"])

_leaderboard = Leaderboard()


@router.get("")
async def get_leaderboard(
    metric: str | None = Query(None),
    model_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse:
    try:
        entries = await _leaderboard.get_rankings(
            metric=metric, model_type=model_type, limit=limit, offset=offset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    items = [{
        "model_name": e.model_name,
        "model_version": e.model_version,
        "model_type": e.model_type,
        "experiment_name": e.experiment_name,
        "run_id": e.run_id,
        "primary_metric": e.primary_metric,
        "primary_score": e.primary_score,
        "secondary_metric": e.secondary_metric,
        "secondary_score": e.secondary_score,
        "training_time_seconds": e.training_time_seconds,
        "inference_latency_ms": e.inference_latency_ms,
        "memory_mb": e.memory_mb,
        "model_size_kb": e.model_size_kb,
        "dataset_name": e.dataset_name,
        "dataset_version": e.dataset_version,
        "feature_version": e.feature_version,
        "params": e.params,
        "created_at": e.created_at,
        "tags": e.tags,
    } for e in entries]
    return PaginatedResponse(items=items, total=len(items), limit=limit, offset=offset)


@router.get("/top")
async def get_top_models(
    metric: str = Query("f1"),
    n: int = Query(5, ge=1, le=100),
    model_type: str | None = Query(None),
) -> dict[str, Any]:
    try:
        entries = await _leaderboard.get_top_n(metric=metric, n=n, model_type=model_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "rankings": [{
            "rank": i + 1,
            "model_name": e.model_name,
            "model_version": e.model_version,
            "model_type": e.model_type,
            "primary_score": e.primary_score,
            "secondary_score": e.secondary_score,
            "inference_latency_ms": e.inference_latency_ms,
            "dataset_name": e.dataset_name,
        } for i, e in enumerate(entries)],
        "metric": metric,
    }


@router.get("/models/{model_name}/history")
async def get_model_history(model_name: str) -> dict[str, Any]:
    try:
        entries = await _leaderboard.get_model_history(model_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "model_name": model_name,
        "history": [{
            "model_version": e.model_version,
            "model_type": e.model_type,
            "experiment_name": e.experiment_name,
            "primary_metric": e.primary_metric,
            "primary_score": e.primary_score,
            "secondary_metric": e.secondary_metric,
            "secondary_score": e.secondary_score,
            "training_time_seconds": e.training_time_seconds,
            "inference_latency_ms": e.inference_latency_ms,
            "dataset_name": e.dataset_name,
            "created_at": e.created_at,
        } for e in entries],
    }


@router.post("/compare")
async def compare_leaderboard_entries(body: dict) -> dict[str, Any]:
    entry_ids = body.get("entry_ids", [])
    if not entry_ids:
        raise HTTPException(status_code=422, detail="'entry_ids' list is required")
    try:
        comparison = await _leaderboard.compare_entries(entry_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return comparison


@router.post("/add")
async def add_ranking_entry(body: dict) -> dict[str, str]:
    try:
        entry = RankingEntry(
            model_name=body["model_name"],
            model_version=int(body.get("model_version", 1)),
            model_type=body["model_type"],
            experiment_name=body.get("experiment_name", ""),
            run_id=body.get("run_id", ""),
            primary_metric=body.get("primary_metric", "f1"),
            primary_score=float(body.get("primary_score", 0.0)),
            secondary_metric=body.get("secondary_metric", "accuracy"),
            secondary_score=float(body.get("secondary_score", 0.0)),
            training_time_seconds=float(body.get("training_time_seconds", 0.0)),
            inference_latency_ms=body.get("inference_latency_ms"),
            memory_mb=body.get("memory_mb"),
            model_size_kb=body.get("model_size_kb"),
            dataset_name=body.get("dataset_name", ""),
            dataset_version=int(body.get("dataset_version", 1)),
            feature_version=int(body.get("feature_version", 1)),
            params=body.get("params", {}),
            tags=body.get("tags", []),
        )
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Missing required field: {e}")
    try:
        entry_id = await _leaderboard.add_entry(entry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"entry_id": entry_id, "status": "added"}


@router.get("/export/markdown")
async def export_leaderboard_markdown(
    metric: str = Query("f1"),
    n: int = Query(10, ge=1, le=100),
) -> dict[str, str]:
    try:
        md = await _leaderboard.to_markdown(n=n, metric=metric)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"markdown": md}


@router.get("/health")
async def leaderboard_health():
    return {"status": "healthy", "service": "Research Leaderboard"}
