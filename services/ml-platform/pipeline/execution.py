import json
from datetime import datetime, timezone
from typing import Any

from backend.shared.logging_config import get_logger
from pipeline.dag import PipelineDAG, PipelineRunResult

logger = get_logger(__name__)


class PipelineExecution:
    def __init__(self):
        self._pipelines: dict[str, PipelineDAG] = {}
        self._history: list[dict[str, Any]] = []

    def register(self, pipeline: PipelineDAG):
        self._pipelines[pipeline.name] = pipeline

    def get(self, name: str) -> PipelineDAG | None:
        return self._pipelines.get(name)

    def list_pipelines(self) -> list[dict[str, Any]]:
        return [
            {"name": p.name, "steps": p.step_count, "step_names": list(p.steps.keys())}
            for p in self._pipelines.values()
        ]

    async def run(self, name: str, context: dict | None = None,
                   step_filter: list[str] | None = None) -> dict[str, Any]:
        pipeline = self._pipelines.get(name)
        if not pipeline:
            raise ValueError(f"Pipeline '{name}' not found. Registered: {list(self._pipelines.keys())}")

        logger.info("running pipeline: %s", name)
        start = datetime.now(timezone.utc)
        results = await pipeline.execute(context=context, step_filter=step_filter)
        end = datetime.now(timezone.utc)

        record = {
            "pipeline_name": name,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration_ms": round((end - start).total_seconds() * 1000, 2),
            "total_steps": len(results),
            "completed": sum(1 for r in results if r.status == "completed"),
            "cached": sum(1 for r in results if r.status == "cached"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "steps": [
                {
                    "step": r.step_name,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in results
            ],
        }
        self._history.append(record)
        logger.info("pipeline %s completed: %d/%d steps",
                     name, record["completed"], record["total_steps"])
        return record

    def get_history(self, pipeline_name: str | None = None,
                     limit: int = 50) -> list[dict[str, Any]]:
        if pipeline_name:
            return [h for h in self._history[-limit:] if h["pipeline_name"] == pipeline_name]
        return self._history[-limit:]


_pipeline_execution: PipelineExecution | None = None


def get_pipeline_execution() -> PipelineExecution:
    global _pipeline_execution
    if _pipeline_execution is None:
        _pipeline_execution = PipelineExecution()
    return _pipeline_execution
