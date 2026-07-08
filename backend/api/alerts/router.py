from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.api.alerts.repository import AlertRepository
from backend.api.alerts.schema import AlertStatusUpdate
from backend.api.alerts.service import AlertService
from backend.api.common.errors import error_response_invalid
from backend.api_service.security import require_admin

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/")
async def list_alerts(
    request: Request,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    repo = AlertRepository(request.app.state.pg_pool)
    service = AlertService(repo)
    return await service.list_alerts(status, limit, offset)


@router.get("/{alert_id}")
async def get_alert(alert_id: int, request: Request):
    repo = AlertRepository(request.app.state.pg_pool)
    service = AlertService(repo)
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}/status")
async def update_alert_status(alert_id: int, payload: AlertStatusUpdate, request: Request):
    repo = AlertRepository(request.app.state.pg_pool)
    service = AlertService(repo)
    try:
        alert = await service.update_alert_status(alert_id, payload.status)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return alert
    except ValueError:
        raise error_response_invalid("Invalid alert status value")


@router.post("/generate", dependencies=[Depends(require_admin)])
async def generate_alerts(request: Request):
    repo = AlertRepository(request.app.state.pg_pool)
    service = AlertService(repo)
    return await service.generate_alerts()
