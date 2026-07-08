from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.entities.repository import EntityRepository
from backend.api.entities.service import EntityService

router = APIRouter(prefix="/entities", tags=["Entities"])


@router.get("/")
async def get_entities(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
):
    repo = EntityRepository(request.app.state.pg_pool)
    service = EntityService(repo)
    return await service.list_entities(limit)


@router.get("/{entity_name}")
async def get_entity_profile(entity_name: str, request: Request):
    repo = EntityRepository(request.app.state.pg_pool)
    service = EntityService(repo)
    profile = await service.get_entity_profile(entity_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Entity not found")
    return profile


@router.get("/{entity_name}/articles")
async def get_entity_articles(entity_name: str, request: Request):
    repo = EntityRepository(request.app.state.pg_pool)
    service = EntityService(repo)
    return await service.get_entity_articles(entity_name)


@router.get("/{entity_name}/relationships")
async def get_entity_relationships(entity_name: str, request: Request):
    repo = EntityRepository(request.app.state.pg_pool)
    service = EntityService(repo)
    return await service.get_entity_relationships(entity_name)
