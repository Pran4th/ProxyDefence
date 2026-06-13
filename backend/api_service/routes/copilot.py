from fastapi import APIRouter, Depends, Request

from backend.api_service.dto import CopilotQueryRequest
from backend.api_service.routes.auth import get_current_user
from backend.api_service.services.intelligence import IntelligenceService

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/query")
async def query_copilot(
    payload: CopilotQueryRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = IntelligenceService(request.app.state.pg_pool, request.app.state.es_client)
    return await service.answer_copilot_query(payload, user_id=current_user.get("id"))
