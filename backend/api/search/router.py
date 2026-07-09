import httpx
from fastapi import APIRouter, Query, Request

from backend.api.search.repository import SearchRepository
from backend.api.search.service import SearchService
from backend.shared.settings import settings

router = APIRouter(prefix="/search", tags=["Search"])
semantic_router = APIRouter(prefix="/semantic-search", tags=["Semantic Search"])


@router.get("/")
async def search_articles(
    request: Request,
    q: str = Query(..., min_length=2),
    topic: str | None = Query(None),
    risk_level: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    repo = SearchRepository(request.app.state.es_client)
    service = SearchService(repo)
    return await service.search_articles(q, topic, risk_level, limit, offset)


@semantic_router.get("")
async def semantic_search(q: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.EMBEDDING_SERVICE_URL}/search",
            params={"q": q},
        )
    return response.json()
