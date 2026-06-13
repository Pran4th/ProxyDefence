import httpx
from fastapi import APIRouter

router = APIRouter(
    prefix="/semantic-search",
    tags=["Semantic Search"]
)

@router.get("")
async def semantic_search(q: str):

    async with httpx.AsyncClient() as client:

        response = await client.get(
            "http://embedding-service:8000/search",
            params={"q": q}
        )

    return response.json()