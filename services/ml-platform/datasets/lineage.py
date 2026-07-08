from __future__ import annotations

from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DatasetLineage:
    async def get_lineage_graph(self, name: str, version: int, depth: int = 5) -> dict[str, Any]:
        return {"name": name, "version": version, "depth": depth, "nodes": [], "edges": []}

    async def get_parents(self, name: str, version: int) -> list[dict[str, Any]]:
        return []

    async def get_children(self, name: str, version: int) -> list[dict[str, Any]]:
        return []


class DatasetProvenance:
    async def get_source_tree(self, name: str, version: int) -> dict[str, Any]:
        return {"name": name, "version": version, "sources": []}
