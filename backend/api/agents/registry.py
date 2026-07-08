from __future__ import annotations

from typing import Any

from backend.api.agents.base import BaseAgent


class AgentRegistry:
    """Registry of all available specialist agents."""

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' already registered")
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[dict]:
        return [{"name": a.name, "description": a.description} for a in self._agents.values()]

    @property
    def agent_names(self) -> list[str]:
        return list(self._agents.keys())


agent_registry = AgentRegistry()
