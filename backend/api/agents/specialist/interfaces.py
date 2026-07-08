from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.shared.llm.schemas import AgentResponse


class SpecialistAgent(ABC):
    """Interface for all specialist agents. Each agent owns its own tools and produces structured outputs."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def owned_tools(self) -> list[str]:
        """List of tool names this agent owns."""
        ...

    @abstractmethod
    async def execute(self, task: str, context: dict) -> Any:
        ...


class ResearchAgent(SpecialistAgent):
    """Gathers information from articles, entities, and search.

    Owns: search_articles, semantic_search, get_entity_articles, get_analytics_summary,
          get_entity_analytics, get_topic_analytics
    """

    @property
    def name(self) -> str:
        return "research"

    @property
    def description(self) -> str:
        return "Searches and retrieves articles, entity data, and analytics."

    @property
    def owned_tools(self) -> list[str]:
        return ["search_articles", "semantic_search", "get_entity_articles", "get_analytics_summary", "get_entity_analytics", "get_topic_analytics"]

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class ScenarioAgent(SpecialistAgent):
    """Runs digital twin simulations and impact analyses.

    Owns: get_entity_network, expand_entity_graph, get_energy_knowledge_graph, get_risk_propagation_map
    """

    @property
    def name(self) -> str:
        return "scenario"

    @property
    def description(self) -> str:
        return "Runs digital twin simulations and impact analysis."

    @property
    def owned_tools(self) -> list[str]:
        return ["get_entity_network", "expand_entity_graph", "get_energy_knowledge_graph", "get_risk_propagation_map"]

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class DecisionAgent(SpecialistAgent):
    """Runs procurement optimization and SPR analysis.

    Owns: lookup_entity, list_entities, get_entity_relationships, get_sanctions_data
    """

    @property
    def name(self) -> str:
        return "decision"

    @property
    def description(self) -> str:
        return "Runs procurement optimization and SPR decision support."

    @property
    def owned_tools(self) -> list[str]:
        return ["lookup_entity", "list_entities", "get_entity_relationships", "get_sanctions_data"]

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class PredictionAgent(SpecialistAgent):
    """Generates forecasts using ML models.

    Owns: (no REST tools — uses ML model inference)
    """

    @property
    def name(self) -> str:
        return "prediction"

    @property
    def description(self) -> str:
        return "Generates ML-powered forecasts and predictions."

    @property
    def owned_tools(self) -> list[str]:
        return []

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class ValidationAgent(SpecialistAgent):
    """Verifies claims against evidence and checks for contradictions.

    Owns: (meta-agent — no direct tools, examines other agent outputs)
    """

    @property
    def name(self) -> str:
        return "validation"

    @property
    def description(self) -> str:
        return "Verifies claims, checks contradictions, validates confidence."

    @property
    def owned_tools(self) -> list[str]:
        return []

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class ExecutiveAgent(SpecialistAgent):
    """Synthesizes multi-agent outputs into executive summaries.

    Owns: (meta-agent — no direct tools, synthesizes from others)
    """

    @property
    def name(self) -> str:
        return "executive"

    @property
    def description(self) -> str:
        return "Synthesizes multiple agent outputs into executive summaries."

    @property
    def owned_tools(self) -> list[str]:
        return []

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class SPRAgent(SpecialistAgent):
    """Strategic Petroleum Reserve analysis.

    Owns: (SPR-specific tools — future)
    """

    @property
    def name(self) -> str:
        return "spr"

    @property
    def description(self) -> str:
        return "Analyzes Strategic Petroleum Reserve inventory, capacity, and policies."

    @property
    def owned_tools(self) -> list[str]:
        return []

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class ProcurementAgent(SpecialistAgent):
    """Procurement optimization and supplier analysis.

    Owns: (procurement-specific tools — future)
    """

    @property
    def name(self) -> str:
        return "procurement"

    @property
    def description(self) -> str:
        return "Optimizes procurement across cost, risk, and quality dimensions."

    @property
    def owned_tools(self) -> list[str]:
        return []

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class KnowledgeGraphAgent(SpecialistAgent):
    """Queries entity relationships and graph topology.

    Owns: get_entity_network, expand_entity_graph, get_energy_knowledge_graph, get_risk_propagation_map,
          get_entity_relationships
    """

    @property
    def name(self) -> str:
        return "knowledge_graph"

    @property
    def description(self) -> str:
        return "Queries entity relationships, graph neighborhoods, and risk propagation."

    @property
    def owned_tools(self) -> list[str]:
        return ["get_entity_network", "expand_entity_graph", "get_energy_knowledge_graph", "get_risk_propagation_map", "get_entity_relationships"]

    async def execute(self, task: str, context: dict) -> Any:
        return {"agent": self.name, "task": task, "status": "not_implemented"}


class SpecialistAgentRegistry:
    """Registry of all specialist agents with their tool ownership."""

    def __init__(self):
        self._agents: dict[str, SpecialistAgent] = {}

    def register(self, agent: SpecialistAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Specialist agent '{agent.name}' already registered")
        self._agents[agent.name] = agent

    def get(self, name: str) -> SpecialistAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[dict]:
        return [{"name": a.name, "description": a.description, "tools": a.owned_tools} for a in self._agents.values()]

    def get_tools_for_agent(self, agent_name: str) -> list[str]:
        agent = self._agents.get(agent_name)
        return agent.owned_tools if agent else []

    def get_agent_for_tool(self, tool_name: str) -> str | None:
        for name, agent in self._agents.items():
            if tool_name in agent.owned_tools:
                return name
        return None

    @property
    def agent_names(self) -> list[str]:
        return list(self._agents.keys())


specialist_agent_registry = SpecialistAgentRegistry()

specialist_agent_registry.register(ResearchAgent())
specialist_agent_registry.register(ScenarioAgent())
specialist_agent_registry.register(DecisionAgent())
specialist_agent_registry.register(PredictionAgent())
specialist_agent_registry.register(ValidationAgent())
specialist_agent_registry.register(ExecutiveAgent())
specialist_agent_registry.register(SPRAgent())
specialist_agent_registry.register(ProcurementAgent())
specialist_agent_registry.register(KnowledgeGraphAgent())
