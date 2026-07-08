from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from backend.shared.llm.schemas import ToolResult


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = False


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter]


class BaseTool(ABC):
    """Base class for all LLM-callable tools."""

    def __init__(self):
        self._name: str = ""
        self._agent_owner: str = ""

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
    def parameters(self) -> list[ToolParameter]:
        ...

    @property
    def agent_owner(self) -> str:
        return self._agent_owner

    @agent_owner.setter
    def agent_owner(self, owner: str) -> None:
        self._agent_owner = owner

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        ...

    def to_openai_tool(self) -> dict:
        props: dict = {}
        required: list[str] = []
        for p in self.parameters:
            props[p.name] = {"type": p.type, "description": p.description}
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }
