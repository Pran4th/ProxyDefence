# Prompt Architecture

## Separation

Prompts are now separated by role into dedicated files:

| File | Contents | Used By |
|------|----------|---------|
| `prompts/system.py` | System prompts for all 9 agents | BaseAgent subclasses |
| `prompts/planning.py` | Planning prompts | Planner |
| `prompts/reflection.py` | Evidence evaluation prompts | ReflectionEngine |
| `prompts/executive.py` | Executive summary prompts | ExecutiveAgent |
| `prompts/validation.py` | Claim verification prompts | ValidationAgent |
| `llm/prompts.py` | PromptLibrary class (registry) | All components |

## Agent System Prompts

Nine agents defined in `prompts/system.py`:

| Agent | Purpose |
|-------|---------|
| supervisor | Thin coordinator |
| intelligence | Geopolitical threat assessment |
| research | Search and retrieval |
| scenario | Simulation and impact analysis |
| decision | Procurement and SPR decisions |
| prediction | ML model predictions |
| validation | Claim verification |
| executive | Executive summaries |
| spr | SPR analysis |
| procurement | Procurement optimization |
| knowledge_graph | Graph queries |

## PromptLibrary (backward compatible)

The existing `PromptLibrary` in `llm/prompts.py` now:
- Re-exports `SYSTEM_PROMPTS` from the new prompts package
- Supports versioned templates via `metadata["version"]`
- Provides `list_templates()` for introspection
- All existing `PromptLibrary.get("query_analysis")` calls continue to work

## Versioning

Every prompt template now carries metadata:

```python
PromptLibrary.register(
    "query_analysis",
    "Analyze the following user query...",
    metadata={"version": "2.0", "category": "planning"}
)
```

## Prompt Categories

| Category | Files |
|----------|-------|
| System | `system.py` |
| Planning | `planning.py`, `llm/prompts.py` (query_analysis) |
| Tool | `llm/prompts.py` (built-in templates) |
| Reflection | `reflection.py` |
| Executive | `executive.py`, `llm/prompts.py` (executive_summary) |
| Validation | `validation.py` |
