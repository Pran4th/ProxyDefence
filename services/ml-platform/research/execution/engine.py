import asyncio
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.shared.logging_config import get_logger
from research.execution.errors import (
    ConfigurationError,
    ExecutionCancelledError,
    PipelineExecutionError,
    StageExecutionError,
    StageNotFoundError,
)
from research.execution.pipeline import ExecutionPipeline
from research.execution.registry import stage_registry
from research.execution.stage import StageResult, StageStatus

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    execution_id: str
    experiment_name: str
    pipeline_name: str
    status: StageStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    stages: list[StageResult] = field(default_factory=list)
    current_stage: str | None = None
    context_summary: dict = field(default_factory=dict)
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)
    model_uuids: list[str] = field(default_factory=list)


@dataclass
class ExecutionContext:
    experiment_name: str
    config: dict
    dataset: Any = None
    X_train: Any = None
    X_val: Any = None
    X_test: Any = None
    y_train: Any = None
    y_val: Any = None
    y_test: Any = None
    model: Any = None
    predictions: Any = None
    metrics: dict = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class ExecutionEngine:
    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._executions: dict[str, ExecutionResult] = {}
        self._logs: dict[str, list[dict]] = {}

    async def execute_pipeline(
        self,
        pipeline: ExecutionPipeline,
        experiment_name: str,
        context: dict | None = None,
        pool=None,
    ) -> ExecutionResult:
        execution_id = str(uuid4())
        now = datetime.now(timezone.utc)

        result = ExecutionResult(
            execution_id=execution_id,
            experiment_name=experiment_name,
            pipeline_name=pipeline.name,
            status=StageStatus.RUNNING,
            started_at=now,
            current_stage=None,
            context_summary=context or {},
        )
        self._executions[execution_id] = result
        self._logs[execution_id] = []

        self._append_log(execution_id, "PIPELINE", "Pipeline execution started")
        logger.info(
            "pipeline execution started: id=%s experiment=%s stages=%d",
            execution_id, experiment_name, len(pipeline.stages),
        )

        stage_map = {s["stage_type"]: s for s in pipeline.stages}
        all_stage_types = set(s["stage_type"] for s in pipeline.stages)

        validation_errors = pipeline.validate()
        if validation_errors:
            error_msg = f"Pipeline validation failed: {'; '.join(validation_errors)}"
            result.status = StageStatus.FAILED
            result.error = error_msg
            result.completed_at = datetime.now(timezone.utc)
            self._append_log(execution_id, "ERROR", error_msg)
            return result

        exec_context = ExecutionContext(
            experiment_name=experiment_name,
            config=pipeline.config,
        )
        completed: set[str] = set()
        failed: set[str] = set()
        pending: set[str] = set(all_stage_types)
        stage_results: dict[str, StageResult] = {}

        try:
            while pending:
                ready = []
                for stage_type in pending:
                    stage = stage_map[stage_type]
                    deps = stage.get("depends_on", [])
                    if all(d in completed for d in deps):
                        ready.append(stage_type)

                if not ready:
                    remaining_deps = set()
                    for stage_type in pending:
                        stage = stage_map[stage_type]
                        for dep in stage.get("depends_on", []):
                            if dep in failed:
                                remaining_deps.add(dep)
                    if remaining_deps:
                        for stage_type in list(pending):
                            stage = stage_map[stage_type]
                            deps = stage.get("depends_on", [])
                            if any(d in failed for d in deps):
                                skip_result = StageResult(
                                    stage_name=f"{stage_type}_stage",
                                    stage_type=stage_type,
                                    status=StageStatus.SKIPPED,
                                    started_at=datetime.now(timezone.utc),
                                    completed_at=datetime.now(timezone.utc),
                                    duration_ms=0.0,
                                    error=f"Dependency failed: {[d for d in deps if d in failed]}",
                                    output_data={},
                                )
                                stage_results[stage_type] = skip_result
                                result.stages.append(skip_result)
                                self._append_log(execution_id, "SKIP", f"Stage {stage_type} skipped due to failed dependency")
                                pending.discard(stage_type)
                        continue
                    else:
                        error_msg = f"Circular dependency or deadlock in pipeline: pending={pending}"
                        result.status = StageStatus.FAILED
                        result.error = error_msg
                        self._append_log(execution_id, "ERROR", error_msg)
                        break

                async def run_stage(st: str) -> StageResult:
                    stage = stage_map[st]
                    result.current_stage = st
                    self._append_log(execution_id, "STAGE_START", f"Starting stage: {st}")
                    try:
                        sr = await self.execute_stage(st, stage.get("config", {}), exec_context, pool)
                        self._append_log(execution_id, "STAGE_END", f"Stage {st} completed: {sr.status.value}")
                        return sr
                    except Exception as e:
                        self._append_log(execution_id, "STAGE_ERROR", f"Stage {st} failed: {e}")
                        return StageResult(
                            stage_name=f"{st}_stage",
                            stage_type=st,
                            status=StageStatus.FAILED,
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc),
                            duration_ms=0.0,
                            error=str(e),
                            output_data={},
                            metadata={"traceback": traceback.format_exc()},
                        )

                tasks = [run_stage(st) for st in ready]
                raw_results = await asyncio.gather(*tasks, return_exceptions=True)

                for st, sr in zip(ready, raw_results):
                    if isinstance(sr, Exception):
                        sr = StageResult(
                            stage_name=f"{st}_stage",
                            stage_type=st,
                            status=StageStatus.FAILED,
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc),
                            duration_ms=0.0,
                            error=f"Unexpected exception: {sr}",
                        )
                    stage_results[st] = sr
                    result.stages.append(sr)
                    if sr.status == StageStatus.COMPLETED:
                        completed.add(st)
                        exec_context.metrics.update(sr.metrics)
                        exec_context.artifacts.extend(sr.artifacts)
                    elif sr.status == StageStatus.FAILED:
                        failed.add(st)
                        exec_context.errors.append(f"{st}: {sr.error}")
                    pending.discard(st)

            if failed:
                result.status = StageStatus.FAILED
                result.error = f"Pipeline completed with {len(failed)} failed stage(s): {sorted(failed)}"
            else:
                result.status = StageStatus.COMPLETED

        except asyncio.CancelledError:
            result.status = StageStatus.CANCELLED
            result.error = "Pipeline execution cancelled"
            self._append_log(execution_id, "CANCEL", "Pipeline execution cancelled")
        except Exception as e:
            result.status = StageStatus.FAILED
            result.error = f"Pipeline execution failed: {e}"
            self._append_log(execution_id, "ERROR", f"Pipeline execution failed: {e}")
            logger.error("pipeline execution failed: id=%s error=%s", execution_id, e, exc_info=True)

        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        result.current_stage = None
        result.artifacts = list(exec_context.artifacts)
        result.context_summary.update({
            "metric_count": len(exec_context.metrics),
            "artifact_count": len(exec_context.artifacts),
            "feature_count": len(exec_context.feature_names),
            "error_count": len(exec_context.errors),
        })

        self._append_log(execution_id, "PIPELINE", f"Pipeline finished: {result.status.value} ({result.duration_seconds:.2f}s)")
        logger.info(
            "pipeline execution finished: id=%s status=%s duration=%.2fs",
            execution_id, result.status.value, result.duration_seconds,
        )
        return result

    async def execute_stage(
        self,
        stage_type: str,
        stage_config: dict,
        context: ExecutionContext,
        pool=None,
    ) -> StageResult:
        now = datetime.now(timezone.utc)
        try:
            handler = stage_registry.get(stage_type)
            result = handler(stage_config, context)
            return result
        except StageNotFoundError:
            return StageResult(
                stage_name=f"{stage_type}_stage",
                stage_type=stage_type,
                status=StageStatus.FAILED,
                started_at=now,
                completed_at=datetime.now(timezone.utc),
                duration_ms=0.0,
                error=f"No handler registered for stage type: {stage_type}",
                output_data={},
            )
        except ConfigurationError as e:
            return StageResult(
                stage_name=f"{stage_type}_stage",
                stage_type=stage_type,
                status=StageStatus.FAILED,
                started_at=now,
                completed_at=datetime.now(timezone.utc),
                duration_ms=0.0,
                error=f"Configuration error: {e}",
                output_data={},
            )
        except Exception as e:
            logger.error("stage execution failed: type=%s error=%s", stage_type, e, exc_info=True)
            return StageResult(
                stage_name=f"{stage_type}_stage",
                stage_type=stage_type,
                status=StageStatus.FAILED,
                started_at=now,
                completed_at=datetime.now(timezone.utc),
                duration_ms=0.0,
                error=str(e),
                output_data={},
                metadata={"traceback": traceback.format_exc()},
            )

    async def cancel_execution(self, execution_id: str) -> None:
        result = self._executions.get(execution_id)
        if result is None:
            raise StageNotFoundError(f"Execution not found: {execution_id}")
        if result.status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.CANCELLED):
            logger.warning("cannot cancel execution %s in status %s", execution_id, result.status.value)
            return
        result.status = StageStatus.CANCELLED
        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        result.error = "Execution cancelled by user"
        self._append_log(execution_id, "CANCEL", "Execution cancelled by user")
        logger.info("execution cancelled: id=%s", execution_id)

    def get_execution(self, execution_id: str) -> ExecutionResult | None:
        return self._executions.get(execution_id)

    def list_executions(self, status: str | None = None) -> list[ExecutionResult]:
        if status is None:
            return list(self._executions.values())
        return [
            e for e in self._executions.values()
            if e.status.value == status
        ]

    def get_execution_log(self, execution_id: str) -> list[dict]:
        return self._logs.get(execution_id, [])

    def _append_log(self, execution_id: str, level: str, message: str) -> None:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        logs = self._logs.setdefault(execution_id, [])
        logs.append(log_entry)
