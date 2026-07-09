from typing import Any

from backend.api.search.repository import SearchRepository


class SearchService:
    def __init__(self, repository: SearchRepository) -> None:
        self.repository = repository

    async def search_articles(
        self,
        query: str,
        topic: str | None = None,
        risk_level: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self.repository.search_articles(query, topic, risk_level, limit, offset)
