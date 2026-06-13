from fastapi import APIRouter, HTTPException, Query, Request

from backend.api_service.services.intelligence import IntelligenceService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_events(
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.list_events(limit=limit, offset=offset)


@router.get("/{event_id}")
async def get_event(request: Request, event_id: int):
    service = IntelligenceService(request.app.state.pg_pool)
    event = await service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/{event_id}/articles")
async def get_event_articles(
    request: Request,
    event_id: int,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.get_event_articles(event_id=event_id, limit=limit, offset=offset)
