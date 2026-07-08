class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(self, message: str, original: Exception | None = None):
        self.original = original
        super().__init__(message)


class LLMTimeoutError(LLMError):
    """Raised when an LLM request times out."""

    def __init__(self, timeout_seconds: float):
        super().__init__(f"LLM request timed out after {timeout_seconds}s")


class LLMConfigurationError(LLMError):
    """Raised when LLM configuration is invalid or missing."""

    def __init__(self, missing_key: str):
        super().__init__(f"LLM configuration error: {missing_key} is not set")


class LLMAuthenticationError(LLMError):
    """Raised when API key authentication fails."""

    def __init__(self, provider: str):
        super().__init__(f"LLM authentication failed for {provider}")


class LLMRateLimitError(LLMError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, provider: str, retry_after: float = 0):
        self.retry_after = retry_after
        super().__init__(f"LLM rate limit exceeded for {provider}")


class LLMContentFilterError(LLMError):
    """Raised when the LLM response was filtered by content policy."""

    def __init__(self, provider: str, reason: str = ""):
        super().__init__(f"LLM content filtered by {provider}: {reason}")


class LLMToolExecutionError(LLMError):
    """Raised when an agent tool call fails during execution."""

    def __init__(self, tool_name: str, tool_args: dict, message: str):
        self.tool_name = tool_name
        self.tool_args = tool_args
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")
