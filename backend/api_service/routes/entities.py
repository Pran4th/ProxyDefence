from fastapi import APIRouter, HTTPException, Request

from backend.api_service.services.intelligence import IntelligenceService

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/{entity}")
async def get_entity_profile(request: Request, entity: str):
    service = IntelligenceService(request.app.state.pg_pool)
    profile = await service.get_entity_profile(entity)
    if profile is None:
        raise HTTPException(status_code=404, detail="Entity profile not found")
    return profile


@router.get("/{entity}/timeline")
async def get_entity_timeline(request: Request, entity: str):
    service = IntelligenceService(request.app.state.pg_pool)
    return await service.get_entity_timeline(entity)
