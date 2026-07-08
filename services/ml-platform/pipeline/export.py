import json
import yaml
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from pipeline.dag import PipelineDAG, PipelineStep

logger = get_logger(__name__)


class PipelineExporter:
    @staticmethod
    def to_dict(pipeline: PipelineDAG) -> dict[str, Any]:
        return {
            "name": pipeline.name,
            "steps": [
                {
                    "name": s.name,
                    "inputs": s.inputs,
                    "outputs": s.outputs,
                    "dependencies": s.dependencies,
                    "cache_key": s.cache_key,
                    "params": s.params,
                }
                for s in pipeline.steps.values()
            ],
            "execution_order": pipeline.get_execution_order(),
        }

    @staticmethod
    def from_dict(data: dict, func_registry: dict[str, Any]) -> PipelineDAG:
        pipeline = PipelineDAG(name=data.get("name", "imported"))
        func_reg = func_registry or {}
        for step_data in data.get("steps", []):
            func = func_reg.get(step_data["name"])
            if func is None:
                func = func_reg.get("_default", lambda **x: x)
            pipeline.add_step(PipelineStep(
                name=step_data["name"],
                func=func,
                inputs=step_data.get("inputs", []),
                outputs=step_data.get("outputs", []),
                dependencies=step_data.get("dependencies", []),
                cache_key=step_data.get("cache_key"),
                params=step_data.get("params", {}),
            ))
        return pipeline

    @staticmethod
    def export_yaml(pipeline: PipelineDAG, path: str):
        data = PipelineExporter.to_dict(pipeline)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        logger.info("pipeline exported to %s", path)

    @staticmethod
    def export_json(pipeline: PipelineDAG, path: str):
        data = PipelineExporter.to_dict(pipeline)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("pipeline exported to %s", path)

    @staticmethod
    def replay(pipeline: PipelineDAG, results: list[dict],
               context: dict | None = None) -> dict[str, Any]:
        ctx = dict(context or {})
        replay_log = []
        for step_result in results:
            step_name = step_result.get("step")
            if step_name in pipeline.steps:
                step = pipeline.steps[step_name]
                ctx.update(step_result.get("outputs", {}))
                replay_log.append({
                    "step": step_name,
                    "status": "replayed",
                    "cached_outputs": list(step.outputs),
                })
        return {"pipeline": pipeline.name, "steps": replay_log, "context_keys": list(ctx.keys())}
