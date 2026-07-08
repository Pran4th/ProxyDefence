# Agent Router

## Purpose

The AgentRouter dispatches execution plan steps to registered specialist agent handlers. It manages execution order, parallelism, retries, timeouts, and dependency resolution.

## File: `backend/shared/orchestration/router.py`

### `AgentRouter.register_agent(name, handler)`

Each handler is an `async def handler(task: str, context: dict) -> Any` function.

### `AgentRouter.dispatch(plan, shared_context) → list[dict]`

Returns a list of step results, each containing:
- `step_id`: matching plan step
- `agent`: agent name
- `status`: "completed", "failed", "error"
- `output`: handler return value (if completed)
- `error`: error message (if failed)
- `attempts`: number of attempts made

### Dependency Resolution

The router uses a simple completion-based resolver:

1. Find all steps whose dependencies are met
2. Execute sequential steps one at a time
3. Execute parallel steps concurrently via `asyncio.gather`
4. Repeat until all steps complete or deadlock detected

### Retry Logic

Each step respects `PlanStep.max_retries` and `PlanStep.timeout_seconds`:

- On failure: exponential backoff (1s, 2s, 3s, ...)
- On timeout: `asyncio.wait_for` with step timeout
- After exhausting retries: marks step as "failed" and continues

### Parallel Execution

Steps with `ExecutionMode.PARALLEL` are batched and executed via `asyncio.gather`. This allows independent research tasks, simulation runs, and data fetches to proceed simultaneously.

### Handler Registration

Supervisor registers handlers at construction:

```python
router.register_agent("research", research_handler)
router.register_agent("scenario", scenario_handler)
router.register_agent("decision", decision_handler)
router.register_agent("prediction", prediction_handler)
router.register_agent("validation", validation_handler)
router.register_agent("executive", executive_handler)
router.register_agent("spr", spr_handler)
router.register_agent("procurement", procurement_handler)
router.register_agent("knowledge_graph", knowledge_graph_handler)
```
