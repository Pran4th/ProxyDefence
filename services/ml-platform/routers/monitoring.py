from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models import DriftBaselineRequest, DriftDetectionRequest, DriftResultResponse
from monitoring.monitor import ModelMonitor
from monitoring.alerts import get_alert_manager

router = APIRouter(prefix="/api/v1/ml/monitoring", tags=["ML Monitoring"])


@router.post("/baselines")
async def compute_baseline(body: DriftBaselineRequest) -> dict[str, Any]:
    monitor = ModelMonitor()
    baselines = await monitor.compute_baseline(body.model_name, body.model_version, body.n_bins)
    return {
        "model_name": body.model_name,
        "model_version": body.model_version,
        "feature_count": len(baselines),
        "features": list(baselines.keys()),
        "baselines": baselines,
    }


@router.post("/drift/detect")
async def detect_drift(body: DriftDetectionRequest) -> dict[str, Any]:
    monitor = ModelMonitor(window_size=body.window_size)
    try:
        results = await monitor.detect_drift(
            model_name=body.model_name,
            model_version=body.model_version,
            threshold_psi=body.threshold_psi,
            threshold_ks=body.threshold_ks,
            window_size=body.window_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    am = get_alert_manager()
    for r in results:
        if r.is_drift:
            am.evaluate("drift_score", r.drift_score,
                        model_name=body.model_name, model_version=body.model_version or 0)

    return {
        "model_name": body.model_name,
        "model_version": body.model_version or "production",
        "total_checks": len(results),
        "drifted_count": sum(1 for r in results if r.is_drift),
        "results": [
            DriftResultResponse(
                feature_name=r.feature_name,
                drift_type=r.drift_type,
                drift_score=r.drift_score,
                threshold=r.threshold,
                is_drift=r.is_drift,
                window_size=body.window_size,
                n_expected=r.n_expected,
                n_actual=r.n_actual,
                details=r.details,
            )
            for r in results
        ],
    }


@router.get("/predictions")
async def get_predictions(
    model_name: str = Query(...),
    model_version: int | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    monitor = ModelMonitor()
    return await monitor.get_recent_predictions(model_name, model_version, limit)


@router.get("/drift/results")
async def get_drift_results(
    model_name: str = Query(...),
    model_version: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    monitor = ModelMonitor()
    return await monitor.get_drift_summary(model_name, model_version, limit)


@router.get("/health")
async def monitoring_health():
    return {"status": "healthy", "service": "ML Monitoring"}
