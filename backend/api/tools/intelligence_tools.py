from __future__ import annotations

from typing import Any

import httpx

from backend.api.tools.base import BaseTool, ToolParameter
from backend.shared.llm.schemas import ToolResult


class GetRiskDashboardTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_risk_dashboard"

    @property
    def description(self) -> str:
        return "Get the current risk dashboard showing aggregated risk scores across all dimensions (geopolitical, supply, operational, financial, regulatory, environmental)."

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/api/v1/intelligence/risk", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Risk dashboard failed: {e}")


class GetActiveSignalsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_active_signals"

    @property
    def description(self) -> str:
        return "List active disruption signals with optional severity and risk dimension filters."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="severity", type="string", description="Filter by severity: critical, high, medium, low", required=False),
            ToolParameter(name="risk_dimension", type="string", description="Filter by dimension: geopolitical, supply, operational, financial, regulatory, environmental", required=False),
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, severity: str | None = None, risk_dimension: str | None = None, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                params: dict = {"limit": limit}
                if severity:
                    params["severity"] = severity
                if risk_dimension:
                    params["risk_dimension"] = risk_dimension
                resp = await client.get("/api/v1/intelligence/signals", params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"signals": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Active signals failed: {e}")


class GetEntityRiskProfileTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_entity_risk_profile"

    @property
    def description(self) -> str:
        return "Get a full risk profile for a specific energy entity including risk scores, active signals, and related risks."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="entity_table", type="string", description="Entity type (ports, refineries, pipelines, oil_fields, gas_fields, suppliers, power_plants, storage_facilities, shipping_routes)", required=True),
            ToolParameter(name="entity_uuid", type="string", description="UUID of the entity", required=True),
        ]

    async def execute(self, entity_table: str, entity_uuid: str, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get(f"/api/v1/intelligence/entity/{entity_table}/{entity_uuid}/risk-profile", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Entity risk profile failed: {e}")


class GetRiskTrendsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_risk_trends"

    @property
    def description(self) -> str:
        return "Get risk score trends over time, optionally filtered by entity or risk dimension."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="entity_id", type="string", description="Optional entity UUID to filter by", required=False),
            ToolParameter(name="risk_dimension", type="string", description="Risk dimension to filter by", required=False),
            ToolParameter(name="days", type="integer", description="Number of days of history (default 30)", required=False),
        ]

    async def execute(self, entity_id: str | None = None, risk_dimension: str | None = None, days: int = 30, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                params: dict = {"days": days}
                if entity_id:
                    params["entity_id"] = entity_id
                if risk_dimension:
                    params["risk_dimension"] = risk_dimension
                resp = await client.get("/api/v1/intelligence/risk/trends", params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Risk trends failed: {e}")


class GetCommodityPricesTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_commodity_prices"

    @property
    def description(self) -> str:
        return "Get recent commodity price records for crude oil, natural gas, petroleum products, etc."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="commodity", type="string", description="Optional commodity name or type to filter by", required=False),
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, commodity: str | None = None, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                params: dict = {"limit": limit}
                if commodity:
                    params["commodity"] = commodity
                resp = await client.get("/api/v1/intelligence/commodity-prices", params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"prices": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Commodity prices failed: {e}")


class GetAlertsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_alerts"

    @property
    def description(self) -> str:
        return "List current alerts with optional status filter. Alerts are system-generated notifications about threats, risks, or important events."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="status", type="string", description="Filter by status: active, acknowledged, resolved", required=False),
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, status: str | None = None, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                params: dict = {"limit": limit}
                if status:
                    params["status"] = status
                resp = await client.get("/alerts/", params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"alerts": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Alerts failed: {e}")


class GetEventsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_events"

    @property
    def description(self) -> str:
        return "List intelligence events with pagination. Events are geopolitical or operational incidents that may impact energy supply chains."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
            ToolParameter(name="offset", type="integer", description="Offset for pagination", required=False),
        ]

    async def execute(self, limit: int = 20, offset: int = 0, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/events/", params={"limit": limit, "offset": offset}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"events": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Events failed: {e}")


class GetThreatTrendsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_threat_trends"

    @property
    def description(self) -> str:
        return "Get threat trend data showing how threat levels have changed over time."

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/analytics/threat-trends", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Threat trends failed: {e}")
