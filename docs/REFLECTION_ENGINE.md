# Reflection Engine

## Purpose

The ReflectionEngine evaluates whether collected evidence is sufficient to answer the user's query. It acts as a quality gate between execution and final response generation.

## File: `backend/shared/orchestration/reflection.py`

### `ReflectionEngine.evaluate(query, evidence, max_iterations) → ReflectionResult`

**Inputs:**
- `query`: Original user query
- `evidence`: List of tool outputs and step results
- `max_iterations`: Max parse attempts (default 3)

**Output:**
```python
class ReflectionResult:
    sufficient: bool              # Is evidence enough?
    confidence: float             # 0.0-1.0 self-assessment
    gaps: list[str]              # Missing information
    conflicts: list[str]         # Contradictions found
    additional_tools: list[str]  # Tools needed for gaps
    recommendation: str           # "proceed" or "gather_more"
```

### Reflection Prompt

The engine uses `EVIDENCE_EVALUATION_PROMPT` which asks the LLM to evaluate:

1. **Evidence sufficiency** — is there enough data?
2. **Evidence conflicts** — do any outputs contradict?
3. **Coverage gaps** — what's unanswered?
4. **Confidence assessment** — how confident?

### Engine Integration

The ExecutionEngine checks reflection output after all plan steps:

```python
reflection = await self._reflection.evaluate(query, evidence)
if reflection.recommendation == "gather_more":
    # Expand plan with additional steps
    plan = await self._expand_plan(plan, reflection)
    extra_outputs = await self._router.dispatch(plan, shared_context)
    # Re-evaluate
    reflection = await self._reflection.evaluate(query, evidence)
```

### Conflict Detection

The reflection prompt explicitly asks the LLM to identify:
- Contradictions between tool outputs
- Disagreements between data sources
- Anomalous or outlier results
