from fastapi import APIRouter, HTTPException, Request

from backend.api.graph.repository import GraphRepository
from backend.api.graph.service import GraphService
from backend.shared.entity_normalization import normalize_entity

router = APIRouter(prefix="/graph", tags=["Graph"])


@router.get("/network")
async def get_network(request: Request):
    try:
        repo = GraphRepository(request.app.state.pg_pool)
        service = GraphService(repo)
        return await service.get_network()
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{entity}")
async def get_entity_graph(
    entity: str,
    request: Request,
    depth: int = 2,
    limit: int = 50,
):
    try:
        entity = normalize_entity(entity)
        repo = GraphRepository(request.app.state.pg_pool)
        service = GraphService(repo)
        return await service.expand_graph(entity, depth, limit)
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
