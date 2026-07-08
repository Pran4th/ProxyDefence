import tiktoken
from backend.shared.llm.config import LLMConfig


MODEL_COST_PER_1K_TOKENS = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "claude-3-5-sonnet-latest": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-latest": {"input": 0.00025, "output": 0.00125},
    "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
    "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
    "mixtral-8x7b-32768": {"input": 0.00027, "output": 0.00027},
    "gemma2-9b-it": {"input": 0.00005, "output": 0.00008},
}

ENCODING_CACHE: dict[str, tiktoken.Encoding] = {}


def _get_encoding(model: str) -> tiktoken.Encoding:
    if model not in ENCODING_CACHE:
        try:
            if model.startswith("gpt"):
                ENCODING_CACHE[model] = tiktoken.encoding_for_model(model)
            else:
                ENCODING_CACHE[model] = tiktoken.get_encoding("cl100k_base")
        except Exception:
            ENCODING_CACHE[model] = tiktoken.get_encoding("cl100k_base")
    return ENCODING_CACHE[model]


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    if not text:
        return 0
    try:
        encoding = _get_encoding(model)
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o") -> float:
    rates = MODEL_COST_PER_1K_TOKENS.get(model, MODEL_COST_PER_1K_TOKENS["gpt-4o"])
    cost = (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"]
    return round(cost, 6)


def truncate_context(text: str, max_tokens: int = 32000, model: str = "gpt-4o") -> str:
    if not text:
        return ""
    tokens = count_tokens(text, model)
    if tokens <= max_tokens:
        return text
    encoding = _get_encoding(model)
    encoded = encoding.encode(text)
    truncated = encoded[:max_tokens]
    return encoding.decode(truncated)
