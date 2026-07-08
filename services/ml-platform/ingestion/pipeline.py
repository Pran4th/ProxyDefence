from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.shared.logging_config import get_logger

from ingestion.errors import IngestionConfigError

logger = get_logger(__name__)


@dataclass
class PipelineStep:
    name: str
    step_type: str
    handler: Callable
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    retry_config: dict = field(default_factory=lambda: {"max_retries": 3, "backoff": 1.0})
    timeout_seconds: float = 300


@dataclass
class PipelineStepResult:
    step_name: str
    step_type: str
    status: str
    started_at: datetime
    completed_at: datetime
    duration_ms: float = 0.0
    records_processed: int = 0
    output_keys: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class IngestionPipeline:
    def __init__(self, name: str, description: str = ""):
        self._name = name
        self._description = description
        self._steps: dict[str, PipelineStep] = {}

    def add_step(self, step: PipelineStep):
        if step.name in self._steps:
            raise IngestionConfigError(
                f"Step '{step.name}' already exists in pipeline '{self._name}'"
            )
        self._steps[step.name] = step

    def get_steps(self) -> list[PipelineStep]:
        return list(self._steps.values())

    def get_execution_order(self) -> list[PipelineStep]:
        step_names = list(self._steps.keys())
        dep_map: dict[str, set[str]] = {name: set() for name in step_names}

        for name, step in self._steps.items():
            for other_name, other_step in self._steps.items():
                if name == other_name:
                    continue
                if any(inp in other_step.outputs for inp in step.inputs):
                    dep_map[name].add(other_name)

        in_degree = {name: len(deps) for name, deps in dep_map.items()}
        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        order: list[PipelineStep] = []

        while queue:
            name = queue.popleft()
            order.append(self._steps[name])
            for other_name, other_deps in dep_map.items():
                if name in other_deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)

        if len(order) != len(step_names):
            logger.warning(
                "cycle detected in pipeline '%s', falling back to insertion order",
                self._name,
            )
            return list(self._steps.values())

        return order

    def validate(self) -> list[str]:
        errors: list[str] = []

        for name, step in self._steps.items():
            for inp in step.inputs:
                found = any(
                    inp in other_step.outputs
                    for other_name, other_step in self._steps.items()
                    if other_name != name
                )
                if not found:
                    errors.append(
                        f"Step '{name}' requires input '{inp}' which is not produced by any step"
                    )

        step_names = list(self._steps.keys())
        dep_map: dict[str, set[str]] = {name: set() for name in step_names}
        for name, step in self._steps.items():
            for other_name, other_step in self._steps.items():
                if name == other_name:
                    continue
                if any(inp in other_step.outputs for inp in step.inputs):
                    dep_map[name].add(other_name)

        in_degree = {name: len(deps) for name, deps in dep_map.items()}
        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        visited = 0
        while queue:
            name = queue.popleft()
            visited += 1
            for other_name, other_deps in dep_map.items():
                if name in other_deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)

        if visited != len(step_names):
            errors.append("Pipeline contains a cycle in step dependencies")

        return errors

    def to_dict(self) -> dict:
        steps = []
        for step in self._steps.values():
            steps.append({
                "name": step.name,
                "step_type": step.step_type,
                "inputs": step.inputs,
                "outputs": step.outputs,
                "config": step.config,
                "retry_config": step.retry_config,
                "timeout_seconds": step.timeout_seconds,
            })
        return {
            "name": self._name,
            "description": self._description,
            "steps": steps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IngestionPipeline":
        pipeline = cls(name=data["name"], description=data.get("description", ""))
        for step_data in data.get("steps", []):
            step = PipelineStep(
                name=step_data["name"],
                step_type=step_data["step_type"],
                handler=lambda ctx, pool: None,
                inputs=step_data.get("inputs", []),
                outputs=step_data.get("outputs", []),
                config=step_data.get("config", {}),
                retry_config=step_data.get(
                    "retry_config", {"max_retries": 3, "backoff": 1.0}
                ),
                timeout_seconds=step_data.get("timeout_seconds", 300),
            )
            pipeline.add_step(step)
        return pipeline

    def to_yaml(self) -> str:
        import yaml
        return yaml.dump(self.to_dict(), default_flow_style=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "IngestionPipeline":
        import yaml
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description
