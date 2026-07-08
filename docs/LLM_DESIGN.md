# LLM Design

The LLM layer uses the OpenAI Python SDK (`AsyncOpenAI`) which is compatible with any OpenAI-compatible API provider. By default, the project is configured for **Groq** (fast, free-tier inference), but can be swapped to OpenAI, Anthropic, Ollama, or any OpenAI-compatible endpoint by changing `OPENAI_BASE_URL` and `OPENAI_API_KEY`.

## Configuration

**File:** `backend/shared/llm/config.py`

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| OPENAI_API_KEY | — | API key (Groq, OpenAI, or any OpenAI-compatible provider) |
| OPENAI_BASE_URL | https://api.groq.com/openai/v1 | API base URL |
| LLM_DEFAULT_MODEL | llama-3.3-70b-versatile | Default LLM model |
| LLM_FALLBACK_MODEL | llama-3.1-8b-instant | Fallback model on rate-limit |
| LLM_MAX_RETRIES | 3 | Max retries on failure |
| LLM_REQUEST_TIMEOUT | 60 | Request timeout in seconds |
| LLM_STREAM_TIMEOUT | 120 | Streaming timeout in seconds |
| LLM_MAX_TOKENS | 4096 | Max output tokens |

## Temperature Presets

| Preset | Temperature | Use Case |
|--------|-------------|----------|
| precise | 0.1 | Factual analysis, tool calling |
| balanced | 0.3 | Default — general queries |
| creative | 0.7 | Summarization, explanation |

## Client

**File:** `backend/shared/llm/client.py`

`LLMClient` wraps `AsyncOpenAI` (OpenAI-compatible SDK):

- Works with Groq, OpenAI, Anthropic (via proxy), Ollama, or any OpenAI-compatible endpoint
- **Retry logic**: exponential backoff up to `max_retries + 1` attempts
- **Error handling**: RateLimitError → auto-retry, AuthenticationError → fail fast, Timeout → retry
- **Streaming**: async generator with per-token callbacks via `on_token` and `on_tool_call`
- **Cost tracking**: per-model pricing from `MODEL_COST_PER_1K_TOKENS` table
- **Token counting**: uses tiktoken for GPT models, cl100k_base for others

## Supported Models

### OpenAI
| Model | Input Cost/1K | Output Cost/1K |
|-------|--------------|---------------|
| gpt-4o | $0.0025 | $0.01 |
| gpt-4o-mini | $0.00015 | $0.0006 |
| gpt-4-turbo | $0.01 | $0.03 |

### Anthropic
| Model | Input Cost/1K | Output Cost/1K |
|-------|--------------|---------------|
| claude-3-5-sonnet | $0.003 | $0.015 |
| claude-3-haiku | $0.00025 | $0.00125 |

### Groq (OpenAI-Compatible)
| Model | Input Cost/1K | Output Cost/1K | Context |
|-------|--------------|---------------|---------|
| llama-3.3-70b-versatile | $0.00059 | $0.00079 | 8192 |
| llama-3.1-8b-instant | $0.00005 | $0.00008 | 8192 |
| mixtral-8x7b-32768 | $0.00027 | $0.00027 | 32768 |
| gemma2-9b-it | $0.00005 | $0.00008 | 8192 |

## Memory

**File:** `backend/shared/llm/memory.py`

`ConversationMemory` — in-memory sliding window:
- Max 50 messages per conversation
- Max 32000 tokens context window
- TTL-based cleanup (stale after 1 hour)
- `MemoryStore` singleton for multi-conversation management

## Prompts

**File:** `backend/shared/llm/prompts.py`

`PromptLibrary` — centralized template registry:
- Templates with `{variable}` substitution
- Built-in templates: `query_analysis`, `threat_assessment`, `executive_summary`
- `SYSTEM_PROMPTS` dict for agent system prompts

## Utils

**File:** `backend/shared/llm/utils.py`

- `count_tokens(text, model)` — accurate token counting
- `estimate_cost(input_tokens, output_tokens, model)` — cost estimation
- `truncate_context(text, max_tokens)` — safe context truncation
