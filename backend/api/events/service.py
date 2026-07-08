from typing import Any

from backend.api.events.repository import EventRepository


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository

    async def list_events(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.list_events(limit, offset)

    async def get_event(self, event_id: int) -> dict[str, Any] | None:
        return await self.repository.get_event(event_id)

    async def get_event_articles(self, event_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.get_event_articles(event_id, limit, offset)
