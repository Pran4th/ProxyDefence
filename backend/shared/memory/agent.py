from __future__ import annotations

from typing import Any


class AgentMemory:
    """Per-agent memory. Each specialist agent gets its own memory slice, isolated from conversation history."""

    def __init__(self, agent_name: str, max_records: int = 50):
        self._agent_name = agent_name
        self._records: list[dict] = []
        self._max_records = max_records
        self._state: dict[str, Any] = {}

    def record(self, event_type: str, data: Any) -> None:
        self._records.append({"type": event_type, "data": data, "agent": self._agent_name})
        if len(self._records) > self._max_records:
            self._records.pop(0)

    def set_state(self, key: str, value: Any) -> None:
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def get_recent(self, n: int = 10) -> list[dict]:
        return self._records[-n:]

    def clear(self) -> None:
        self._records.clear()
        self._state.clear()

    @property
    def agent_name(self) -> str:
        return self._agent_name


class AgentMemoryStore:
    """Manages memory for multiple agents across conversations."""

    def __init__(self):
        self._stores: dict[str, dict[str, AgentMemory]] = {}

    def get(self, conversation_id: str, agent_name: str) -> AgentMemory:
        if conversation_id not in self._stores:
            self._stores[conversation_id] = {}
        if agent_name not in self._stores[conversation_id]:
            self._stores[conversation_id][agent_name] = AgentMemory(agent_name)
        return self._stores[conversation_id][agent_name]

    def remove_conversation(self, conversation_id: str) -> None:
        self._stores.pop(conversation_id, None)

    def remove_agent(self, conversation_id: str, agent_name: str) -> None:
        if conversation_id in self._stores:
            self._stores[conversation_id].pop(agent_name, None)


agent_memory_store = AgentMemoryStore()
