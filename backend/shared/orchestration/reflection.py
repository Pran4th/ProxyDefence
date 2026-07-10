from __future__ import annotations

import json
from typing import Any

from backend.shared.llm.client import LLMClient
from backend.shared.llm.config import LLMConfig, TEMPERATURE_PRESETS
from backend.shared.orchestration.trace import ExecutionTracer
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

REFLECTION_SYSTEM_PROMPT = """You are a reflection agent. Your job is to evaluate whether the collected evidence is sufficient to answer the user's query.

Evaluate:
1. Evidence sufficiency: Is there enough data to form a complete answer?
2. Evidence conflicts: Do any tool outputs contradict each other?
3. Coverage gaps: What aspects of the query are still unanswered?
4. Confidence assessment: How confident should we be?

If evidence is insufficient, specify:
- What additional information is needed
- Which tools could provide it
- Which agent should retrieve it

Output JSON:
{
  "sufficient": true/false,
  "confidence": 0.0-1.0,
  "gaps": ["list of missing information"],
  "conflicts": ["list of contradictions"],
  "additional_tools_needed": ["tool1", "tool2"],
  "recommendation": "proceed" or "gather_more"
}"""


class ReflectionResult:
    def __init__(self, sufficient: bool, confidence: float, gaps: list[str], conflicts: list[str], additional_tools: list[str], recommendation: str):
        self.sufficient = sufficient
        self.confidence = confidence
        self.gaps = gaps
        self.conflicts = conflicts
        self.additional_tools = additional_tools
        self.recommendation = recommendation


class ReflectionEngine:
    """Evaluates evidence quality, detects conflicts, and recommends additional information gathering."""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client or LLMClient()
        self._tracer: ExecutionTracer | None = None

    def set_tracer(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer

    async def evaluate(
        self,
        query: str,
        evidence: list[dict],
        max_iterations: int = 3,
    ) -> ReflectionResult:
        reflect_node = None
        if self._tracer:
            reflect_node = self._tracer.add_reflection(f"reflect: {query[:50]}")
            reflect_node.input = {"query": query, "evidence_count": len(evidence)}

        messages = [{"role": "system", "content": REFLECTION_SYSTEM_PROMPT}]

        evidence_text = "\n\n".join(
            f"[{i + 1}] {e.get('source', 'unknown')}: {json.dumps(e.get('data', {}), default=str)[:500]}"
            for i, e in enumerate(evidence)
        )
        messages.append({"role": "user", "content": f"Query: {query}\n\nCollected evidence:\n{evidence_text}\n\nEvaluate sufficiency."})

        for attempt in range(max_iterations):
            try:
                settings = LLMConfig.load().settings_for(temperature_preset="precise")
                content, _, _ = await self._llm.chat(messages=messages, settings=settings)
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
                data = json.loads(cleaned)

                result = ReflectionResult(
                    sufficient=data.get("sufficient", True),
                    confidence=data.get("confidence", 0.5),
                    gaps=data.get("gaps", []),
                    conflicts=data.get("conflicts", []),
                    additional_tools=data.get("additional_tools_needed", []),
                    recommendation=data.get("recommendation", "proceed"),
                )

                if self._tracer and reflect_node:
                    self._tracer.end(reflect_node, output=result.__dict__)
                return result

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Reflection parse error (attempt %d): %s", attempt + 1, e)
                continue

        fallback = ReflectionResult(
            sufficient=True, confidence=0.5, gaps=[], conflicts=[],
            additional_tools=[], recommendation="proceed",
        )
        if self._tracer and reflect_node:
            self._tracer.end(reflect_node, output=fallback.__dict__, error="Max iterations exceeded")
        return fallback
