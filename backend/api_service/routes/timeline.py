from fastapi import APIRouter, Query, Request

from backend.api_service.services.intelligence import IntelligenceService

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("")
async def get_timeline(
    request: Request,
    entity: str | None = None,
    event_id: int | None = None,
    timeline_type: str | None = Query(None, pattern="^(article|event|risk)$"),
    limit: int = Query(50, ge=1, le=200),
):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.get_timeline(
        entity=entity,
        event_id=event_id,
        timeline_type=timeline_type,
        limit=limit,
    )
