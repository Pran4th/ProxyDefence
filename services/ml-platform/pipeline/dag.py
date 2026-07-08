from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineStep:
    name: str
    func: Callable
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    cache_key: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineRunResult:
    step_name: str
    status: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float = 0.0
    error: str | None = None
    output: Any = None


class PipelineDAG:
    def __init__(self, name: str = "pipeline"):
        self._name = name
        self._steps: dict[str, PipelineStep] = {}
        self._execution_history: list[PipelineRunResult] = []

    def add_step(self, step: PipelineStep):
        if step.name in self._steps:
            raise ValueError(f"Step '{step.name}' already exists")
        self._steps[step.name] = step

    def add_step_from_func(self, name: str, func: Callable,
                            dependencies: list[str] | None = None,
                            inputs: list[str] | None = None,
                            outputs: list[str] | None = None):
        self.add_step(PipelineStep(
            name=name, func=func,
            dependencies=dependencies or [],
            inputs=inputs or [],
            outputs=outputs or [],
        ))

    def get_execution_order(self) -> list[str]:
        visited: set[str] = set()
        order: list[str] = []

        def _visit(name: str):
            if name in visited:
                return
            visited.add(name)
            step = self._steps.get(name)
            if step:
                for dep in step.dependencies:
                    _visit(dep)
                order.append(name)

        for name in self._steps:
            _visit(name)
        return order

    def validate(self) -> list[str]:
        errors = []
        for name, step in self._steps.items():
            for dep in step.dependencies:
                if dep not in self._steps:
                    errors.append(f"Step '{name}' depends on unknown step '{dep}'")
        execution_order = self.get_execution_order()
        if len(execution_order) != len(self._steps):
            errors.append("Not all steps are reachable (possible cycle)")
        return errors

    async def execute(self, context: dict[str, Any] | None = None,
                       step_filter: list[str] | None = None,
                       cache: dict[str, Any] | None = None) -> list[PipelineRunResult]:
        errors = self.validate()
        if errors:
            raise ValueError(f"Pipeline validation failed: {errors}")

        ctx = dict(context or {})
        execution_order = self.get_execution_order()
        if step_filter:
            execution_order = [s for s in execution_order if s in step_filter]

        results = []
        for step_name in execution_order:
            step = self._steps[step_name]
            cached = (cache or {}).get(step.cache_key) if step.cache_key else None
            if cached is not None:
                result = PipelineRunResult(
                    step_name=step_name, status="cached",
                    start_time=datetime.now(timezone.utc),
                )
                ctx.update({out: cached for out in step.outputs})
                results.append(result)
                continue

            start = datetime.now(timezone.utc)
            try:
                step_inputs = {k: ctx.get(k) for k in step.inputs} if step.inputs else ctx
                output = await step.func(**step_inputs) if step.inputs else await step.func(**ctx)
                end = datetime.now(timezone.utc)
                duration = (end - start).total_seconds() * 1000
                result = PipelineRunResult(
                    step_name=step_name, status="completed",
                    start_time=start, end_time=end,
                    duration_ms=round(duration, 2), output=output,
                )
                if step.outputs:
                    if len(step.outputs) == 1:
                        ctx[step.outputs[0]] = output
                    else:
                        for i, out_name in enumerate(step.outputs):
                            if isinstance(output, (list, tuple)) and i < len(output):
                                ctx[out_name] = output[i]
            except Exception as e:
                end = datetime.now(timezone.utc)
                duration = (end - start).total_seconds() * 1000
                result = PipelineRunResult(
                    step_name=step_name, status="failed",
                    start_time=start, end_time=end,
                    duration_ms=round(duration, 2), error=str(e),
                )
                logger.error("pipeline step %s failed: %s", step_name, e)

            self._execution_history.append(result)
            results.append(result)

            if result.status == "failed":
                break

        return results

    def get_history(self, limit: int = 100) -> list[PipelineRunResult]:
        return self._execution_history[-limit:]

    @property
    def name(self) -> str:
        return self._name

    @property
    def steps(self) -> dict[str, PipelineStep]:
        return dict(self._steps)

    @property
    def step_count(self) -> int:
        return len(self._steps)
