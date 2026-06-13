from fastapi import APIRouter, Depends, Request

from backend.api_service.dto import ReportGenerateRequest
from backend.api_service.routes.auth import get_current_user
from backend.api_service.services.intelligence import IntelligenceService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate")
async def generate_report(
    payload: ReportGenerateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.generate_report(payload, user_id=current_user.get("id"))
