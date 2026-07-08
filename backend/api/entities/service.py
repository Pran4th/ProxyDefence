from typing import Any

from backend.api.entities.repository import EntityRepository


class EntityService:
    def __init__(self, repository: EntityRepository) -> None:
        self.repository = repository

    async def list_entities(self, limit: int) -> list[dict[str, Any]]:
        return await self.repository.list_entities(limit)

    async def get_entity_profile(self, entity_name: str) -> dict[str, Any] | None:
        return await self.repository.get_entity_profile(entity_name)

    async def get_entity_articles(self, entity_name: str) -> list[dict[str, Any]]:
        return await self.repository.get_entity_articles(entity_name)

    async def get_entity_relationships(self, entity_name: str) -> list[dict[str, Any]]:
        return await self.repository.get_entity_relationships(entity_name)
