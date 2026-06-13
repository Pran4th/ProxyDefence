from fastapi import APIRouter, Request, HTTPException

from backend.api_service.repositories.intelligence import IntelligenceRepository

router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


@router.get("/")
async def list_events(
    request: Request,
    limit: int = 50,
    offset: int = 0
):
    repo = IntelligenceRepository(request.app.state.pg_pool)
    return await repo.list_events(limit, offset)


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    request: Request
):
    repo = IntelligenceRepository(request.app.state.pg_pool)

    event = await repo.get_event(event_id)

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    return event


@router.get("/{event_id}/articles")
async def get_event_articles(
    event_id: int,
    request: Request,
    limit: int = 20,
    offset: int = 0
):
    repo = IntelligenceRepository(request.app.state.pg_pool)

    return await repo.get_event_articles(
        event_id,
        limit,
        offset
    )