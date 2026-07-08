from backend.api.tools.base import BaseTool
from backend.api.tools.registry import ToolRegistry, tool_registry
from backend.api.tools.search_tools import SearchArticlesTool, SemanticSearchTool, GetEntityArticlesTool
from backend.api.tools.intelligence_tools import (
    GetRiskDashboardTool,
    GetActiveSignalsTool,
    GetEntityRiskProfileTool,
    GetRiskTrendsTool,
    GetCommodityPricesTool,
    GetAlertsTool,
    GetEventsTool,
    GetThreatTrendsTool,
)
from backend.api.tools.energy_tools import (
    LookupEntityTool,
    ListEntitiesTool,
    GetEntityRelationshipsTool,
    GetPortCongestionTool,
    GetTankerAvailabilityTool,
    GetSanctionsDataTool,
)
from backend.api.tools.analytics_tools import GetAnalyticsSummaryTool, GetEntityAnalyticsTool, GetTopicAnalyticsTool, GetDashboardStatsTool
from backend.api.tools.graph_tools import GetEntityNetworkTool, ExpandEntityGraphTool, GetKnowledgeGraphNetworkTool, GetRiskPropagationMapTool


def _set_owner(tool: BaseTool, owner: str) -> BaseTool:
    tool.agent_owner = owner
    return tool


def register_all_tools() -> ToolRegistry:
    tool_defs = [
        (SearchArticlesTool(), "research"),
        (SemanticSearchTool(), "research"),
        (GetEntityArticlesTool(), "research"),
        (GetRiskDashboardTool(), "research"),
        (GetActiveSignalsTool(), "research"),
        (GetEntityRiskProfileTool(), "research"),
        (GetRiskTrendsTool(), "research"),
        (GetCommodityPricesTool(), "research"),
        (GetAlertsTool(), "research"),
        (GetEventsTool(), "research"),
        (GetThreatTrendsTool(), "research"),
        (LookupEntityTool(), "decision"),
        (ListEntitiesTool(), "decision"),
        (GetEntityRelationshipsTool(), "knowledge_graph"),
        (GetPortCongestionTool(), "research"),
        (GetTankerAvailabilityTool(), "research"),
        (GetSanctionsDataTool(), "decision"),
        (GetAnalyticsSummaryTool(), "research"),
        (GetEntityAnalyticsTool(), "research"),
        (GetTopicAnalyticsTool(), "research"),
        (GetDashboardStatsTool(), "research"),
        (GetEntityNetworkTool(), "knowledge_graph"),
        (ExpandEntityGraphTool(), "knowledge_graph"),
        (GetKnowledgeGraphNetworkTool(), "knowledge_graph"),
        (GetRiskPropagationMapTool(), "knowledge_graph"),
    ]
    for tool, owner in tool_defs:
        _set_owner(tool, owner)
        tool_registry.register(tool)
    return tool_registry


__all__ = [
    "BaseTool",
    "ToolRegistry",
    "tool_registry",
    "register_all_tools",
    "SearchArticlesTool",
    "SemanticSearchTool",
    "GetEntityArticlesTool",
    "GetRiskDashboardTool",
    "GetActiveSignalsTool",
    "GetEntityRiskProfileTool",
    "GetRiskTrendsTool",
    "GetCommodityPricesTool",
    "GetAlertsTool",
    "GetEventsTool",
    "GetThreatTrendsTool",
    "LookupEntityTool",
    "ListEntitiesTool",
    "GetEntityRelationshipsTool",
    "GetPortCongestionTool",
    "GetTankerAvailabilityTool",
    "GetSanctionsDataTool",
    "GetAnalyticsSummaryTool",
    "GetEntityAnalyticsTool",
    "GetTopicAnalyticsTool",
    "GetDashboardStatsTool",
    "GetEntityNetworkTool",
    "ExpandEntityGraphTool",
    "GetKnowledgeGraphNetworkTool",
    "GetRiskPropagationMapTool",
]
