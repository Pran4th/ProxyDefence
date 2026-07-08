# Agent Design

## BaseAgent

All agents extend `BaseAgent` (`backend/api/agents/base.py`):

```python
class BaseAgent(ABC):
    async def run(self, query: str, context: AgentContext | None = None) -> AgentResponse
    async def run_stream(self, query: str, context: AgentContext | None = None) -> AsyncGenerator[dict, None]
```

## Supervisor Agent

**File:** `backend/api/agents/supervisor.py`

The Supervisor is the entry point for all user queries. It:

1. Loads conversation memory from `MemoryStore`
2. Builds OpenAI messages with system prompt
3. Calls LLM with all 25 tools available
4. Executes tool calls, feeds results back to LLM
5. Synthesizes final response with citations

**System Prompt:** Defined in `SYSTEM_PROMPTS["supervisor"]` in prompts.py

**Streaming:** Uses SSE events: `agent_status`, `tool_call`, `tool_result`, `token`, `citation`, `confidence`, `metadata`

## Intelligence Agent

**File:** `backend/api/agents/intelligence.py`

Specialist agent for geopolitical threat assessment. Has access to a focused subset of tools:
- Risk dashboard, signals, entity risk profiles, trends
- Article search (keyword + semantic)
- Entity research (articles, profiles, relationships)
- Energy infrastructure lookup
- Port congestion, tanker availability, sanctions
- Knowledge graph, risk propagation

**System Prompt:** Defined in `SYSTEM_PROMPTS["intelligence"]` in prompts.py

## Agent Registry

**File:** `backend/api/agents/registry.py`

```python
agent_registry = AgentRegistry()
agent_registry.register(SupervisorAgent())
agent_registry.register(IntelligenceAgent())
```

## Agent Context

`AgentResponse` schema (`backend/shared/llm/schemas.py`):

| Field | Type | Description |
|-------|------|-------------|
| content | str | The agent's response text |
| citations | list[Citation] | Cited sources with ID, type, title, relevance |
| confidence | float | 0.0-1.0 confidence score |
| tool_calls | list[ToolCall] | Tools the agent called |
| tool_results | list[ToolResult] | Results from tool executions |
| agent_name | str | Name of the agent |
| conversation_id | str | Conversation identifier |
| metadata | dict | LLM metrics and other metadata |
