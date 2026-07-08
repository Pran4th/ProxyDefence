from __future__ import annotations

import time
from typing import Any


class ExecutionMemory:
    """Stores execution plan history for a conversation. Separates execution context from conversation history."""

    def __init__(self, max_plans: int = 20):
        self._plans: list[dict] = []
        self._current_plan: dict | None = None
        self._max_plans = max_plans
        self._last_access = time.time()

    def start_plan(self, plan: dict) -> None:
        self._current_plan = {
            "plan": plan,
            "steps": [],
            "started_at": time.time(),
            "completed_at": None,
            "status": "running",
        }

    def add_step_result(self, step_result: dict) -> None:
        if self._current_plan:
            self._current_plan["steps"].append(step_result)

    def complete_plan(self, output: Any = None, error: str | None = None) -> None:
        if self._current_plan:
            self._current_plan["completed_at"] = time.time()
            self._current_plan["status"] = "failed" if error else "completed"
            self._current_plan["output"] = output
            self._current_plan["error"] = error
            self._plans.append(self._current_plan)
            if len(self._plans) > self._max_plans:
                self._plans.pop(0)
            self._current_plan = None

    def get_current_plan(self) -> dict | None:
        return self._current_plan

    def get_plan_history(self, max_plans: int | None = None) -> list[dict]:
        limit = max_plans or self._max_plans
        return self._plans[-limit:]

    def clear(self) -> None:
        self._plans.clear()
        self._current_plan = None
