from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.agents.registry import agent_registry
from backend.api.agents.specialist.interfaces import specialist_agent_registry
from backend.api.agents.supervisor import SupervisorAgent
from backend.shared.llm.schemas import AgentResponse
from backend.shared.orchestration.planner import Planner

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None


class AgentQueryResponse(BaseModel):
    content: str
    citations: list[dict] | None = None
    confidence: float | None = None
    tool_calls: list[dict] | None = None
    agent_name: str
    conversation_id: str
    metadata: dict | None = None


@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest) -> Any:
    supervisor = SupervisorAgent()
    if request.conversation_id:
        supervisor.set_conversation(request.conversation_id)
    response = await supervisor.run(request.query)
    return AgentQueryResponse(
        content=response.answer,
        citations=[c.model_dump() for c in response.citations] if response.citations else None,
        confidence=response.confidence,
        tool_calls=None,
        agent_name=response.agent_chain[0] if response.agent_chain else "supervisor",
        conversation_id=request.conversation_id or "default",
        metadata={"latency_ms": response.latency_ms, "tokens_used": response.tokens_used, "estimated_cost": response.estimated_cost},
    )


@router.post("/plan")
async def plan_query(request: AgentQueryRequest) -> Any:
    planner = Planner()
    plan = await planner.plan(request.query)
    return plan.model_dump()


@router.get("/list")
async def list_agents() -> list[dict]:
    return agent_registry.list_agents()


@router.get("/specialist-agents")
async def list_specialist_agents() -> list[dict]:
    return specialist_agent_registry.list_agents()
