# Planner

## Purpose

The Planner transforms a user query into a structured execution plan. It NEVER answers questions — its only output is a list of ordered steps.

## ExecutionPlan Schema

```python
class ExecutionPlan(BaseModel):
    query: str                    # Original user query
    steps: list[PlanStep]         # Ordered execution steps
    complexity: str               # simple / medium / complex
    estimated_steps: int          # Total step count
```

```python
class PlanStep(BaseModel):
    step_id: str                  # Unique identifier
    agent: str                    # Specialist agent assigned
    task: str                     # What to accomplish
    depends_on: list[str]         # Step IDs that must complete first
    mode: ExecutionMode           # sequential / parallel / dependent
    tools: list[str]              # Tools this step may use
    max_retries: int              # Retry on failure
    timeout_seconds: float        # Timeout per attempt
```

## Execution Modes

| Mode | Behavior |
|------|----------|
| sequential | Steps execute one at a time in order |
| parallel | Independent steps execute concurrently |
| dependent | Executes when all dependencies complete |

## Planner Prompt

The Planner uses a dedicated `PLANNING_SYSTEM_PROMPT` in `backend/shared/orchestration/planner.py`. Key rules:

- Break queries into discrete ordered steps
- Each step maps to exactly one specialist agent
- Identify dependencies between steps
- Use parallel mode for independent steps
- Output ONLY valid JSON — no explanation text

## Fallback Planning

When LLM-based planning fails (timeout, parse error, etc.), the Planner falls back to a deterministic 3-step plan:

1. Research Agent — search and gather articles
2. Research Agent — analyze risk data
3. Executive Agent — synthesize response

## Endpoint

`POST /api/v1/agents/plan`

```json
{"query": "What happens if Iran blocks Hormuz for 10 days?"}
```

Returns:
```json
{
  "query": "...",
  "steps": [
    {"step_id": "step_1", "agent": "research", "task": "Research geopolitical situation...", "depends_on": [], "mode": "sequential"},
    {"step_id": "step_2", "agent": "knowledge_graph", "task": "Query KG for Hormuz...", "depends_on": ["step_1"], "mode": "sequential"}
  ],
  "complexity": "medium",
  "estimated_steps": 2
}
```
