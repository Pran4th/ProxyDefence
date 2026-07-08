from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class TraceNode:
    """A single node in the execution trace tree."""

    def __init__(self, node_type: str, label: str, parent_id: str | None = None):
        self.id = uuid.uuid4().hex[:12]
        self.node_type = node_type
        self.label = label
        self.parent_id = parent_id
        self._start_time = time.time()
        self.completed_at: str | None = None
        self.duration_ms: float = 0
        self.status: str = "pending"
        self.input: Any = None
        self.output: Any = None
        self.error: str | None = None
        self.children: list[TraceNode] = []
        self.metadata: dict[str, Any] = {}

    def complete(self, output: Any = None, error: str | None = None) -> None:
        self.completed_at = datetime.utcnow().isoformat()
        self.duration_ms = (time.time() - self._start_time) * 1000
        self.status = "failed" if error else "completed"
        self.output = output
        self.error = error


class ExecutionTracer:
    """Tracks every step of orchestration with proper parent-child nesting."""

    def __init__(self):
        self._root: TraceNode | None = None
        self._current_id: str | None = None
        self._nodes: dict[str, TraceNode] = {}
        self._start_time = time.time()
        self._id_stack: list[str] = []

    def start(self, label: str = "execution") -> str:
        node = TraceNode("execution", label)
        self._root = node
        self._nodes[node.id] = node
        self._current_id = node.id
        self._id_stack = [node.id]
        return node.id

    @contextmanager
    def span(self, node_type: str, label: str) -> Generator[TraceNode, None, None]:
        nid = self._add_node(node_type, label)
        node = self._nodes[nid]
        self._id_stack.append(nid)
        self._current_id = nid
        try:
            yield node
        except Exception as e:
            node.complete(error=str(e))
            raise
        finally:
            if self._id_stack and self._id_stack[-1] == nid:
                self._id_stack.pop()
            self._current_id = self._id_stack[-1] if self._id_stack else None

    def add_plan(self, label: str = "planning") -> TraceNode:
        nid = self._add_node("plan", label)
        return self._nodes[nid]

    def add_step(self, label: str, step_index: int) -> TraceNode:
        nid = self._add_node("step", label)
        self._nodes[nid].metadata["step_index"] = step_index
        return self._nodes[nid]

    def add_agent_call(self, agent_name: str) -> TraceNode:
        nid = self._add_node("agent", agent_name)
        return self._nodes[nid]

    def add_tool_call(self, tool_name: str) -> TraceNode:
        nid = self._add_node("tool", tool_name)
        return self._nodes[nid]

    def add_reflection(self, label: str = "reflection") -> TraceNode:
        nid = self._add_node("reflection", label)
        return self._nodes[nid]

    def add_reasoning_iteration(self, iteration: int) -> TraceNode:
        nid = self._add_node("reasoning", f"iteration_{iteration}")
        self._nodes[nid].metadata["iteration"] = iteration
        return self._nodes[nid]

    def end(self, node: TraceNode, output: Any = None, error: str | None = None) -> None:
        node.complete(output=output, error=error)

    def get_node(self, node_id: str) -> TraceNode | None:
        return self._nodes.get(node_id)

    def snapshot(self) -> dict:
        per_type = {}
        for n in self._nodes.values():
            t = n.node_type
            if t not in per_type:
                per_type[t] = {"count": 0, "total_ms": 0}
            per_type[t]["count"] += 1
            per_type[t]["total_ms"] += n.duration_ms

        return {
            "total_duration_ms": (time.time() - self._start_time) * 1000,
            "node_count": len(self._nodes),
            "root": self._to_dict(self._root) if self._root else None,
            "per_type": per_type,
        }

    def push_context(self, node_id: str) -> None:
        self._id_stack.append(node_id)
        self._current_id = node_id

    def pop_context(self) -> None:
        if self._id_stack:
            self._id_stack.pop()
        self._current_id = self._id_stack[-1] if self._id_stack else None

    def _add_node(self, node_type: str, label: str) -> str:
        node = TraceNode(node_type, label, parent_id=self._current_id)
        self._nodes[node.id] = node
        if self._current_id and self._current_id in self._nodes:
            self._nodes[self._current_id].children.append(node)
        return node.id

    def _to_dict(self, node: TraceNode) -> dict:
        return {
            "id": node.id,
            "type": node.node_type,
            "label": node.label,
            "status": node.status,
            "duration_ms": round(node.duration_ms, 1),
            "error": node.error,
            "metadata": node.metadata,
            "children": [self._to_dict(c) for c in node.children],
        }

    def get_per_type_summary(self) -> dict:
        summary = {}
        for n in self._nodes.values():
            t = n.node_type
            if t not in summary:
                summary[t] = {"count": 0, "total_ms": 0, "min_ms": float("inf"), "max_ms": 0}
            summary[t]["count"] += 1
            summary[t]["total_ms"] += n.duration_ms
            summary[t]["min_ms"] = min(summary[t]["min_ms"], n.duration_ms)
            summary[t]["max_ms"] = max(summary[t]["max_ms"], n.duration_ms)

        for v in summary.values():
            if v["count"] > 0:
                v["avg_ms"] = round(v["total_ms"] / v["count"], 1)
                v["total_ms"] = round(v["total_ms"], 1)
            del v["min_ms"]
            del v["max_ms"]

        return summary
