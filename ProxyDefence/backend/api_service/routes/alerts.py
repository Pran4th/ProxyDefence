from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.api_service.repositories.intelligence import IntelligenceRepository
from backend.api_service.security import require_admin

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"]
)


class AlertStatusUpdate(BaseModel):
    status: str


@router.get("/")
async def list_alerts(
    request: Request,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List all alerts with optional status filter."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    return await repo.list_alerts(status, limit, offset)


@router.get("/{alert_id}")
async def get_alert(
    alert_id: int,
    request: Request
):
    """Get a specific alert with watchlist and event details."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    alert = await repo.get_alert(alert_id)

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )

    return alert


@router.patch("/{alert_id}/status")
async def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    request: Request
):
    """Update an alert's status."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    try:
        alert = await repo.update_alert_status(alert_id, payload.status)

        if not alert:
            raise HTTPException(
                status_code=404,
                detail="Alert not found"
            )

        return alert

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/generate", dependencies=[Depends(require_admin)])
async def generate_alerts(
    request: Request
):
    """Automatically generate alerts by matching watchlist entities with event entities."""
    repo = IntelligenceRepository(request.app.state.pg_pool)
    
    result = await repo.generate_alerts()
    
    return result
