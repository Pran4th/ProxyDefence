from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.api.watchlists.repository import WatchlistRepository
from backend.api.watchlists.schema import WatchlistCreate, WatchlistEntityAdd
from backend.api.watchlists.service import WatchlistService
from backend.api_service.security import get_current_user

router = APIRouter(prefix="/watchlists", tags=["Watchlists"])


@router.get("/")
async def list_watchlists(
    request: Request,
    current_user: dict = Depends(get_current_user),
    owner_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    repo = WatchlistRepository(request.app.state.pg_pool)
    service = WatchlistService(repo)
    owner_filter = owner_id if current_user.get("role") == "admin" else current_user["id"]
    return await service.list_watchlists(owner_filter, limit, offset)


@router.post("/")
async def create_watchlist(
    payload: WatchlistCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = WatchlistRepository(request.app.state.pg_pool)
    service = WatchlistService(repo)
    return await service.create_watchlist(
        name=payload.name,
        description=payload.description,
        owner_id=current_user["id"],
        entities=payload.entities,
    )


@router.get("/{watchlist_id}")
async def get_watchlist(
    watchlist_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = WatchlistRepository(request.app.state.pg_pool)
    service = WatchlistService(repo)
    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    service.ensure_access(watchlist, current_user)
    return watchlist


@router.delete("/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = WatchlistRepository(request.app.state.pg_pool)
    service = WatchlistService(repo)
    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    service.ensure_access(watchlist, current_user)
    result = await service.delete_watchlist(watchlist_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return result


@router.post("/{watchlist_id}/entities")
async def add_watchlist_entity(
    watchlist_id: int,
    payload: WatchlistEntityAdd,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = WatchlistRepository(request.app.state.pg_pool)
    service = WatchlistService(repo)
    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    service.ensure_access(watchlist, current_user)
    entities = await service.add_watchlist_entity(watchlist_id, payload.entity_text)
    return {"watchlist_id": watchlist_id, "entities": entities}


@router.delete("/{watchlist_id}/entities/{entity_text}")
async def remove_watchlist_entity(
    watchlist_id: int,
    entity_text: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = WatchlistRepository(request.app.state.pg_pool)
    service = WatchlistService(repo)
    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    service.ensure_access(watchlist, current_user)
    entities = await service.remove_watchlist_entity(watchlist_id, entity_text)
    return {"watchlist_id": watchlist_id, "entities": entities}
