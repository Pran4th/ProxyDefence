from __future__ import annotations

from typing import Any

import httpx

from backend.api.tools.base import BaseTool, ToolParameter
from backend.shared.llm.schemas import ToolResult


class GetAnalyticsSummaryTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_analytics_summary"

    @property
    def description(self) -> str:
        return "Get an analytics summary of the defense intelligence platform including article counts, sentiment breakdown, and key metrics."

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/analytics/summary", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Analytics summary failed: {e}")


class GetEntityAnalyticsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_entity_analytics"

    @property
    def description(self) -> str:
        return "Get top entity analytics showing entities most frequently mentioned in articles ranked by mention count."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/analytics/entities", params={"limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"entities": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Entity analytics failed: {e}")


class GetTopicAnalyticsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_topic_analytics"

    @property
    def description(self) -> str:
        return "Get topic breakdown analytics showing what topics/themes are most prevalent in recent articles."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/analytics/topics", params={"limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"topics": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Topic analytics failed: {e}")


class GetDashboardStatsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_dashboard_stats"

    @property
    def description(self) -> str:
        return "Get the main dashboard statistics for the defense intelligence platform."

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/analytics/dashboard", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Dashboard stats failed: {e}")
