from typing import Any

from backend.api.analytics.repository import AnalyticsRepository


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    async def get_dashboard_stats(self) -> dict[str, Any]:
        return await self.repository.get_dashboard_stats()

    async def get_threat_trends(self) -> dict:
        return await self.repository.get_threat_analytics()

    async def get_summary(self) -> dict[str, Any]:
        return await self.repository.get_summary()

    async def get_attack_graph(self) -> dict[str, Any]:
        return await self.repository.get_attack_graph()

    async def get_timeseries(self) -> list[dict[str, Any]]:
        return await self.repository.get_timeseries()

    async def get_top_entities(self) -> list[dict[str, Any]]:
        return await self.repository.get_top_entities()

    async def get_top_events(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self.repository.get_top_events(limit)

    async def get_topic_breakdown(self) -> list[dict[str, Any]]:
        return await self.repository.get_topic_breakdown()
