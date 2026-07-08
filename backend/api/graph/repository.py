from typing import Any

from backend.api.common.schema import record_to_dict


class GraphRepository:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def get_network(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source_entity, target_entity, relationship_type, confidence
                FROM relationships
                WHERE confidence >= 0.55
                ORDER BY confidence DESC NULLS LAST, created_at DESC
                LIMIT 250
                """
            )
        return [dict(row) for row in rows]

    async def expand_graph(self, entity: str, depth: int, limit: int) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM relationships
                WHERE LOWER(source_entity) = LOWER($1) OR LOWER(target_entity) = LOWER($1)
                ORDER BY confidence DESC NULLS LAST, created_at DESC
                LIMIT $2
                """,
                entity,
                limit * max(depth, 1),
            )

        nodes = {entity: {"id": entity, "label": entity}}
        edges = []
        for row in rows:
            source = row["source_entity"]
            target = row["target_entity"]
            nodes.setdefault(source, {"id": source, "label": source})
            nodes.setdefault(target, {"id": target, "label": target})
            edges.append(record_to_dict(row))

        return {"nodes": list(nodes.values()), "edges": edges}
