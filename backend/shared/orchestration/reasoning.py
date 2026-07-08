from __future__ import annotations

import json
from typing import Any, Callable

from backend.shared.llm.client import LLMClient
from backend.shared.llm.schemas import ToolCall, ToolResult
from backend.shared.orchestration.trace import ExecutionTracer
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

REASONING_SYSTEM_PROMPT = """You are a reasoning agent. Use the following structured thinking process:

---
Thought: What information do I need and what should I do next?
Action: The tool to call (or "Final" if done)
Action Input: JSON arguments for the tool
---

After each tool result, analyze the observation:
---
Observation: What the tool returned
Reflection: Does this answer the question? Is there conflicting evidence? What's missing?
Thought: What to do next
---

Repeat until you have sufficient evidence, then respond with:
---
Final Answer: <complete response based on all evidence>
---"""


class ReasoningLoop:
    """Implements Thought → Tool → Observation → Reflection → ... → Final reasoning."""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client or LLMClient()
        self._tracer: ExecutionTracer | None = None
        self._tool_executor: Callable[[str, dict], ToolResult] | None = None

    def set_tracer(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer

    def set_tool_executor(self, executor: Callable[[str, dict], ToolResult]) -> None:
        self._tool_executor = executor

    async def reason(
        self,
        query: str,
        context: str | None = None,
        tools: list[dict] | None = None,
        max_iterations: int = 5,
    ) -> tuple[str, list[ToolResult], list[dict]]:
        iterations: list[dict] = []
        all_tool_results: list[ToolResult] = []
        messages = [{"role": "system", "content": REASONING_SYSTEM_PROMPT}]
        if context:
            messages.append({"role": "system", "content": f"Additional context:\n{context}"})
        messages.append({"role": "user", "content": query})

        for i in range(max_iterations):
            iter_node = None
            if self._tracer:
                iter_node = self._tracer.add_reasoning_iteration(i + 1)

            content, tool_calls, _ = await self._llm.chat(messages=messages, tools=tools)

            iteration_record = {"iteration": i + 1, "thought": content, "tool_calls": [], "observations": []}

            if not tool_calls:
                messages.append({"role": "assistant", "content": content})
                if self._tracer and iter_node:
                    self._tracer.end(iter_node, output={"status": "final", "content": content})
                iterations.append(iteration_record)
                return content, all_tool_results, iterations

            messages.append({"role": "assistant", "content": content})

            for tc in tool_calls:
                iteration_record["tool_calls"].append({"name": tc.name, "arguments": tc.arguments})
                result = ToolResult(success=False, tool_call_id=tc.id, tool_name=tc.name, output=None)
                tool_node = None
                if self._tracer:
                    tool_node = self._tracer.add_tool_call(tc.name)
                    tool_node.input = {"arguments": tc.arguments}

                if self._tool_executor:
                    try:
                        result = self._tool_executor(tc.name, tc.arguments or {})
                    except Exception as e:
                        result = ToolResult(success=False, tool_call_id=tc.id, tool_name=tc.name, output=None, error=str(e))

                if self._tracer and tool_node:
                    self._tracer.end(tool_node, output=result.model_dump() if result.success else None, error=result.error)

                all_tool_results.append(result)
                observation = json.dumps(result.model_dump(), default=str)[:2000]
                iteration_record["observations"].append({"tool": tc.name, "result": observation})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": observation,
                })

            if self._tracer and iter_node:
                self._tracer.end(iter_node, output={"iteration": i + 1, "tool_count": len(tool_calls)})

            iterations.append(iteration_record)

        content, _, _ = await self._llm.chat(messages=messages)
        return content, all_tool_results, iterations
