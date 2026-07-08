from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from backend.api.agents.base import BaseAgent
from backend.api.tools.registry import tool_registry
from backend.shared.llm.memory import memory_store
from backend.shared.llm.prompts import PromptLibrary, SYSTEM_PROMPTS
from backend.shared.llm.schemas import AgentContext, AgentResponse, Citation, ToolCall, ToolResult
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class IntelligenceAgent(BaseAgent):
    """Specialist agent for geopolitical threat assessment, entity research, and risk explanation."""

    def __init__(self, llm_client=None):
        super().__init__(llm_client)
        self._conversation_id: str | None = None

    @property
    def name(self) -> str:
        return "intelligence"

    @property
    def description(self) -> str:
        return "Geopolitical intelligence analyst that assesses threats, researches entities, explains risks, and identifies connections between events and infrastructure."

    def set_conversation(self, conversation_id: str) -> None:
        self._conversation_id = conversation_id

    async def _execute(self, query: str) -> AgentResponse:
        conversation_id = self._conversation_id or "default"
        memory = memory_store.get_or_create(conversation_id)
        memory.add_user_message(query)

        tools = self._get_intelligence_tools()
        messages = memory.to_openai_messages(system_prompt=SYSTEM_PROMPTS["intelligence"])

        content, tool_calls, metrics = await self._llm.chat(
            messages=messages,
            tools=tools,
        )

        citations: list[Citation] = []
        tool_results: list[ToolResult] = []

        if tool_calls:
            for tc in tool_calls:
                result = await tool_registry.execute(tc.name, **(tc.arguments or {}))
                tool_results.append(result)
                memory.add_tool_result(tc.name, tc.id, result.success, result.data if result.success else (result.error or ""))
                if result.success and result.citation:
                    citations.append(result.citation)

            messages_with_results = memory.to_openai_messages(system_prompt=SYSTEM_PROMPTS["intelligence"])
            content, _, metrics = await self._llm.chat(messages=messages_with_results)

        response = AgentResponse(
            answer=content,
            citations=citations if citations else [],
            confidence=self._compute_confidence(tool_results),
            tool_executions=[
                {"tool_name": r.tool_name, "success": r.success, "output": r.output, "error": r.error}
                for r in (tool_results or [])
            ],
            agent_chain=[self.name],
        )

        memory.add_assistant_message(content, citations=citations if citations else None)
        return response

    async def _execute_stream(self, query: str) -> AsyncGenerator[dict, None]:
        conversation_id = self._conversation_id or "default"
        memory = memory_store.get_or_create(conversation_id)
        memory.add_user_message(query)

        tools = self._get_intelligence_tools()
        messages = memory.to_openai_messages(system_prompt=SYSTEM_PROMPTS["intelligence"])

        yield {"type": "agent_status", "agent": self.name, "status": "gathering_intelligence", "message": "Gathering intelligence data..."}

        collected_tokens: list[str] = []
        collected_tool_calls: list[ToolCall] = []

        async def on_token(token: str) -> None:
            collected_tokens.append(token)

        async def on_tool_call(tc: ToolCall) -> None:
            collected_tool_calls.append(tc)
            yield {"type": "tool_call", "name": tc.name, "arguments": tc.arguments or {}}

        content, tool_calls, metrics = await self._llm.chat(
            messages=messages,
            tools=tools,
            stream=True,
            on_token=on_token,
            on_tool_call=on_tool_call,
        )

        citations: list[Citation] = []
        tool_results: list[ToolResult] = []

        if collected_tool_calls:
            yield {"type": "agent_status", "agent": self.name, "status": "analyzing", "message": f"Analyzing {len(collected_tool_calls)} data sources..."}
            for tc in collected_tool_calls:
                result = await tool_registry.execute(tc.name, **(tc.arguments or {}))
                tool_results.append(result)
                memory.add_tool_result(tc.name, tc.id, result.success, result.data if result.success else (result.error or ""))
                if result.success and result.citation:
                    citations.append(result.citation)
                yield {"type": "tool_result", "name": tc.name, "success": result.success, "summary": str(result.data)[:200] if result.success else (result.error or "")}

            yield {"type": "agent_status", "agent": self.name, "status": "formulating_assessment", "message": "Formulating threat assessment..."}
            messages_with_results = memory.to_openai_messages(system_prompt=SYSTEM_PROMPTS["intelligence"])
            content_parts: list[str] = []
            async def on_final_token(token: str) -> None:
                content_parts.append(token)
                yield {"type": "token", "value": token}

            content, _, metrics = await self._llm.chat(messages=messages_with_results, stream=True, on_token=on_final_token)

        yield {"type": "token", "value": content}
        for c in citations:
            yield {"type": "citation", "source_id": c.source_id, "source_type": c.source_type, "title": c.title, "relevance": c.relevance}
        yield {"type": "confidence", "score": self._compute_confidence(tool_results)}
        yield {"type": "metadata", "value": {"agent": self.name, "conversation_id": conversation_id, "llm_metrics": metrics}}

        memory.add_assistant_message(content, citations=citations if citations else None)

    def _get_intelligence_tools(self) -> list[dict]:
        tool_names = [
            "get_risk_dashboard",
            "get_active_signals",
            "search_articles",
            "semantic_search",
            "get_entity_articles",
            "get_entity_risk_profile",
            "get_risk_trends",
            "get_threat_trends",
            "get_commodity_prices",
            "get_alerts",
            "get_events",
            "get_entity_network",
            "expand_entity_graph",
            "get_risk_propagation_map",
            "lookup_entity",
            "list_entities",
            "get_port_congestion",
            "get_tanker_availability",
            "get_sanctions_data",
        ]
        return [tool_registry.get(name).to_openai_tool() for name in tool_names if tool_registry.get(name)]

    def _compute_confidence(self, tool_results: list[ToolResult]) -> float:
        if not tool_results:
            return 0.5
        success_count = sum(1 for r in tool_results if r.success)
        return round(success_count / len(tool_results), 2)
