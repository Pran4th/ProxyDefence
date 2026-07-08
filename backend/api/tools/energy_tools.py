from __future__ import annotations

from typing import Any

import httpx

from backend.api.tools.base import BaseTool, ToolParameter
from backend.shared.llm.schemas import ToolResult


class LookupEntityTool(BaseTool):
    """Look up any energy entity by table type and UUID."""

    @property
    def name(self) -> str:
        return "lookup_entity"

    @property
    def description(self) -> str:
        return "Look up a specific energy infrastructure entity by type and UUID. Returns full entity details including location, status, capacity, and criticality."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="entity_type", type="string", description="Entity type: ports, refineries, pipelines, oil_fields, gas_fields, suppliers, power_plants, storage_facilities, strategic_petroleum_reserves, shipping_routes, import_corridors, locations, organizations, commodities", required=True),
            ToolParameter(name="entity_uuid", type="string", description="UUID of the entity", required=True),
        ]

    async def execute(self, entity_type: str, entity_uuid: str, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get(f"/api/v1/energy/{entity_type}/{entity_uuid}", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data=data)
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Entity lookup failed: {e}")


class ListEntitiesTool(BaseTool):
    """List entities of a given type with search/sort/filter."""

    @property
    def name(self) -> str:
        return "list_entities"

    @property
    def description(self) -> str:
        return "List energy infrastructure entities of a specific type with optional search, sort, status, criticality, and location filters."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="entity_type", type="string", description="Entity type: ports, refineries, pipelines, oil_fields, gas_fields, suppliers, power_plants, storage_facilities, strategic_petroleum_reserves, shipping_routes, import_corridors, locations, organizations, commodities", required=True),
            ToolParameter(name="search", type="string", description="Search term to filter by name", required=False),
            ToolParameter(name="status", type="string", description="Filter by operational status", required=False),
            ToolParameter(name="criticality", type="string", description="Filter by criticality: critical, high, medium, low", required=False),
            ToolParameter(name="location", type="string", description="Filter by location/country", required=False),
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, entity_type: str, search: str | None = None, status: str | None = None, criticality: str | None = None, location: str | None = None, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                params: dict = {"limit": limit}
                if search:
                    params["search"] = search
                if status:
                    params["status"] = status
                if criticality:
                    params["criticality"] = criticality
                if location:
                    params["location"] = location
                resp = await client.get(f"/api/v1/energy/{entity_type}", params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"results": data, "count": len(data), "entity_type": entity_type})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"List entities failed: {e}")


class GetEntityRelationshipsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_entity_relationships"

    @property
    def description(self) -> str:
        return "Get all relationships for a specific energy entity (e.g., which ports a refinery imports from, which pipelines connect to a storage facility)."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="entity_type", type="string", description="Entity type", required=True),
            ToolParameter(name="entity_uuid", type="string", description="UUID of the entity", required=True),
        ]

    async def execute(self, entity_type: str, entity_uuid: str, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get(f"/api/v1/energy/{entity_type}/{entity_uuid}/relationships", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"relationships": data, "entity_uuid": entity_uuid})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Entity relationships failed: {e}")


class GetPortCongestionTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_port_congestion"

    @property
    def description(self) -> str:
        return "Get current port congestion data showing wait times, berth availability, and traffic levels at major ports."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="port", type="string", description="Optional port name to filter by", required=False),
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, port: str | None = None, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                params: dict = {"limit": limit}
                if port:
                    params["port"] = port
                resp = await client.get("/api/v1/intelligence/port-congestion", params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"port_congestion": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Port congestion failed: {e}")


class GetTankerAvailabilityTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_tanker_availability"

    @property
    def description(self) -> str:
        return "Get current tanker availability data including fleet status, rates, and vessel counts."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/api/v1/intelligence/tanker-availability", params={"limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"tanker_availability": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Tanker availability failed: {e}")


class GetSanctionsDataTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_sanctions_data"

    @property
    def description(self) -> str:
        return "Get current sanctions records that may affect energy trade, shipping, or supply chains."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="limit", type="integer", description="Max results (default 20)", required=False),
        ]

    async def execute(self, limit: int = 20, **kwargs: Any) -> ToolResult:
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                resp = await client.get("/api/v1/intelligence/sanctions", params={"limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return ToolResult(success=True, data={"sanctions": data, "count": len(data)})
            except Exception as e:
                return ToolResult(success=False, data={}, error=f"Sanctions data failed: {e}")
