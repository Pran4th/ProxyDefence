# AI Architecture

ProxyDefence transforms from a deterministic rule-based platform to an AI-driven intelligence system using a multi-agent LLM architecture.

## Architecture Overview

```
User Query
    |
    v
Copilot API (POST /copilot/query)
    |
    v
Supervisor Agent
    |
    |-- Intent Detection (LLM)
    |-- Task Planning (LLM)
    |-- Tool Selection (LLM)
    |
    v
Intelligence Agent  (Specialist)
    |
    |-- Tool Calls (25+ tools)
    |-- RAG Context (Hybrid Search)
    |
    v
LLM Client (OpenAI GPT-4o)
    |
    v
Response Synthesis
    |
    v
User Response (JSON or SSE Stream)
```

## Core Components

### Shared LLM Layer (`backend/shared/llm/`)
- `LLMConfig` — environment-based configuration (model, temperature, retries)
- `LLMClient` — AsyncOpenAI wrapper with streaming, tool calling, retry logic, cost tracking
- `ConversationMemory` — sliding window context management
- `PromptLibrary` — centralized, versioned prompt templates
- `StreamingHandler` — SSE event builder for streaming responses

### Tool Layer (`backend/api/tools/`)
- 25 tools mapped to existing REST API endpoints
- Categories: Search, Intelligence, Energy, Analytics, Graph
- Every tool calls the modular API (port 8000) which proxies to energy service

### Agent Framework (`backend/api/agents/`)
- `BaseAgent` — abstract base with sync/stream execution
- `SupervisorAgent` — orchestrator: intent detection, routing, tool delegation, response merging
- `IntelligenceAgent` — specialist: geopolitical threat assessment, entity research, risk explanation

### Hybrid RAG (`backend/api/rag/`)
- Dense retrieval: pgvector (bge-small-en-v1.5, 384d)
- Sparse retrieval: Elasticsearch BM25
- Knowledge Graph expansion: entity relationships
- Fusion: Reciprocal Rank Fusion (RRF)
- Future: cross-encoder re-ranking (bge-reranker-v2-m3)

### Copilot (`backend/api/copilot/`)
- Replaced rule-based keyword counting with LLM-powered Intelligence Agent
- Streaming SSE support for real-time responses
- Conversation persistence via `copilot_conversations` / `copilot_messages` tables
- Backward compatible API

### Observability (`backend/shared/observability/metrics.py`)
- LLM latency, token counts, cost, request counts
- Tool execution latency and counts
- Agent run latency
- RAG retrieval latency

## Data Flow

1. User sends query to `POST /copilot/query`
2. Copilot service creates Intelligence Agent
3. Agent loads conversation memory
4. LLM analyzes query, selects tools
5. Tools call existing REST endpoints (articles, analytics, search, entities, graph, energy, intelligence)
6. Tool results feed back into LLM context
7. LLM synthesizes final response with citations
8. Response streamed to user (SSE) or returned as JSON
9. Conversation saved to PostgreSQL

## Key Principles

- All claims come from tool outputs — LLM is for reasoning only
- No direct database queries from agents — always through existing APIs
- No mocked responses — every tool calls a real endpoint
- Backward compatible — existing API routes unchanged
