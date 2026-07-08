from __future__ import annotations

from typing import Any

import httpx

from backend.api.tools.base import BaseTool, ToolParameter
from backend.shared.llm.schemas import ToolResult


class GetEntityNetworkTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_entity_network"

    @property
    def description(self) -> str:
        return "Get the full entity relationship network showing connections between entities, threat actors, regions, and infrastructure."

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/graph/network", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Entity network failed: {e}")


class ExpandEntityGraphTool(BaseTool):
    @property
    def name(self) -> str:
        return "expand_entity_graph"

    @property
    def description(self) -> str:
        return "Expand the knowledge graph for a specific entity, showing its relationships, connected entities, and network neighborhood."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="entity_name", type="string", description="Name of the entity to expand", required=True),
            ToolParameter(name="depth", type="integer", description="Depth of graph expansion (default 2)", required=False),
            ToolParameter(name="limit", type="integer", description="Max related entities (default 20)", required=False),
        ]

    async def execute(self, entity_name: str, depth: int = 2, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get(f"/graph/{entity_name}", params={"depth": depth, "limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Entity graph expansion failed: {e}")


class GetKnowledgeGraphNetworkTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_energy_knowledge_graph"

    @property
    def description(self) -> str:
        return "Get the full energy infrastructure knowledge graph showing all relationships between energy entities (ports, refineries, pipelines, fields, etc.)."

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/api/v1/energy/graph/network", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Knowledge graph failed: {e}")


class GetRiskPropagationMapTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_risk_propagation_map"

    @property
    def description(self) -> str:
        return "Get the risk propagation map showing how risk propagates through the knowledge graph from source entities to connected entities."

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/api/v1/intelligence/propagation-map", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Risk propagation map failed: {e}")
