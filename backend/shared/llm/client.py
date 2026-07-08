from __future__ import annotations

import json
import time
import traceback
from collections.abc import AsyncGenerator
from typing import Any, Callable

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError
from openai.types.chat import ChatCompletionMessageToolCall

from backend.shared.llm.config import LLMConfig, LLMSettings
from backend.shared.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from backend.shared.llm.schemas import ToolCall, ToolResult
from backend.shared.llm.utils import count_tokens, estimate_cost
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Reusable LLM client with streaming, tool calling, retry logic, and cost tracking."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig.load()
        self._client: AsyncOpenAI | None = None
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self._total_requests = 0

    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if not self.config.openai_api_key:
            raise LLMConfigurationError("OPENAI_API_KEY")
        self._client = AsyncOpenAI(
            api_key=self.config.openai_api_key,
            organization=self.config.openai_organization or None,
            base_url=self.config.openai_base_url,
            timeout=self.config.request_timeout,
        )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        settings: LLMSettings | None = None,
        tools: list[dict] | None = None,
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
        on_tool_call: Callable[[ToolCall], None] | None = None,
    ) -> tuple[str, list[ToolCall] | None, dict]:
        s = settings or self.config.settings_for()
        client = self._ensure_client()
        last_error: Exception | None = None
        start_time = time.time()

        for attempt in range(1, self.config.max_retries + 2):
            try:
                kwargs: dict = {
                    "model": s.model,
                    "messages": messages,
                    "temperature": s.temperature,
                    "max_tokens": s.max_tokens,
                    "top_p": s.top_p,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                if stream:
                    return await self._stream_chat(client, kwargs, s, on_token, on_tool_call, start_time)

                response = await client.chat.completions.create(**kwargs)
                self._total_requests += 1
                usage = response.usage
                if usage:
                    self._total_input_tokens += usage.prompt_tokens
                    self._total_output_tokens += usage.completion_tokens
                    self._total_cost += estimate_cost(usage.prompt_tokens, usage.completion_tokens, s.model)

                choice = response.choices[0]
                content = choice.message.content or ""
                tool_calls = self._parse_tool_calls(choice.message.tool_calls)

                latency = (time.time() - start_time) * 1000
                metrics = {
                    "model": s.model,
                    "input_tokens": usage.prompt_tokens if usage else 0,
                    "output_tokens": usage.completion_tokens if usage else 0,
                    "cost": self._total_cost,
                    "latency_ms": round(latency, 1),
                    "attempt": attempt,
                }
                return content, tool_calls, metrics

            except RateLimitError as e:
                last_error = LLMRateLimitError("OpenAI", retry_after=3)
                logger.warning("LLM rate limited (attempt %d/%d)", attempt, self.config.max_retries + 1)
                if attempt <= self.config.max_retries:
                    time.sleep(3 * attempt)
                    continue
                break

            except APITimeoutError as e:
                last_error = LLMTimeoutError(self.config.request_timeout)
                logger.warning("LLM timeout (attempt %d/%d)", attempt, self.config.max_retries + 1)
                if attempt <= self.config.max_retries:
                    time.sleep(1)
                    continue
                break

            except APIError as e:
                if e.status_code == 401:
                    raise LLMAuthenticationError("OpenAI") from e
                last_error = LLMError(f"OpenAI API error: {e}", original=e)
                logger.warning("LLM API error (attempt %d/%d): %s", attempt, self.config.max_retries + 1, e)
                if attempt <= self.config.max_retries and e.status_code and e.status_code >= 500:
                    time.sleep(2 * attempt)
                    continue
                break

            except Exception as e:
                last_error = LLMError(f"Unexpected LLM error: {e}", original=e)
                logger.error("LLM unexpected error: %s\n%s", e, traceback.format_exc())
                break

        raise last_error or LLMError("LLM request failed after all retries")

    async def _stream_chat(
        self,
        client: AsyncOpenAI,
        kwargs: dict,
        settings: LLMSettings,
        on_token: Callable[[str], None] | None,
        on_tool_call: Callable[[ToolCall], None] | None,
        start_time: float,
    ) -> tuple[str, list[ToolCall] | None, dict]:
        content_parts: list[str] = []
        tool_calls_map: dict[int, ToolCall] = {}
        input_tokens = 0
        output_tokens = 0

        stream = await client.chat.completions.create(**kwargs, stream=True)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if delta.content:
                content_parts.append(delta.content)
                if on_token:
                    on_token(delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = ToolCall(
                            id=tc_delta.id or f"call_{idx}",
                            name=tc_delta.function.name or "",
                            arguments={},
                        )
                    tc = tool_calls_map[idx]
                    if tc_delta.id:
                        tc.id = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        tc.name = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        current_args = tc.arguments or {}
                        if isinstance(current_args, dict):
                            try:
                                new_args = json.loads(tc_delta.function.arguments)
                                current_args.update(new_args)
                            except json.JSONDecodeError:
                                pass
                            tc.arguments = current_args

            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0

        self._total_requests += 1
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost += estimate_cost(input_tokens, output_tokens, settings.model)

        final_tool_calls = list(tool_calls_map.values()) if tool_calls_map else None
        if final_tool_calls and on_tool_call:
            for tc in final_tool_calls:
                on_tool_call(tc)

        latency = (time.time() - start_time) * 1000
        content = "".join(content_parts)
        metrics = {
            "model": settings.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": self._total_cost,
            "latency_ms": round(latency, 1),
            "streamed": True,
        }
        return content, final_tool_calls, metrics

    def _parse_tool_calls(self, raw_calls: list[ChatCompletionMessageToolCall] | None) -> list[ToolCall] | None:
        if not raw_calls:
            return None
        result = []
        for tc in raw_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            result.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return result if result else None

    @property
    def stats(self) -> dict:
        return {
            "total_requests": self._total_requests,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_cost": round(self._total_cost, 4),
        }

    def reset_stats(self) -> None:
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self._total_requests = 0
