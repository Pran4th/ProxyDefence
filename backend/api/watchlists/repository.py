from typing import Any

from backend.api.common.schema import record_to_dict


class WatchlistRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def create_watchlist(
        self, name: str, description: str | None, owner_id: int | None, entities: list[str]
    ) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                watchlist = await conn.fetchrow(
                    """
                    INSERT INTO watchlists (name, description, owner_id)
                    VALUES ($1, $2, $3)
                    RETURNING *
                    """,
                    name,
                    description,
                    owner_id,
                )
                for entity in entities:
                    await conn.execute(
                        """
                        INSERT INTO watchlist_entities (watchlist_id, entity_text)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        watchlist["id"],
                        entity.strip(),
                    )
                rows = await conn.fetch(
                    "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                    watchlist["id"],
                )

        payload = record_to_dict(watchlist)
        payload["entities"] = [row["entity_text"] for row in rows]
        return payload

    async def list_watchlists(self, owner_id: int | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT w.*, ARRAY_REMOVE(ARRAY_AGG(we.entity_text ORDER BY we.entity_text), NULL) AS entities
                FROM watchlists w
                LEFT JOIN watchlist_entities we ON we.watchlist_id = w.id
                WHERE ($1::int IS NULL OR w.owner_id = $1)
                GROUP BY w.id
                ORDER BY w.updated_at DESC
                LIMIT $2 OFFSET $3
                """,
                owner_id,
                limit,
                offset,
            )
        return [record_to_dict(row) for row in rows]

    async def get_watchlist(self, watchlist_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            watchlist = await conn.fetchrow("SELECT * FROM watchlists WHERE id = $1", watchlist_id)
            if watchlist is None:
                return None
            entities = await conn.fetch(
                "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                watchlist_id,
            )
        payload = record_to_dict(watchlist)
        payload["entities"] = [row["entity_text"] for row in entities]
        return payload

    async def delete_watchlist(self, watchlist_id: int) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("DELETE FROM watchlists WHERE id = $1 RETURNING id", watchlist_id)
        deleted = result is not None
        return {"deleted": deleted, "watchlist_id": watchlist_id}

    async def add_watchlist_entity(self, watchlist_id: int, entity_text: str) -> list[str]:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO watchlist_entities (watchlist_id, entity_text)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                watchlist_id,
                entity_text.strip(),
            )
            rows = await conn.fetch(
                "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                watchlist_id,
            )
        return [row["entity_text"] for row in rows]

    async def remove_watchlist_entity(self, watchlist_id: int, entity_text: str) -> list[str]:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM watchlist_entities WHERE watchlist_id = $1 AND entity_text = $2",
                watchlist_id,
                entity_text.strip(),
            )
            rows = await conn.fetch(
                "SELECT entity_text FROM watchlist_entities WHERE watchlist_id = $1 ORDER BY entity_text",
                watchlist_id,
            )
        return [row["entity_text"] for row in rows]
