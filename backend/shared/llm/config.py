import os
from dataclasses import dataclass, field
from typing import Literal


ModelName = Literal[
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "claude-3-5-sonnet-latest",
    "claude-3-haiku-latest",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

TemperaturePreset = Literal["precise", "balanced", "creative"]


@dataclass
class LLMSettings:
    """Per-model configuration overrides."""

    model: ModelName = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4096
    top_p: float = 0.95
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


TEMPERATURE_PRESETS: dict[TemperaturePreset, float] = {
    "precise": 0.1,
    "balanced": 0.3,
    "creative": 0.7,
}


@dataclass
class LLMConfig:
    """Global LLM configuration loaded from environment."""

    openai_api_key: str = ""
    openai_organization: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    default_model: ModelName = "llama-3.3-70b-versatile"
    fallback_model: ModelName = "llama-3.1-8b-instant"
    max_retries: int = 3
    request_timeout: float = 60.0
    stream_timeout: float = 120.0
    max_tokens_per_response: int = 4096
    max_context_tokens: int = 64000
    enable_fallbacks: bool = True
    log_prompts: bool = False
    log_responses: bool = False
    cost_tracking_enabled: bool = True

    _instance: "LLMConfig | None" = None

    @classmethod
    def load(cls) -> "LLMConfig":
        if cls._instance is not None:
            return cls._instance
        cfg = cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_organization=os.getenv("OPENAI_ORGANIZATION", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            default_model=os.getenv("LLM_DEFAULT_MODEL", "gpt-4o"),
            fallback_model=os.getenv("LLM_FALLBACK_MODEL", "gpt-4o-mini"),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            request_timeout=float(os.getenv("LLM_REQUEST_TIMEOUT", "60")),
            stream_timeout=float(os.getenv("LLM_STREAM_TIMEOUT", "120")),
            max_tokens_per_response=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            max_context_tokens=int(os.getenv("LLM_MAX_CONTEXT", "64000")),
            enable_fallbacks=os.getenv("LLM_ENABLE_FALLBACKS", "true").lower() == "true",
            log_prompts=os.getenv("LLM_LOG_PROMPTS", "false").lower() == "true",
            log_responses=os.getenv("LLM_LOG_RESPONSES", "false").lower() == "true",
            cost_tracking_enabled=os.getenv("LLM_COST_TRACKING", "true").lower() == "true",
        )
        cls._instance = cfg
        return cfg

    def settings_for(self, model: ModelName | None = None, temperature_preset: TemperaturePreset | None = None) -> LLMSettings:
        return LLMSettings(
            model=model or self.default_model,
            temperature=TEMPERATURE_PRESETS.get(temperature_preset or "balanced", 0.3),
            max_tokens=self.max_tokens_per_response,
        )
