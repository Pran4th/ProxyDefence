from fastapi import APIRouter, Depends, Query, Request

from backend.api_service.dto import WatchlistCreateRequest
from backend.api_service.routes.auth import get_current_user
from backend.api_service.services.intelligence import IntelligenceService

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.post("")
async def create_watchlist(
    payload: WatchlistCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.create_watchlist(payload, user_id=current_user.get("id"))


@router.get("")
async def list_watchlists(
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.list_watchlists(user_id=current_user.get("id"), limit=limit, offset=offset)
