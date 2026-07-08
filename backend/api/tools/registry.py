from __future__ import annotations

from typing import Any

from backend.api.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """Global registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_openai_tools(self) -> list[dict]:
        return [t.to_openai_tool() for t in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, data={}, error=f"Tool '{name}' not found")
        return await tool.execute(**kwargs)

    def get_tools_by_agent(self, agent_name: str) -> list[BaseTool]:
        return [t for t in self._tools.values() if t.agent_owner == agent_name]

    def get_openai_tools_for_agent(self, agent_name: str) -> list[dict]:
        return [t.to_openai_tool() for t in self.get_tools_by_agent(agent_name)]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())


tool_registry = ToolRegistry()
