from fastapi import APIRouter, HTTPException, Request

from backend.api.events.repository import EventRepository
from backend.api.events.service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/")
async def list_events(request: Request, limit: int = 50, offset: int = 0):
    repo = EventRepository(request.app.state.pg_pool)
    service = EventService(repo)
    return await service.list_events(limit, offset)


@router.get("/{event_id}")
async def get_event(event_id: int, request: Request):
    repo = EventRepository(request.app.state.pg_pool)
    service = EventService(repo)
    event = await service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/{event_id}/articles")
async def get_event_articles(event_id: int, request: Request, limit: int = 20, offset: int = 0):
    repo = EventRepository(request.app.state.pg_pool)
    service = EventService(repo)
    return await service.get_event_articles(event_id, limit, offset)
