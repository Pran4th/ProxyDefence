from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Citation(BaseModel):
    """A source citation for an LLM-generated claim."""

    source_id: str = Field(description="Unique identifier of the source document")
    source_type: str = Field(description="Type of source: article, entity, simulation, etc.")
    title: str = Field(description="Title or name of the source")
    relevance: float = Field(default=1.0, ge=0, le=1, description="Relevance score of this source")
    url: str | None = Field(default=None, description="URL to the source")
    snippet: str | None = Field(default=None, description="Relevant excerpt from the source")


class ToolCall(BaseModel):
    """A request from the LLM to execute a tool."""

    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    name: str = Field(description="Tool name to execute")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ToolResult(BaseModel):
    """The result of executing a tool call."""

    tool_call_id: str = Field(default="", description="Matching ToolCall.id")
    tool_name: str = Field(default="", description="Name of the tool that was executed")
    success: bool = Field(description="Whether execution succeeded")
    output: Any = Field(default=None, description="Tool output data")
    error: str | None = Field(default=None, description="Error message if failed")
    duration_ms: float = Field(default=0, description="Execution time in milliseconds")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @model_validator(mode="before")
    @classmethod
    def _map_data_to_output(cls, data: Any) -> Any:
        if isinstance(data, dict) and "data" in data and "output" not in data:
            data["output"] = data.pop("data")
        return data


class AgentMessage(BaseModel):
    """A message in the agent conversation history."""

    role: str = Field(description="user, assistant, system, or tool")
    content: str | None = Field(default=None, description="Message content")
    tool_calls: list[ToolCall] | None = Field(default=None, description="Tool calls made by assistant")
    tool_call_id: str | None = Field(default=None, description="ID of tool call this result belongs to")
    tool_name: str | None = Field(default=None, description="Name of tool this result belongs to")
    citations: list[Citation] | None = Field(default=None, description="Source citations")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentContext(BaseModel):
    """Context for an agent invocation passed between agents."""

    conversation_id: str | None = Field(default=None, description="Conversation ID from copilot_conversations")
    user_id: int | None = Field(default=None, description="User ID making the request")
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique session identifier")
    query: str = Field(description="The user's original query")
    agent_chain: list[str] = Field(default_factory=list, description="Agents involved in this request")
    tool_results: list[ToolResult] = Field(default_factory=list, description="Accumulated tool results")
    citations: list[Citation] = Field(default_factory=list, description="Accumulated citations")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")


class AgentResponse(BaseModel):
    """Final response from an agent. Supports both old (content) and new (answer) field names."""

    answer: str = Field(description="The agent's natural language response in markdown")
    citations: list[Citation] = Field(default_factory=list, description="Source citations")
    confidence: float = Field(default=0.5, ge=0, le=1, description="Confidence in the response")
    suggested_actions: list[str] = Field(default_factory=list, description="Recommended next actions")
    follow_up_questions: list[str] = Field(default_factory=list, description="Suggested follow-up questions")
    agent_chain: list[str] = Field(default_factory=list, description="Agents involved")
    tool_executions: list[dict] = Field(default_factory=list, description="Tool execution trace")
    latency_ms: float = Field(default=0, description="Total processing time")
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    estimated_cost: float = Field(default=0, description="Estimated API cost in USD")

    @model_validator(mode="before")
    @classmethod
    def _map_old_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "content" in data and "answer" not in data:
                data["answer"] = data.pop("content")
            if "agent_name" in data and not data.get("agent_chain"):
                data["agent_chain"] = [data.pop("agent_name")]
            if "tool_results" in data:
                data["tool_executions"] = [
                    {
                        "tool_name": r.tool_name if hasattr(r, "tool_name") else r.get("tool_name", ""),
                        "success": r.success if hasattr(r, "success") else r.get("success", False),
                        "output": r.output if hasattr(r, "output") else r.get("output"),
                        "error": r.error if hasattr(r, "error") else r.get("error"),
                    }
                    for r in (data.pop("tool_results", []) or [])
                ]
        return data
