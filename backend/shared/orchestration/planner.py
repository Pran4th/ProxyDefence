from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.shared.llm.client import LLMClient
from backend.shared.llm.config import LLMConfig, TEMPERATURE_PRESETS
from backend.shared.orchestration.trace import ExecutionTracer, TraceNode
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENT = "dependent"


class PlanStep(BaseModel):
    """A single step in an execution plan."""

    step_id: str = Field(description="Unique step identifier")
    agent: str = Field(description="Specialist agent responsible")
    task: str = Field(description="What this step should accomplish")
    depends_on: list[str] = Field(default_factory=list, description="Step IDs that must complete first")
    mode: ExecutionMode = Field(default=ExecutionMode.SEQUENTIAL)
    tools: list[str] = Field(default_factory=list, description="Tools this step may use")
    max_retries: int = Field(default=2)
    timeout_seconds: float = Field(default=60.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """Structured plan produced by the Planner."""

    query: str = Field(description="Original user query")
    steps: list[PlanStep] = Field(description="Ordered execution steps")
    complexity: str = Field(default="medium", description="simple / medium / complex")
    estimated_steps: int = Field(default=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


PLANNING_SYSTEM_PROMPT = """You are a strategic planning agent.

Your role is to produce execution plans. You NEVER answer questions.

Given a user query, analyze what information and computations are needed, and produce a structured plan.

Rules:
- Break the query into discrete, ordered steps
- Each step must be handled by exactly one specialist agent
- Identify dependencies between steps
- Use "parallel" mode for independent steps
- Use "sequential" mode for dependent steps
- Choose the appropriate agent for each step
- Available agents: research, scenario, decision, prediction, validation, executive, spr, procurement, knowledge_graph
- ResearchAgent: article search, entity lookup, semantic search
- ScenarioAgent: digital twin, simulation, impact analysis
- DecisionAgent: procurement, spr, executive cards
- PredictionAgent: ML predictions, forecasting
- KnowledgeGraphAgent: relationships, graph expansion, risk propagation
- ExecutiveAgent: synthesizing outputs, executive summaries
- ValidationAgent: checking evidence, verifying claims
- SPRAgent: strategic petroleum reserve analysis
- ProcurementAgent: procurement optimization, supplier analysis

Output ONLY valid JSON matching the ExecutionPlan schema. No explanation text."""


class Planner:
    """Produces structured execution plans from user queries. Does NOT answer questions."""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client or LLMClient()
        self._tracer: ExecutionTracer | None = None

    def set_tracer(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer

    async def plan(self, query: str, conversation_history: list[dict] | None = None) -> ExecutionPlan:
        plan_node = None
        if self._tracer:
            plan_node = self._tracer.add_plan(f"plan: {query[:50]}")
            plan_node.input = {"query": query}

        messages = [{"role": "system", "content": PLANNING_SYSTEM_PROMPT}]
        if conversation_history:
            messages.extend(conversation_history[-5:])
        messages.append({"role": "user", "content": f"Query: {query}\n\nProduce a structured execution plan."})

        try:
            settings = LLMConfig.load().settings_for(temperature_preset="precise")
            content, _, metrics = await self._llm.chat(messages=messages, settings=settings)

            plan_data = self._parse_plan(content, query)
            plan = ExecutionPlan(**plan_data)

            if self._tracer and plan_node:
                self._tracer.push_context(plan_node.id)
                for i, step in enumerate(plan.steps):
                    step_node = self._tracer.add_step(f"{step.agent}: {step.task[:40]}", i)
                    step_node.input = step.model_dump()
                    self._tracer.end(step_node, output={"status": "planned"})
                self._tracer.pop_context()
                self._tracer.end(plan_node, output=plan.model_dump())

            return plan

        except Exception as e:
            logger.error("Planning failed: %s", e)
            fallback = self._fallback_plan(query)
            if self._tracer and plan_node:
                self._tracer.end(plan_node, output=fallback.model_dump(), error=str(e))
            return fallback

    def _parse_plan(self, content: str, query: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        return self._fallback_plan(query).model_dump()

    def _fallback_plan(self, query: str) -> ExecutionPlan:
        return ExecutionPlan(
            query=query,
            steps=[
                PlanStep(
                    step_id="step_1",
                    agent="research",
                    task=f"Research: {query}",
                    mode=ExecutionMode.SEQUENTIAL,
                    tools=["search_articles", "semantic_search"],
                ),
                PlanStep(
                    step_id="step_2",
                    agent="research",
                    task="Analyze findings",
                    mode=ExecutionMode.SEQUENTIAL,
                    depends_on=["step_1"],
                    tools=["get_risk_dashboard", "get_active_signals"],
                ),
                PlanStep(
                    step_id="step_3",
                    agent="executive",
                    task="Synthesize final response",
                    mode=ExecutionMode.SEQUENTIAL,
                    depends_on=["step_2"],
                ),
            ],
            complexity="medium",
            estimated_steps=3,
        )
