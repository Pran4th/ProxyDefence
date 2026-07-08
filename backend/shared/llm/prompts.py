from __future__ import annotations

from typing import Any


class PromptTemplate:
    """A reusable prompt template with variable substitution."""

    def __init__(self, template: str, metadata: dict[str, Any] | None = None):
        self._template = template
        self._metadata = metadata or {}

    def render(self, **kwargs: Any) -> str:
        result = self._template
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                str_value = str(value) if value is not None else ""
                result = result.replace(placeholder, str_value)
        return result

    @property
    def template(self) -> str:
        return self._template

    @property
    def metadata(self) -> dict[str, Any]:
        return self._metadata


# Re-export system prompts from the new prompts package for backward compatibility.
# All new prompt additions should go to backend/shared/prompts/
from backend.shared.prompts.system import SYSTEM_PROMPTS as _system_prompts

SYSTEM_PROMPTS: dict[str, str] = _system_prompts


class PromptLibrary:
    """Central registry for all prompt templates with versioning support."""

    _templates: dict[str, PromptTemplate] = {}

    @classmethod
    def register(cls, name: str, template: str, metadata: dict[str, Any] | None = None) -> None:
        meta = metadata or {}
        if "version" not in meta:
            meta["version"] = "1.0"
        cls._templates[name] = PromptTemplate(template, meta)

    @classmethod
    def get(cls, name: str) -> PromptTemplate:
        if name not in cls._templates:
            raise KeyError(f"Prompt template '{name}' not found")
        return cls._templates[name]

    @classmethod
    def get_system(cls, agent_name: str) -> str:
        return SYSTEM_PROMPTS.get(agent_name, "")

    @classmethod
    def render(cls, name: str, **kwargs: Any) -> str:
        return cls.get(name).render(**kwargs)

    @classmethod
    def list_templates(cls) -> list[dict]:
        return [
            {"name": name, "version": t.metadata.get("version", "1.0"), "preview": t.template[:80]}
            for name, t in cls._templates.items()
        ]

    @classmethod
    def register_builtins(cls) -> None:
        cls.register(
            "query_analysis",
            """Analyze the following user query and provide:
1. Primary intent: what is the user asking for?
2. Required agents: which specialist agents should handle this?
3. Required data: what information needs to be retrieved?
4. Complexity: simple (single tool) / medium (multiple tools) / complex (multiple agents)

Query: {query}

Respond in JSON format with keys: intent, required_agents, required_data, complexity, suggested_tools.""",
            metadata={"version": "2.0", "category": "planning"},
        )

        cls.register(
            "threat_assessment",
            """Based on the following intelligence data, provide a threat assessment:

Risk Dashboard: {risk_dashboard}
Active Signals: {signals}
Recent Articles: {articles}
Commodity Prices: {commodity_prices}
Entity Context: {entity_context}

Provide:
1. Overall threat level with justification
2. Key risk factors driving the assessment
3. Geographic regions most affected
4. Commodities/infrastructure at risk
5. Confidence level
6. Recommended monitoring actions""",
            metadata={"version": "2.0", "category": "intelligence"},
        )

        cls.register(
            "executive_summary",
            """Synthesize the following intelligence into a concise executive summary:

Risk Assessment: {risk_assessment}
Key Events: {events}
Affected Infrastructure: {infrastructure}
Economic Indicators: {economic_indicators}

Format:
## Executive Summary
{2-3 sentence overview}

## Key Findings
- {finding 1}
- {finding 2}
- {finding 3}

## Recommended Actions
1. {action 1}
2. {action 2}

## Confidence: {confidence}""",
            metadata={"version": "2.0", "category": "executive"},
        )


PromptLibrary.register_builtins()
