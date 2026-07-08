from collections.abc import AsyncGenerator
from typing import Any

from backend.api.agents.intelligence import IntelligenceAgent
from backend.api.agents.registry import agent_registry
from backend.api.copilot.repository import CopilotRepository
from backend.shared.llm.memory import memory_store
from backend.shared.llm.schemas import AgentResponse
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class CopilotService:
    """LLM-powered Copilot service that delegates to the Intelligence Agent."""

    def __init__(self, repository: CopilotRepository) -> None:
        self.repository = repository

    async def query(self, question: str, conversation_id: int | None = None) -> dict:
        agent = IntelligenceAgent()
        conv_str = str(conversation_id) if conversation_id is not None else None
        if conv_str:
            agent.set_conversation(conv_str)

        response = await agent.run(question)

        if conversation_id:
            await self.repository.add_message(conversation_id, "user", question)
            await self.repository.add_message(conversation_id, "assistant", response.answer)

        return {
            "question": question,
            "conversation_id": conversation_id,
            "summary": response.answer,
            "citations": [c.model_dump() for c in response.citations],
            "confidence": response.confidence,
            "tool_calls": response.tool_executions,
            "agent_name": response.agent_chain[0] if response.agent_chain else "intelligence",
            "llm_metrics": {"tokens_used": response.tokens_used, "latency_ms": response.latency_ms, "estimated_cost": response.estimated_cost},
        }

    async def query_stream(self, question: str, conversation_id: int | None = None) -> AsyncGenerator[str, None]:
        agent = IntelligenceAgent()
        conv_str = str(conversation_id) if conversation_id is not None else None
        if conv_str:
            agent.set_conversation(conv_str)

        collected_parts: list[str] = []

        async for event in agent.run_stream(question):
            event_type = event.get("type")
            value = event.get("value") if "value" in event else event
            yield f"data: {__import__('json').dumps({'type': event_type, 'value': value})}\n\n"
            if event_type == "token":
                collected_parts.append(value)

        full_content = "".join(collected_parts)
        if conversation_id and full_content:
            await self.repository.add_message(conversation_id, "user", question)
            await self.repository.add_message(conversation_id, "assistant", full_content)

        if collected_parts:
            yield f"data: {{\"type\":\"done\"}}\n\n"
