from copy import deepcopy
from typing import Any

from backend.shared.logging_config import get_logger
from research.execution.errors import ConfigurationError, DependencyError
from research.execution.registry import DEFAULT_STAGE_ORDER

logger = get_logger(__name__)


class ExecutionPipeline:
    def __init__(self, config: dict | None = None):
        self._config: dict = config or {}
        self._stages: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._config.get("experiment", {}).get("name", "default_pipeline")

    @property
    def config(self) -> dict:
        return self._config

    @property
    def stages(self) -> list[dict[str, Any]]:
        return list(self._stages)

    def add_stage(
        self,
        stage_type: str,
        stage_config: dict | None = None,
        depends_on: list[str] | None = None,
    ) -> "ExecutionPipeline":
        for s in self._stages:
            if s["stage_type"] == stage_type:
                raise ConfigurationError(f"Stage already exists in pipeline: {stage_type}")
        self._stages.append({
            "stage_type": stage_type,
            "config": stage_config or {},
            "depends_on": depends_on or [],
        })
        logger.debug("added stage %s to pipeline %s", stage_type, self.name)
        return self

    def remove_stage(self, stage_type: str) -> "ExecutionPipeline":
        for i, s in enumerate(self._stages):
            if s["stage_type"] == stage_type:
                self._stages.pop(i)
                logger.debug("removed stage %s from pipeline %s", stage_type, self.name)
                break
        return self

    def get_execution_order(self) -> list[str]:
        stage_map = {s["stage_type"]: s for s in self._stages}
        in_degree: dict[str, int] = {s["stage_type"]: 0 for s in self._stages}
        adj: dict[str, list[str]] = {s["stage_type"]: [] for s in self._stages}

        for s in self._stages:
            for dep in s.get("depends_on", []):
                if dep in stage_map:
                    adj[dep].append(s["stage_type"])
                    in_degree[s["stage_type"]] = in_degree.get(s["stage_type"], 0) + 1

        queue = [t for t, d in in_degree.items() if d == 0]
        order: list[str] = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        return order

    def validate(self) -> list[str]:
        errors: list[str] = []
        seen: set[str] = set()
        for s in self._stages:
            st = s["stage_type"]
            if st in seen:
                errors.append(f"Duplicate stage type: {st}")
            seen.add(st)
            for dep in s.get("depends_on", []):
                if dep not in seen:
                    errors.append(f"Stage '{st}' depends on unknown stage '{dep}'")
        order = self.get_execution_order()
        if len(order) < len(self._stages):
            missing = set(s["stage_type"] for s in self._stages) - set(order)
            if missing:
                errors.append(f"Circular dependency detected for stages: {sorted(missing)}")
        return errors

    def build_default_pipeline(self) -> "ExecutionPipeline":
        self._stages = []
        for stage_type in DEFAULT_STAGE_ORDER:
            stage_config = {}
            if stage_type == "dataset" and "dataset" in self._config:
                stage_config = deepcopy(self._config["dataset"])
            elif stage_type == "export" and "export" in self._config:
                stage_config = deepcopy(self._config["export"])
            elif stage_type in ("cross_validation", "hyperparameter_search", "evaluation"):
                model_config = self._config.get("model", {})
                eval_config = model_config.get("evaluation", {})
                if stage_type == "cross_validation":
                    stage_config = deepcopy(eval_config.get("cross_validation", {}))
                elif stage_type == "hyperparameter_search":
                    stage_config = deepcopy(eval_config.get("hyperparameter_search", {}))
                elif stage_type == "evaluation":
                    stage_config = {"metrics": eval_config.get("metrics", ["accuracy", "f1"])}
            elif stage_type == "training" and "model" in self._config:
                stage_config = deepcopy(self._config["model"])
            self._stages.append({
                "stage_type": stage_type,
                "config": stage_config,
                "depends_on": [],
            })
        logger.info("built default pipeline with %d stages for %s", len(self._stages), self.name)
        return self

    def build_from_config(self, config: dict) -> "ExecutionPipeline":
        self._config = config
        return self.build_default_pipeline()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "config": self._config,
            "stages": deepcopy(self._stages),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionPipeline":
        pipeline = cls(config=data.get("config", {}))
        for stage in data.get("stages", []):
            pipeline.add_stage(
                stage["stage_type"],
                stage.get("config"),
                stage.get("depends_on"),
            )
        return pipeline
