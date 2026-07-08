from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from backend.shared.llm.client import LLMClient
from backend.shared.llm.schemas import AgentContext, AgentResponse, Citation, ToolCall, ToolResult


class BaseAgent(ABC):
    """Base class for all specialist agents."""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client or LLMClient()
        self._context: AgentContext | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    async def run(self, query: str, context: AgentContext | None = None) -> AgentResponse:
        self._context = context
        result = await self._execute(query)
        return result

    async def run_stream(self, query: str, context: AgentContext | None = None) -> AsyncGenerator[dict, None]:
        self._context = context
        async for event in self._execute_stream(query):
            yield event

    @abstractmethod
    async def _execute(self, query: str) -> AgentResponse:
        ...

    async def _execute_stream(self, query: str) -> AsyncGenerator[dict, None]:
        response = await self._execute(query)
        yield {"type": "token", "value": response.answer}
        for c in response.citations:
            yield {"type": "citation", "source_id": c.source_id, "source_type": c.source_type, "title": c.title, "relevance": c.relevance}
        yield {"type": "confidence", "score": response.confidence}
