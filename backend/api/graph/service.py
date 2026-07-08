from typing import Any

from backend.api.graph.repository import GraphRepository
from backend.shared.entity_normalization import normalize_entity, is_blacklisted_entity


class GraphService:
    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository

    async def get_network(self) -> dict[str, Any]:
        rows = await self.repository.get_network()

        nodes = {}
        edges = []
        seen_edges = set()

        for row in rows:
            source = normalize_entity(row["source_entity"])
            target = normalize_entity(row["target_entity"])

            if is_blacklisted_entity(source) or is_blacklisted_entity(target):
                continue
            if source == target:
                continue

            edge_key = (source, target, row["relationship_type"])
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            nodes.setdefault(source, {"id": source, "label": source})
            nodes.setdefault(target, {"id": target, "label": target})

            edges.append({
                "source": source,
                "target": target,
                "relationship": row["relationship_type"],
                "confidence": float(row["confidence"] or 0),
            })

        return {"node_count": len(nodes), "edge_count": len(edges), "nodes": list(nodes.values()), "edges": edges}

    async def expand_graph(self, entity: str, depth: int, limit: int) -> dict[str, Any]:
        return await self.repository.expand_graph(entity, depth, limit)
