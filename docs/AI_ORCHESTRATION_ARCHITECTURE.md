# AI Orchestration Architecture

## Architecture Overview

```
User Query
    |
    v
Supervisor (thin coordinator)
    |
    v
Planner ───→ ExecutionPlan (structured steps w/ dependencies)
    |
    v
AgentRouter ──→ Specialist Agents (parallel / sequential / dependent)
    |                |
    |                v
    |           Specialist Tools (each agent owns its tools)
    |
    v
ReflectionEngine ──→ Evidence check → more data if needed
    |
    v
ConfidenceEngine ──→ Multi-factor confidence scoring
    |
    v
CitationEngine ──→ Structured source tracking
    |
    v
ExecutionEngine ──→ Synthesize Executive Response
    |
    v
User Response
```

## Key Design Decisions

### 1. Supervisor is a Thin Coordinator
The Supervisor does NOT call tools. It does NOT plan. It does NOT answer questions directly. Its only job is to wire Planner → AgentRouter → Reflection → Confidence → Answer.

### 2. Planner Never Answers Questions
The Planner's only output is a structured `ExecutionPlan` — a list of ordered steps with agent assignments, dependencies, and tool recommendations. No natural language.

### 3. Agents Own Their Tools
Every specialist agent owns its tool set. The Supervisor never calls tools directly. Tools are assigned to agents at registration time via `agent_owner`.

### 4. Reasoning Loop is Separate
The `ReasoningLoop` (Thought → Tool → Observation → Reflection) is a standalone component. Specialist agents can use it, but the core orchestration pipeline does not force it.

### 5. Reflection is a Gate
After all plan steps execute, the ReflectionEngine evaluates whether evidence is sufficient. If not, it can request additional plan steps.

### 6. Confidence is Multi-Factor
Seven factors weighted into overall confidence: tool reliability, evidence count, source agreement, KG support, RAG score, LLM self-evaluation, contradictions.

### 7. Citations are Centralized
The `CitationEngine` collects sources from every plan step. Agents never manually assemble citations.

## Directory Structure

```
backend/
  shared/
    orchestration/        # NEW: orchestration layer
      planner.py          # produces structured plans
      engine.py           # orchestrates plan → route → reflect → answer
      router.py           # dispatches steps to agents
      reasoning.py        # Thought → Tool → Observation → Reflection loop
      reflection.py       # evidence evaluation
      confidence.py       # multi-factor confidence
      citations.py        # centralized citation management
      trace.py            # execution tracing
    prompts/              # NEW: separated prompt architecture
      system.py           # agent system prompts
      planning.py         # planning prompts
      reflection.py       # reflection prompts
      executive.py        # executive summary prompts
      validation.py       # validation prompts
    memory/               # NEW: specialized memory types
      conversation.py     # conversation history
      execution.py        # execution plan history
      agent.py            # per-agent memory
      compression.py      # context compression & summarization
  api/
    agents/
      specialist/         # NEW: specialist agent interfaces
        interfaces.py     # 9 agent interfaces + registry
      supervisor.py       # REFACTORED: now thin
      base.py             # REFACTORED: simplified
```

## Data Flow (Refactored)

```
1. User sends query → POST /api/v1/agents/query
2. Supervisor receives query
3. Supervisor calls Planner.plan(query) → ExecutionPlan
4. Supervisor passes plan to AgentRouter.dispatch(plan)
5. AgentRouter executes steps (parallel/sequential based on dependencies)
6. Each step calls the registered specialist agent handler
7. Each handler uses the Intelligence Agent (or future specialist)
8. AgentRouter returns step outputs
9. ReflectionEngine.evaluate(evidence) → ReflectionResult
10. If insufficient, expand plan and re-dispatch
11. ConfidenceEngine.compute(...) → ConfidenceResult
12. CitationEngine collects all sources
13. ExecutionEngine synthesizes AgentResponse
14. Supervisor returns response to user
```
