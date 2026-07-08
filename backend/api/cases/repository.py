from typing import Any

from backend.api.common.schema import record_to_dict


class CaseRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def create_case(
        self, title: str, description: str | None, owner_id: int | None, priority: str = "medium"
    ) -> dict[str, Any]:
        allowed_priorities = {"low", "medium", "high", "critical"}
        if priority not in allowed_priorities:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {allowed_priorities}")

        async with self.pool.acquire() as conn:
            case = await conn.fetchrow(
                """
                INSERT INTO cases (title, description, owner_id, priority)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                title,
                description,
                owner_id,
                priority,
            )
        return record_to_dict(case)

    async def get_case(self, case_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            case = await conn.fetchrow("SELECT * FROM cases WHERE id = $1", case_id)
            if case is None:
                return None

            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

            notes = await conn.fetch(
                """
                SELECT * FROM case_notes
                WHERE case_id = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                case_id,
            )

            notes_count = await conn.fetchval(
                "SELECT COUNT(*) FROM case_notes WHERE case_id = $1",
                case_id,
            )

        payload = record_to_dict(case)
        payload["items"] = [record_to_dict(row) for row in items]
        payload["notes"] = [record_to_dict(row) for row in notes]
        payload["notes_count"] = notes_count
        return payload

    async def list_cases(
        self, owner_id: int | None = None, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.*,
                    COUNT(DISTINCT ci.item_id) AS item_count,
                    COUNT(DISTINCT cn.id) AS notes_count
                FROM cases c
                LEFT JOIN case_items ci ON ci.case_id = c.id
                LEFT JOIN case_notes cn ON cn.case_id = c.id
                WHERE ($1::int IS NULL OR c.owner_id = $1)
                    AND ($2::varchar IS NULL OR c.status = $2)
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT $3 OFFSET $4
                """,
                owner_id,
                status,
                limit,
                offset,
            )
        return [record_to_dict(row) for row in rows]

    async def add_case_item(self, case_id: int, item_type: str, item_id: int) -> dict[str, Any]:
        allowed_types = {"alert", "event", "article", "entity"}
        if item_type not in allowed_types:
            raise ValueError(f"Invalid item_type: {item_type}. Must be one of {allowed_types}")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO case_items (case_id, item_type, item_id)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                case_id,
                item_type,
                item_id,
            )
            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

        return {"case_id": case_id, "items": [record_to_dict(row) for row in items]}

    async def remove_case_item(self, case_id: int, item_type: str, item_id: int) -> dict[str, Any]:
        allowed_types = {"alert", "event", "article", "entity"}
        if item_type not in allowed_types:
            raise ValueError(f"Invalid item_type: {item_type}. Must be one of {allowed_types}")

        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM case_items WHERE case_id = $1 AND item_type = $2 AND item_id = $3",
                case_id,
                item_type,
                item_id,
            )
            items = await conn.fetch(
                """
                SELECT item_type, item_id, created_at
                FROM case_items WHERE case_id = $1
                ORDER BY created_at DESC
                """,
                case_id,
            )

        return {"case_id": case_id, "items": [record_to_dict(row) for row in items]}

    async def add_case_note(self, case_id: int, note_text: str, created_by: int | None) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            note = await conn.fetchrow(
                """
                INSERT INTO case_notes (case_id, note_text, created_by)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                case_id,
                note_text,
                created_by,
            )
        return record_to_dict(note)

    async def list_case_notes(self, case_id: int, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM case_notes
                WHERE case_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                case_id,
                limit,
                offset,
            )
        return [record_to_dict(row) for row in rows]
