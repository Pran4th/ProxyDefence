from fastapi import APIRouter, Depends, Request

from backend.api_service.dto import AlertCreateRequest
from backend.api_service.routes.auth import get_current_user
from backend.api_service.services.intelligence import IntelligenceService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("")
async def create_alert(
    payload: AlertCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.create_alert(payload, user_id=current_user.get("id"))
