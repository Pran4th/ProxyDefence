from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.api_service.repositories.intelligence import IntelligenceRepository

router = APIRouter(
    prefix="/watchlists",
    tags=["Watchlists"]
)


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    entities: list[str] = Field(default_factory=list)


class WatchlistEntityAdd(BaseModel):
    entity_text: str = Field(min_length=1, max_length=500)


@router.get("/")
async def list_watchlists(
    request: Request,
    owner_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List all watchlists with optional owner filter."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    return await repo.list_watchlists(owner_id, limit, offset)


@router.get("/{watchlist_id}")
async def get_watchlist(
    watchlist_id: int,
    request: Request
):
    """Get a specific watchlist with its entities."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    watchlist = await repo.get_watchlist(watchlist_id)

    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )

    return watchlist


@router.post("/")
async def create_watchlist(
    payload: WatchlistCreate,
    request: Request,
    owner_id: int | None = None
):
    """Create a new watchlist with optional initial entities."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    watchlist = await repo.create_watchlist(
        name=payload.name,
        description=payload.description,
        owner_id=owner_id,
        entities=payload.entities
    )

    return watchlist


@router.delete("/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: int,
    request: Request
):
    """Delete a watchlist and all its associated entities."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    result = await repo.delete_watchlist(watchlist_id)

    if not result.get("deleted"):
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )

    return result


@router.post("/{watchlist_id}/entities")
async def add_watchlist_entity(
    watchlist_id: int,
    payload: WatchlistEntityAdd,
    request: Request
):
    """Add an entity to a watchlist."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    # Verify watchlist exists
    watchlist = await repo.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )

    entities = await repo.add_watchlist_entity(
        watchlist_id,
        payload.entity_text
    )

    return {
        "watchlist_id": watchlist_id,
        "entities": entities
    }


@router.delete("/{watchlist_id}/entities/{entity_text}")
async def remove_watchlist_entity(
    watchlist_id: int,
    entity_text: str,
    request: Request
):
    """Remove an entity from a watchlist."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    # Verify watchlist exists
    watchlist = await repo.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )

    entities = await repo.remove_watchlist_entity(
        watchlist_id,
        entity_text
    )

    return {
        "watchlist_id": watchlist_id,
        "entities": entities
    }
