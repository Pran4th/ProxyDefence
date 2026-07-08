from __future__ import annotations

import time
from typing import Any

from backend.shared.llm.schemas import AgentMessage, Citation


class ConversationMemory:
    """In-memory conversation history with sliding window context management."""

    def __init__(self, max_messages: int = 50, max_tokens: int = 32000):
        self._messages: list[AgentMessage] = []
        self._max_messages = max_messages
        self._max_tokens = max_tokens
        self._last_access = time.time()
        self._metadata: dict[str, Any] = {}
        self._summarized: bool = False

    def add_message(self, message: AgentMessage) -> None:
        self._messages.append(message)
        self._last_access = time.time()
        if len(self._messages) > self._max_messages:
            self._messages.pop(0)

    def add_user_message(self, content: str) -> AgentMessage:
        msg = AgentMessage(role="user", content=content)
        self.add_message(msg)
        return msg

    def add_assistant_message(self, content: str, citations: list[Citation] | None = None) -> AgentMessage:
        msg = AgentMessage(role="assistant", content=content, citations=citations)
        self.add_message(msg)
        return msg

    def add_tool_result(self, tool_name: str, tool_call_id: str, success: bool, output: Any, error: str | None = None) -> AgentMessage:
        msg = AgentMessage(
            role="tool",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            content=str(output) if success else error,
        )
        self.add_message(msg)
        return msg

    def get_history(self, max_messages: int | None = None) -> list[AgentMessage]:
        limit = max_messages or self._max_messages
        return self._messages[-limit:]

    def to_openai_messages(self, system_prompt: str | None = None, max_messages: int | None = None) -> list[dict]:
        result: list[dict] = []
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        for msg in self.get_history(max_messages):
            entry: dict = {"role": msg.role}
            if msg.role == "tool":
                entry["content"] = msg.content or ""
            elif msg.tool_calls:
                entry["content"] = msg.content or ""
                entry["tool_calls"] = [
                    {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": str(tc.arguments)}}
                    for tc in msg.tool_calls
                ]
            else:
                entry["content"] = msg.content or ""
            result.append(entry)
        return result

    def clear(self) -> None:
        self._messages.clear()
        self._summarized = False

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def is_stale(self, max_age_seconds: int = 3600) -> bool:
        return (time.time() - self._last_access) > max_age_seconds

    @property
    def is_summarized(self) -> bool:
        return self._summarized

    def mark_summarized(self) -> None:
        self._summarized = True


class MemoryStore:
    """Simple in-memory store for conversation memories, keyed by conversation_id."""

    def __init__(self):
        self._stores: dict[str, ConversationMemory] = {}

    def get_or_create(self, conversation_id: str) -> ConversationMemory:
        if conversation_id not in self._stores:
            self._stores[conversation_id] = ConversationMemory()
        return self._stores[conversation_id]

    def get(self, conversation_id: str) -> ConversationMemory | None:
        return self._stores.get(conversation_id)

    def remove(self, conversation_id: str) -> None:
        self._stores.pop(conversation_id, None)

    def cleanup_stale(self, max_age_seconds: int = 3600) -> int:
        before = len(self._stores)
        self._stores = {k: v for k, v in self._stores.items() if not v.is_stale(max_age_seconds)}
        return before - len(self._stores)


memory_store = MemoryStore()
