from __future__ import annotations

from typing import Any

import httpx

from backend.api.tools.base import BaseTool, ToolParameter
from backend.shared.llm.schemas import ToolResult


class SearchArticlesTool(BaseTool):
    """Full-text search articles via Elasticsearch."""

    @property
    def name(self) -> str:
        return "search_articles"

    @property
    def description(self) -> str:
        return "Search articles by keyword using full-text search. Returns matching articles with title, source, date, sentiment, and risk level."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="query", type="string", description="Search keyword or phrase", required=True),
            ToolParameter(name="limit", type="integer", description="Max results (default 10)", required=False),
        ]

    async def execute(self, query: str, limit: int = 10, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/search/", params={"q": query, "limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"results": data, "count": len(data), "query": query})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Search failed: {e}")


class SemanticSearchTool(BaseTool):
    """Semantic search articles via embeddings."""

    @property
    def name(self) -> str:
        return "semantic_search"

    @property
    def description(self) -> str:
        return "Search articles by semantic meaning using vector embeddings. Better for conceptual queries than keyword search."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="query", type="string", description="Natural language query", required=True),
            ToolParameter(name="limit", type="integer", description="Max results (default 10)", required=False),
        ]

    async def execute(self, query: str, limit: int = 10, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/semantic-search/", params={"q": query, "limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"results": data, "count": len(data), "query": query})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Semantic search failed: {e}")


class GetEntityArticlesTool(BaseTool):
    """Get articles mentioning a specific entity."""

    @property
    def name(self) -> str:
        return "get_entity_articles"

    @property
    def description(self) -> str:
        return "Get all articles that mention a specific entity (person, organization, country, etc.)."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="entity_name", type="string", description="Name of the entity to look up", required=True),
        ]

    async def execute(self, entity_name: str, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get(f"/entities/{entity_name}/articles", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"articles": data, "entity": entity_name, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Failed to get entity articles: {e}")
