# Request Flow

## Complete Query Lifecycle

### Step 1: User sends query
```
POST /copilot/query
{
  "question": "What is the current threat level in the South China Sea?",
  "conversation_id": 42
}
```

### Step 2: Copilot Router
`backend/api/copilot/router.py` — validates auth, creates CopilotService, delegates to `service.query()`

### Step 3: Copilot Service
`backend/api/copilot/service.py` — creates IntelligenceAgent, sets conversation, calls `agent.run()`

### Step 4: Conversation Memory
`backend/shared/llm/memory.py` — retrieves or creates `ConversationMemory` for conversation_id. Adds user message to history.

### Step 5: LLM Chat (Round 1)
`backend/shared/llm/client.py` — sends messages + 25 tool definitions to OpenAI GPT-4o.
LLM decides which tools to call (e.g., `search_articles`, `get_entity_risk_profile`, `get_active_signals`).

### Step 6: Tool Execution
`backend/api/tools/registry.py` — executes each tool call.
Each tool makes an HTTP GET to the modular API (port 8000), which proxies to the appropriate backend.

### Step 7: LLM Chat (Round 2)
Tool results + updated conversation history sent back to LLM.
LLM synthesizes final response with citations.

### Step 8: Response Assembly
`backend/shared/llm/schemas.py` — `AgentResponse` built with content, citations, confidence, metrics.

### Step 9: Persistence
`backend/api/copilot/repository.py` — user message + assistant response saved to `copilot_messages` table.

### Step 10: Response Returned
```json
{
  "question": "What is the current threat level in the South China Sea?",
  "summary": "Based on current intelligence, the threat level in the South China Sea is elevated...",
  "citations": [
    {"source_id": "123", "source_type": "article", "title": "...", "relevance": 0.95}
  ],
  "confidence": 0.87,
  "tool_calls": [...],
  "agent_name": "intelligence",
  "llm_metrics": {"model": "gpt-4o", "input_tokens": 2048, ...}
}
```

## Streaming Flow

Same as above but:
- Round 1 streams tokens + tool calls as SSE events
- After tool results, Round 2 streams final tokens as SSE events
- Client renders tokens in real-time

## Error Handling

| Error | HTTP Status | Behavior |
|-------|-------------|----------|
| Rate Limit | 429 | Auto-retry up to 3 times with exponential backoff |
| Timeout | 504 | Retry once, then return error |
| Auth Failed | 401 | Fail immediately |
| API Error 5xx | 502 | Retry up to 2 times |
| Tool Not Found | 500 | Return error in tool result, continue |

## Metrics Collected

Per request:
- `llm_request_latency_seconds` — histogram by service/model
- `llm_token_count` — histogram by service/model/type
- `llm_cost_total_dollars` — gauge (accumulated)
- `llm_requests_total` — gauge by service/status
- `tool_execution_latency_seconds` — histogram by service/tool_name
- `tool_execution_total` — gauge by service/tool_name/status
- `agent_run_latency_seconds` — histogram by service/agent_name
