from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import PaginatedResponse
from research.experiment import ExperimentManager

router = APIRouter(prefix="/api/v1/ml/research/experiments", tags=["ML Research Experiments"])


@router.post("")
async def create_experiment(name: str, experiment_type: str,
                              description: str | None = Query(None),
                              author: str | None = Query(None),
                              random_seed: int | None = Query(None),
                              tags: str | None = Query(None)) -> dict[str, Any]:
    manager = ExperimentManager()
    result = await manager.create_experiment(
        name=name, experiment_type=experiment_type,
        description=description, author=author,
        random_seed=random_seed,
        tags=tags.split(",") if tags else None,
    )
    return result


@router.get("")
async def list_experiments(
    experiment_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse:
    manager = ExperimentManager()
    items, total = await manager.list_experiments(
        experiment_type=experiment_type, status=status,
        limit=limit, offset=offset,
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{uuid_or_name}")
async def get_experiment(uuid_or_name: str) -> dict[str, Any]:
    manager = ExperimentManager()
    result = await manager.get_experiment(uuid_or_name)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


@router.post("/{experiment_uuid}/runs")
async def start_run(experiment_uuid: str, run_name: str,
                     random_seed: int | None = Query(None)) -> dict[str, Any]:
    manager = ExperimentManager()
    try:
        result = await manager.start_run(experiment_uuid, run_name, random_seed=random_seed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.put("/runs/{run_uuid}/finish")
async def finish_run(run_uuid: str, status: str = Query("completed"),
                      metrics_json: str | None = Query(None),
                      error_message: str | None = Query(None)) -> dict[str, Any]:
    manager = ExperimentManager()
    import json
    metrics = json.loads(metrics_json) if metrics_json else None
    try:
        result = await manager.finish_run(
            run_uuid=run_uuid, status=status,
            metrics=metrics, error_message=error_message,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.get("/{experiment_uuid}/runs")
async def get_runs(experiment_uuid: str, limit: int = Query(100, ge=1, le=1000),
                     offset: int = Query(0, ge=0)) -> PaginatedResponse:
    manager = ExperimentManager()
    items, total = await manager.get_runs(experiment_uuid, limit=limit, offset=offset)
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/runs/{run_uuid}")
async def get_run(run_uuid: str) -> dict[str, Any]:
    manager = ExperimentManager()
    result = await manager.get_run(run_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.post("/compare")
async def compare_runs(run_uuids: str = Query(...)) -> list[dict[str, Any]]:
    manager = ExperimentManager()
    uuids = [u.strip() for u in run_uuids.split(",")]
    return await manager.compare_runs(uuids)


@router.get("/health")
async def experiments_health():
    return {"status": "healthy", "service": "Research Experiments"}
