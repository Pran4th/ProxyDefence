from __future__ import annotations

from typing import Any

from backend.shared.llm.client import LLMClient
from backend.shared.llm.utils import count_tokens


SUMMARIZATION_PROMPT = """Summarize the following conversation, preserving key facts, decisions, and unresolved questions.

Conversation:
{text}

Summary:"""


class ContextCompressor:
    """Compresses conversation context when it exceeds token limits. Supports summarization and sliding window."""

    def __init__(self, llm_client: LLMClient | None = None, max_tokens: int = 32000):
        self._llm = llm_client
        self._max_tokens = max_tokens

    def should_compress(self, messages: list[dict]) -> bool:
        total = sum(count_tokens(m.get("content", "")) for m in messages)
        return total > self._max_tokens

    def sliding_window(self, messages: list[dict], window_size: int = 20) -> list[dict]:
        if len(messages) <= window_size:
            return messages
        system = [m for m in messages if m.get("role") == "system"]
        recent = messages[-window_size:]
        return system + recent

    async def summarize(self, messages: list[dict], target_length: int = 500) -> str:
        if not self._llm:
            return self._simple_summary(messages)
        text = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')[:500]}"
            for m in messages[-20:]
        )
        prompt = SUMMARIZATION_PROMPT.format(text=text[:8000])
        content, _, _ = await self._llm.chat(
            messages=[{"role": "user", "content": prompt}],
        )
        return content[:target_length]

    def _simple_summary(self, messages: list[dict]) -> str:
        user_msgs = sum(1 for m in messages if m.get("role") == "user")
        asst_msgs = sum(1 for m in messages if m.get("role") == "assistant")
        tool_msgs = sum(1 for m in messages if m.get("role") == "tool")
        return f"Conversation: {user_msgs} user messages, {asst_msgs} assistant messages, {tool_msgs} tool calls"
