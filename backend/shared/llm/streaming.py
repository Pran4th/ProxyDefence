from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from enum import Enum
from typing import Any


class StreamEvent(str, Enum):
    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_STATUS = "agent_status"
    CITATION = "citation"
    CONFIDENCE = "confidence"
    ERROR = "error"
    DONE = "done"
    METADATA = "metadata"


class StreamingHandler:
    """Builds Server-Sent Events for agent streaming responses."""

    def __init__(self):
        self._events: list[str] = []

    def token(self, text: str) -> str:
        return self._make_event(StreamEvent.TOKEN, text)

    def tool_call(self, tool_name: str, arguments: dict) -> str:
        return self._make_event(StreamEvent.TOOL_CALL, {"name": tool_name, "arguments": arguments})

    def tool_result(self, tool_name: str, success: bool, summary: str) -> str:
        return self._make_event(StreamEvent.TOOL_RESULT, {"name": tool_name, "success": success, "summary": summary})

    def agent_status(self, agent_name: str, status: str, message: str = "") -> str:
        return self._make_event(StreamEvent.AGENT_STATUS, {"agent": agent_name, "status": status, "message": message})

    def citation(self, source_id: str, source_type: str, title: str, relevance: float) -> str:
        return self._make_event(StreamEvent.CITATION, {
            "source_id": source_id, "source_type": source_type, "title": title, "relevance": relevance,
        })

    def confidence(self, score: float) -> str:
        return self._make_event(StreamEvent.CONFIDENCE, {"score": score})

    def error(self, message: str) -> str:
        return self._make_event(StreamEvent.ERROR, {"message": message})

    def done(self) -> str:
        return self._make_event(StreamEvent.DONE, {})

    def metadata(self, data: dict) -> str:
        return self._make_event(StreamEvent.METADATA, data)

    def _make_event(self, event_type: StreamEvent, data: Any) -> str:
        payload = json.dumps({"type": event_type.value, "value": data})
        return f"data: {payload}\n\n"

    def build_generator(self, agent_run) -> AsyncGenerator[str, None]:
        """Wrap an agent run into an SSE generator."""
        return self._agent_to_sse(agent_run)

    async def _agent_to_sse(self, agent_run) -> AsyncGenerator[str, None]:
        async for event in agent_run:
            if isinstance(event, str):
                yield self.token(event)
            elif isinstance(event, dict):
                etype = event.get("type")
                if etype == "token":
                    yield self.token(event["value"])
                elif etype == "tool_call":
                    yield self.tool_call(event["name"], event.get("arguments", {}))
                elif etype == "tool_result":
                    yield self.tool_result(event["name"], event.get("success", True), event.get("summary", ""))
                elif etype == "agent_status":
                    yield self.agent_status(event["agent"], event["status"], event.get("message", ""))
                elif etype == "citation":
                    yield self.citation(event["source_id"], event["source_type"], event["title"], event.get("relevance", 1.0))
                elif etype == "confidence":
                    yield self.confidence(event["score"])
                elif etype == "error":
                    yield self.error(event["message"])
            yield ""
        yield self.done()
