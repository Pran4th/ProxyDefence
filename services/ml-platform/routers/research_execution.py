from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import PaginatedResponse
from research.experiment_runner import ExperimentRunner, ExecutionCoordinator

router = APIRouter(prefix="/api/v1/ml/research/execution", tags=["ML Research Execution"])

_runner = ExperimentRunner()
_coordinator = ExecutionCoordinator()


@router.post("/run")
async def run_experiment(body: dict) -> dict[str, str]:
    config = body.get("config")
    if not config:
        raise HTTPException(status_code=422, detail="'config' field is required")
    experiment_name = body.get("experiment_name")
    try:
        execution_id = await _coordinator.submit(_runner, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "execution_id": execution_id,
        "status": "submitted",
        "experiment_name": experiment_name or config.get("experiment", {}).get("name", "unnamed"),
    }


@router.post("/cancel/{execution_id}")
async def cancel_execution(execution_id: str) -> dict[str, str]:
    try:
        await _coordinator.cancel(execution_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"execution_id": execution_id, "status": "cancelled"}


@router.get("/status/{execution_id}")
async def get_execution_status(execution_id: str) -> dict[str, Any]:
    try:
        status = await _runner.get_status(execution_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return status


@router.get("/history")
async def list_execution_history(
    experiment_name: str | None = Query(None),
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse:
    try:
        items = await _runner.get_execution_history(
            experiment_name=experiment_name, limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return PaginatedResponse(
        items=items[offset:offset + limit],
        total=len(items),
        limit=limit,
        offset=offset,
    )


@router.get("/history/{execution_id}/logs")
async def get_execution_logs(execution_id: str) -> dict[str, Any]:
    try:
        logs = await _runner.get_execution_logs(execution_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"execution_id": execution_id, "logs": logs}


@router.post("/compare")
async def compare_executions(body: dict) -> dict[str, Any]:
    execution_ids = body.get("execution_ids", [])
    if not execution_ids:
        raise HTTPException(status_code=422, detail="'execution_ids' list is required")
    try:
        comparison = await _runner.compare_experiments(execution_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    scores = {}
    for eid, data in comparison.get("executions", {}).items():
        metrics = data.get("metrics", {})
        if metrics:
            scores[eid] = metrics.get("f1", metrics.get("accuracy", 0))
    winner = max(scores, key=scores.get) if scores else None
    return {"comparison": comparison, "winner": winner}


@router.post("/resume/{execution_id}")
async def resume_execution(execution_id: str, body: dict) -> dict[str, str]:
    from_stage = body.get("from_stage")
    try:
        new_execution_id = await _runner.resume_experiment(execution_id, from_stage=from_stage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"execution_id": new_execution_id, "status": "resumed"}


@router.get("/coordinator/active")
async def list_active_executions() -> dict[str, Any]:
    active = await _coordinator.list_active()
    return {"active": active, "count": len(active)}


@router.post("/coordinator/cleanup")
async def cleanup_executions(body: dict) -> dict[str, int]:
    from datetime import datetime, timezone, timedelta
    max_age_hours = body.get("max_age_hours", 72)
    before = len(_coordinator._completed) + len(_coordinator._active)
    _coordinator.cleanup(max_age_hours=max_age_hours)
    after = len(_coordinator._completed) + len(_coordinator._active)
    return {"removed": before - after}


@router.get("/health")
async def execution_health():
    return {"status": "healthy", "service": "Research Execution"}
