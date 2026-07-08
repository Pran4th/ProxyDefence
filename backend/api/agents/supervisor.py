from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from backend.api.agents.base import BaseAgent
from backend.api.agents.intelligence import IntelligenceAgent
from backend.api.agents.specialist.interfaces import specialist_agent_registry
from backend.api.tools.registry import tool_registry
from backend.shared.llm.memory import memory_store
from backend.shared.llm.schemas import AgentContext, AgentResponse
from backend.shared.orchestration.engine import ExecutionEngine
from backend.shared.orchestration.planner import Planner
from backend.shared.orchestration.reflection import ReflectionEngine
from backend.shared.orchestration.router import AgentRouter
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class SupervisorAgent(BaseAgent):
    """Orchestrator agent. Delegates to Planner → AgentRouter → Reflection → Confidence → Answer.

    Kept intentionally thin. All orchestration logic lives in backend/shared/orchestration/.
    """

    def __init__(self, llm_client=None):
        super().__init__(llm_client)
        self._conversation_id: str | None = None
        self._engine = self._build_engine()

    def _build_engine(self) -> ExecutionEngine:
        planner = Planner(llm_client=self._llm)
        router = AgentRouter()
        reflection = ReflectionEngine(llm_client=self._llm)

        intelligence = IntelligenceAgent(llm_client=self._llm)

        async def research_handler(task: str, context: dict) -> Any:
            return await self._agent_handler(task, context, intelligence)

        async def scenario_handler(task: str, context: dict) -> Any:
            return await self._agent_handler(task, context, intelligence)

        async def decision_handler(task: str, context: dict) -> Any:
            return await self._agent_handler(task, context, intelligence)

        async def prediction_handler(task: str, context: dict) -> Any:
            return {"agent": "prediction", "status": "not_implemented", "task": task}

        async def validation_handler(task: str, context: dict) -> Any:
            return {"agent": "validation", "status": "not_implemented", "task": task}

        async def executive_handler(task: str, context: dict) -> Any:
            return {"agent": "executive", "status": "not_implemented", "task": task}

        async def spr_handler(task: str, context: dict) -> Any:
            return {"agent": "spr", "status": "not_implemented", "task": task}

        async def procurement_handler(task: str, context: dict) -> Any:
            return {"agent": "procurement", "status": "not_implemented", "task": task}

        async def knowledge_graph_handler(task: str, context: dict) -> Any:
            return await self._agent_handler(task, context, intelligence)

        router.register_agent("research", research_handler)
        router.register_agent("scenario", scenario_handler)
        router.register_agent("decision", decision_handler)
        router.register_agent("prediction", prediction_handler)
        router.register_agent("validation", validation_handler)
        router.register_agent("executive", executive_handler)
        router.register_agent("spr", spr_handler)
        router.register_agent("procurement", procurement_handler)
        router.register_agent("knowledge_graph", knowledge_graph_handler)

        return ExecutionEngine(planner=planner, router=router, reflection=reflection)

    @property
    def name(self) -> str:
        return "supervisor"

    @property
    def description(self) -> str:
        return "Orchestrator that plans, routes to specialist agents, reflects, and returns executive responses."

    def set_conversation(self, conversation_id: str) -> None:
        self._conversation_id = conversation_id

    async def _execute(self, query: str) -> AgentResponse:
        conversation_id = self._conversation_id or "default"
        memory = memory_store.get_or_create(conversation_id)
        history = memory.to_openai_messages()
        response = await self._engine.execute(query, conversation_history=history)
        memory.add_assistant_message(response.answer, citations=response.citations)
        return response

    async def _execute_stream(self, query: str) -> AsyncGenerator[dict, None]:
        response = await self._execute(query)
        yield {"type": "token", "value": response.answer}
        for c in response.citations:
            yield {"type": "citation", "source_id": c.source_id, "source_type": c.source_type, "title": c.title, "relevance": c.relevance}
        yield {"type": "confidence", "score": response.confidence}
        yield {"type": "metadata", "value": {"agent": self.name, "conversation_id": self._conversation_id}}

    async def _agent_handler(self, task: str, context: dict, agent: IntelligenceAgent) -> Any:
        query = context.get("query", "")
        full_task = f"{query}\nTask: {task}"
        response = await agent.run(full_task)
        return {"answer": response.answer, "citations": [c.model_dump() for c in response.citations], "confidence": response.confidence}
