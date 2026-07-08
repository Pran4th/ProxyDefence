import httpx
from fastapi import APIRouter, Query, Request

from backend.api.search.repository import SearchRepository
from backend.api.search.service import SearchService
from backend.shared.settings import settings

router = APIRouter(prefix="/search", tags=["Search"])
semantic_router = APIRouter(prefix="/semantic-search", tags=["Semantic Search"])


@router.get("/")
async def search_articles(request: Request, q: str = Query(..., min_length=2)):
    repo = SearchRepository(request.app.state.es_client)
    service = SearchService(repo)
    return await service.search_articles(q)


@semantic_router.get("")
async def semantic_search(q: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.EMBEDDING_SERVICE_URL}/search",
            params={"q": q},
        )
    return response.json()
