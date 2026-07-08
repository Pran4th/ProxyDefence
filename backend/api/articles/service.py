from typing import Any

from backend.api.articles.repository import ArticleRepository


class ArticleService:
    def __init__(self, repository: ArticleRepository) -> None:
        self.repository = repository

    async def list_articles(
        self,
        limit: int,
        offset: int,
        sentiment: str | None = None,
        topic: str | None = None,
        risk_level: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repository.list_articles(limit, offset, sentiment, topic, risk_level)

    async def get_article(self, article_id: int) -> dict[str, Any] | None:
        article = await self.repository.get_article(article_id)
        if article:
            energy = await self.repository.get_article_energy_context(article_id)
            article["energy_context"] = energy
        return article

    async def get_article_entities(self, article_id: int) -> list[dict[str, Any]]:
        return await self.repository.get_article_entities(article_id)
