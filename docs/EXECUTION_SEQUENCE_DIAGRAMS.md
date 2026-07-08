# Execution Sequence Diagrams

## Full Orchestrated Flow

```
User                    Supervisor              Planner              AgentRouter          Specialist Agents        Reflection         Confidence
 |                          |                      |                      |                      |                      |                  |
 |-- POST /agents/query --->|                      |                      |                      |                      |                  |
 |                          |-- planner.plan() ---->|                      |                      |                      |                  |
 |                          |<-- ExecutionPlan -----|                      |                      |                      |                  |
 |                          |                      |                      |                      |                      |                  |
 |                          |-- router.dispatch() ----------------------->|                      |                      |                  |
 |                          |                      |                      |                      |                      |                  |
 |                          |                      |                      |-- step_1 (research) ->|                      |                  |
 |                          |                      |                      |                      |-- search_articles -->|                  |
 |                          |                      |                      |                      |<-- results ----------|                  |
 |                          |                      |                      |                      |-- get_risk_data ---->|                  |
 |                          |                      |                      |                      |<-- risk scores ------|                  |
 |                          |                      |                      |                      |                      |                  |
 |                          |                      |                      |-- step_2 (kg) ------->|                      |                  |
 |                          |                      |                      |                      |-- expand_graph ----->|                  |
 |                          |                      |                      |                      |<-- graph data -------|                  |
 |                          |                      |                      |                      |                      |                  |
 |                          |                      |                      |<-- step outputs ------|                      |                  |
 |                          |                      |                      |                      |                      |                  |
 |                          |-- reflection.evaluate() -------------------------------->|                      |                  |
 |                          |<-- ReflectionResult  |                      |                      |                      |                  |
 |                          |                      |                      |                      |                      |                  |
 |                          |-- confidence.compute() --------------------------------------------->|                  |
 |                          |<-- ConfidenceResult  |                      |                      |                      |                  |
 |                          |                      |                      |                      |                      |                  |
 |                          |-- synthesize --------|                      |                      |                      |                  |
 |                          |                      |                      |                      |                      |                  |
 |<-- AgentResponse --------|                      |                      |                      |                      |                  |
```

## Parallel Execution

```
AgentRouter
    |
    |-- [PARALLEL] ------------------------------------|
    |   |                    |                         |
    |   v                    v                         v
    |   step_1 (research)   step_2 (kg)           step_3 (risk)
    |   |                    |                         |
    |   v                    v                         v
    |   search_articles      expand_graph         get_risk_dashboard
    |   semantic_search      get_entity_net       get_active_signals
    |                       get_relationships
    |   |                    |                         |
    |   +---------+----------+-------------------------+
    |             |
    |             v
    |    all done → continue
```

## Reflection-Triggered Re-Execution

```
Router ──→ Step Outputs
                |
                v
          ReflectionEngine
                |
                ├── sufficient=true ──→ proceed to confidence
                |
                └── sufficient=false ──→ expand plan
                        |
                        v
                  Planner expands plan
                        |
                        v
                  Router re-dispatches
                        |
                        v
                  Reflection re-evaluates
                        |
                        v
                  (repeat or proceed)
```
