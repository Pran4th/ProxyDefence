from __future__ import annotations

from typing import Any

from backend.shared.llm.schemas import AgentResponse, Citation, ToolCall, ToolResult
from backend.shared.orchestration.citations import CitationEngine
from backend.shared.orchestration.confidence import ConfidenceEngine, ConfidenceResult
from backend.shared.orchestration.planner import ExecutionPlan, Planner
from backend.shared.orchestration.reflection import ReflectionEngine, ReflectionResult
from backend.shared.orchestration.router import AgentRouter
from backend.shared.orchestration.trace import ExecutionTracer
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ExecutionEngine:
    """Orchestrates the full execution lifecycle: Plan → Route → Reflect → Confidence → Answer."""

    def __init__(self, planner: Planner | None = None, router: AgentRouter | None = None, reflection: ReflectionEngine | None = None, confidence: ConfidenceEngine | None = None):
        self._planner = planner or Planner()
        self._router = router or AgentRouter()
        self._reflection = reflection or ReflectionEngine()
        self._confidence = confidence or ConfidenceEngine()
        self._tracer = ExecutionTracer()
        self._citation_engine = CitationEngine()

        self._planner.set_tracer(self._tracer)
        self._router.set_tracer(self._tracer)
        self._reflection.set_tracer(self._tracer)

    async def execute(self, query: str, conversation_history: list[dict] | None = None) -> AgentResponse:
        self._tracer.start(f"execute: {query[:50]}")
        exec_id = self._tracer._current_id
        self._citation_engine.clear()

        plan = await self._planner.plan(query, conversation_history)
        shared_context = {"query": query}

        self._tracer.push_context(exec_id)
        step_outputs = await self._router.dispatch(plan, shared_context)
        self._tracer.pop_context()
        evidence = self._collect_evidence(step_outputs)

        reflect_node = self._tracer.add_reflection("initial_evaluation")
        self._tracer.push_context(reflect_node.id)
        reflection = await self._reflection.evaluate(query, evidence)
        self._tracer.pop_context()
        self._tracer.end(reflect_node, output=reflection.__dict__)

        if reflection.recommendation == "gather_more" and reflection.additional_tools:
            expanded = await self._expand_plan(plan, reflection)
            self._tracer.push_context(exec_id)
            extra_outputs = await self._router.dispatch(expanded, shared_context)
            self._tracer.pop_context()
            step_outputs.extend(extra_outputs)
            evidence = self._collect_evidence(step_outputs)
            reflect_node2 = self._tracer.add_reflection("re_evaluation")
            self._tracer.push_context(reflect_node2.id)
            reflection = await self._reflection.evaluate(query, evidence)
            self._tracer.pop_context()
            self._tracer.end(reflect_node2, output=reflection.__dict__)

        confidence = self._confidence.compute(
            tool_results=[e for e in evidence],
            citations=self._citation_engine.get_all(),
            reflection_feedback={"confidence": reflection.confidence},
        )

        answer = self._synthesize_answer(query, step_outputs, confidence, reflection)
        trace = self._tracer.snapshot()
        per_type = self._tracer.get_per_type_summary()

        return AgentResponse(
            answer=answer,
            citations=[Citation(**c) for c in self._citation_engine.to_agent_response()],
            confidence=confidence.overall,
            agent_chain=[s.get("agent", "") for s in step_outputs if isinstance(s, dict)],
            tool_executions=[e for e in evidence],
            latency_ms=trace.get("total_duration_ms", 0),
            tokens_used=0,
            estimated_cost=0.0,
        )

    async def get_trace_snapshot(self) -> dict:
        return self._tracer.snapshot()

    async def get_per_type_summary(self) -> dict:
        return self._tracer.get_per_type_summary()

    def _collect_evidence(self, step_outputs: list[dict]) -> list[dict]:
        evidence = []
        for step in step_outputs:
            output = step.get("output", {})
            if isinstance(output, dict):
                evidence.append({"source": step.get("agent", "unknown"), "step_id": step.get("step_id"), "data": output})
                for tool_result in output.get("tool_results", []):
                    if isinstance(tool_result, dict):
                        evidence.append({"source": tool_result.get("tool_name", "tool"), "data": tool_result})
            elif isinstance(output, str):
                evidence.append({"source": step.get("agent"), "data": {"content": output[:500]}})
        return evidence

    async def _expand_plan(self, original: ExecutionPlan, reflection: ReflectionResult) -> ExecutionPlan:
        new_steps = []
        for i, gap in enumerate(reflection.gaps):
            tools = reflection.additional_tools if i == 0 else []
            from backend.shared.orchestration.planner import PlanStep, ExecutionMode
            new_steps.append(
                PlanStep(
                    step_id=f"reflect_{i}",
                    agent="research",
                    task=f"Gather additional: {gap}",
                    depends_on=[s.step_id for s in original.steps],
                    tools=tools if tools else [],
                )
            )
        original.steps.extend(new_steps)
        return original

    def _synthesize_answer(self, query: str, step_outputs: list[dict], confidence: ConfidenceResult, reflection: ReflectionResult) -> str:
        parts = [f"Query: {query}", ""]
        for step in step_outputs:
            agent = step.get("agent", "unknown")
            status = step.get("status", "unknown")
            parts.append(f"**{agent}** ({status})")
            output = step.get("output")
            if isinstance(output, dict):
                content = output.get("answer", output.get("content", str(output)[:300]))
                parts.append(str(content)[:500])
            elif isinstance(output, str):
                parts.append(output[:500])
            parts.append("")

        parts.append(f"**Confidence**: {confidence.overall:.0%}")
        if reflection.gaps:
            parts.append(f"**Unresolved gaps**: {', '.join(reflection.gaps[:3])}")
        if reflection.conflicts:
            parts.append(f"**Conflicts detected**: {', '.join(reflection.conflicts[:2])}")

        return "\n".join(parts)
