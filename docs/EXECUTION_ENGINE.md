# Execution Engine

## Purpose

The ExecutionEngine orchestrates the complete lifecycle:

```
Plan → Route → Execute → Reflect → Confidence → Answer
```

## File: `backend/shared/orchestration/engine.py`

### `ExecutionEngine.execute(query, conversation_history) → AgentResponse`

1. Creates `ExecutionTracer` for the entire execution
2. Calls `Planner.plan(query)` → `ExecutionPlan`
3. Passes plan to `AgentRouter.dispatch(plan, shared_context)`
4. Collects evidence from all step outputs
5. Calls `ReflectionEngine.evaluate(evidence)`
6. If reflection recommends gathering more evidence, expands plan and re-dispatches
7. Calls `ConfidenceEngine.compute(...)` for multi-factor scoring
8. CitationEngine collects all sources across steps
9. Synthesizes final `AgentResponse`

### AgentResponse Fields

| Field | Source |
|-------|--------|
| answer | LLM-synthesized from step outputs |
| citations | CitationEngine collection |
| confidence | ConfidenceEngine result |
| agent_chain | Ordered names of agents involved |
| tool_executions | All tool call results |
| latency_ms | Total execution duration |
| tokens_used | Token count (from LLMClient stats) |
| estimated_cost | API cost estimate |

### Reflection Gate

If `ReflectionResult.recommendation == "gather_more"`, the engine:
1. Creates additional `PlanStep` entries for each gap
2. Appends them to the original plan
3. Re-dispatches through the AgentRouter
4. Re-evaluates evidence with updated results

### Execution Trace

Every execution produces a tree structure:
```
execution
  ├── plan (planning)
  │   ├── step_1 (agent dispatch)
  │   │   ├── agent_call
  │   │   │   ├── tool_call_1
  │   │   │   └── tool_call_2
  │   │   └── ...
  │   └── step_2
  ├── reflection
  └── (confidence computed at engine level)
```
