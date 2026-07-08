from typing import Any

from backend.api.search.repository import SearchRepository


class SearchService:
    def __init__(self, repository: SearchRepository) -> None:
        self.repository = repository

    async def search_articles(self, query: str, limit: int = 20) -> dict[str, Any]:
        return await self.repository.search_articles(query, limit)
