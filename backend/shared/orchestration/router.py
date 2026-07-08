from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from backend.shared.orchestration.planner import ExecutionMode, ExecutionPlan, PlanStep
from backend.shared.orchestration.trace import ExecutionTracer, TraceNode
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

AgentHandler = Callable[[str, dict], Any]


class AgentRouter:
    """Dispatches plan steps to specialist agents. Supports sequential, parallel, and dependency-based execution."""

    def __init__(self):
        self._handlers: dict[str, AgentHandler] = {}
        self._tracer: ExecutionTracer | None = None

    def register_agent(self, name: str, handler: AgentHandler) -> None:
        self._handlers[name] = handler

    def set_tracer(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer

    async def dispatch(self, plan: ExecutionPlan, shared_context: dict) -> list[dict]:
        results: dict[str, Any] = {}
        outputs: list[dict] = []

        steps_by_id = {s.step_id: s for s in plan.steps}
        completed: set[str] = set()
        pending = list(plan.steps)
        max_iterations = 50

        for _ in range(max_iterations):
            if not pending:
                break

            ready: list[PlanStep] = []
            remaining: list[PlanStep] = []

            for step in pending:
                if all(dep in completed for dep in step.depends_on):
                    ready.append(step)
                else:
                    remaining.append(step)

            if not ready:
                logger.warning("Deadlocked steps: %s", [s.step_id for s in remaining])
                break

            parallel_batch = [s for s in ready if s.mode in (ExecutionMode.PARALLEL, ExecutionMode.DEPENDENT)]
            sequential_batch = [s for s in ready if s.mode == ExecutionMode.SEQUENTIAL]

            for step in sequential_batch:
                result = await self._execute_step(step, shared_context, results)
                outputs.append(result)
                completed.add(step.step_id)
                results[step.step_id] = result.get("output")

            if parallel_batch:
                tasks = [self._execute_step(s, shared_context, results) for s in parallel_batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for step, res in zip(parallel_batch, batch_results):
                    if isinstance(res, Exception):
                        outputs.append({"step_id": step.step_id, "agent": step.agent, "status": "failed", "error": str(res)})
                    else:
                        outputs.append(res)
                        results[step.step_id] = res.get("output")
                    completed.add(step.step_id)

            pending = remaining

        return outputs

    async def _execute_step(self, step: PlanStep, shared_context: dict, prior_results: dict) -> dict:
        agent_node = None
        if self._tracer:
            agent_node = self._tracer.add_agent_call(f"{step.agent}:{step.step_id}")
            agent_node.input = {"step_id": step.step_id, "task": step.task, "tools": step.tools}
            self._tracer.push_context(agent_node.id)

        handler = self._handlers.get(step.agent)
        if not handler:
            error = f"No handler registered for agent '{step.agent}'"
            logger.error(error)
            if self._tracer:
                self._tracer.pop_context()
                self._tracer.end(agent_node, error=error)
            return {"step_id": step.step_id, "agent": step.agent, "status": "error", "error": error}

        context = {
            "query": shared_context.get("query", ""),
            "task": step.task,
            "tools": step.tools,
            "step_id": step.step_id,
            "prior_results": prior_results,
            "shared_context": shared_context,
        }

        last_error: str | None = None
        for attempt in range(1, step.max_retries + 2):
            try:
                result = await asyncio.wait_for(handler(step.task, context), timeout=step.timeout_seconds)
                if self._tracer and agent_node:
                    self._tracer.pop_context()
                    self._tracer.end(agent_node, output=result)
                return {
                    "step_id": step.step_id,
                    "agent": step.agent,
                    "status": "completed",
                    "output": result,
                    "attempts": attempt,
                }
            except asyncio.TimeoutError:
                last_error = f"Timeout after {step.timeout_seconds}s"
                logger.warning("Step %s timed out (attempt %d)", step.step_id, attempt)
            except Exception as e:
                last_error = str(e)
                logger.warning("Step %s failed (attempt %d): %s", step.step_id, attempt, e)

            if attempt <= step.max_retries:
                await asyncio.sleep(attempt)

        if self._tracer and agent_node:
            self._tracer.pop_context()
            self._tracer.end(agent_node, error=last_error)
        return {"step_id": step.step_id, "agent": step.agent, "status": "failed", "error": last_error}
