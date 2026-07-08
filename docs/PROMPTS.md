# Prompt Management

All prompts are managed centrally in `backend/shared/llm/prompts.py`.

## Agent System Prompts

### Supervisor Agent

The Supervisor prompt defines the orchestrator role: understand queries, route to specialists, call tools, merge responses, cite sources, and never fabricate data.

### Intelligence Agent

The Intelligence prompt defines the geopolitical analyst role: analyze events, assess threats, explain risks, identify connections, recommend actions, and always cite sources.

## Prompt Templates

### `query_analysis`
Analyzes user query to extract intent, required agents, required data, and complexity level.

### `threat_assessment`
Synthesizes risk dashboard data, signals, articles, commodity prices, and entity context into a structured assessment with threat level, risk factors, affected regions, and recommendations.

### `executive_summary`
Formats risk assessment, events, infrastructure, and economic indicators into a concise executive summary.

## Prompt Library

```python
PromptLibrary.register("template_name", "Template text with {variable}")
PromptLibrary.render("template_name", variable="value")
```

Templates are registered at import time via `PromptLibrary.register_builtins()`.
