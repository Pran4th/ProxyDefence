from typing import Any

from fastapi import HTTPException

from backend.api.watchlists.repository import WatchlistRepository


class WatchlistService:
    def __init__(self, repository: WatchlistRepository) -> None:
        self.repository = repository

    def ensure_access(self, watchlist: dict, current_user: dict) -> None:
        if current_user.get("role") == "admin":
            return
        if watchlist.get("owner_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Watchlist access denied")

    async def list_watchlists(self, owner_id: int | None, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.list_watchlists(owner_id, limit, offset)

    async def get_watchlist(self, watchlist_id: int) -> dict[str, Any] | None:
        return await self.repository.get_watchlist(watchlist_id)

    async def create_watchlist(self, name: str, description: str | None, owner_id: int | None, entities: list[str]) -> dict[str, Any]:
        return await self.repository.create_watchlist(name, description, owner_id, entities)

    async def delete_watchlist(self, watchlist_id: int) -> dict[str, Any]:
        return await self.repository.delete_watchlist(watchlist_id)

    async def add_watchlist_entity(self, watchlist_id: int, entity_text: str) -> list[str]:
        return await self.repository.add_watchlist_entity(watchlist_id, entity_text)

    async def remove_watchlist_entity(self, watchlist_id: int, entity_text: str) -> list[str]:
        return await self.repository.remove_watchlist_entity(watchlist_id, entity_text)
