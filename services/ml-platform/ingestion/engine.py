import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.shared.logging_config import get_logger

from ingestion.errors import (
    IngestionCancelledError,
    IngestionStepError,
    IngestionTimeoutError,
)
from ingestion.pipeline import IngestionPipeline, PipelineStep, PipelineStepResult

logger = get_logger(__name__)


class IngestionContext:
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._stats = {
            "records_processed": 0,
            "errors_count": 0,
            "started_at": None,
            "completed_at": None,
            "step_timings": [],
        }

    def set(self, key: str, value: Any):
        self._data[key] = value

    def get(self, key: str, default=None) -> Any:
        return self._data.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def stats(self) -> dict:
        return dict(self._stats)


@dataclass
class IngestionResult:
    pipeline_name: str
    status: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float = 0.0
    step_results: list[PipelineStepResult] = field(default_factory=list)
    records_downloaded: int = 0
    records_inserted: int = 0
    records_failed: int = 0
    errors: list[dict] = field(default_factory=list)
    context_summary: dict = field(default_factory=dict)
    error: str | None = None


class IngestionEngine:
    def __init__(self, pipeline: IngestionPipeline):
        self._pipeline = pipeline
        self._cancelled = asyncio.Event()
        self._progress: dict = {
            "total_steps": 0,
            "completed_steps": 0,
            "current_step": None,
            "status": "idle",
            "percent": 0.0,
        }

    async def execute(
        self,
        initial_context: IngestionContext | None = None,
        pool=None,
        dry_run: bool = False,
    ) -> IngestionResult:
        context = initial_context or IngestionContext()

        if self._cancelled.is_set():
            completed_at = datetime.now(timezone.utc)
            self._progress["status"] = "cancelled"
            return IngestionResult(
                pipeline_name=self._pipeline.name,
                status="cancelled",
                started_at=completed_at,
                completed_at=completed_at,
                context_summary={"keys": context.keys(), **context.stats()},
            )

        self._cancelled.clear()
        self._progress["status"] = "running"
        self._progress["total_steps"] = len(self._pipeline.get_steps())
        started_at = datetime.now(timezone.utc)
        step_results: list[PipelineStepResult] = []
        errors: list[dict] = []
        records_downloaded = 0
        records_inserted = 0
        records_failed = 0

        validation_errors = await self.validate_pipeline()
        if validation_errors:
            completed_at = datetime.now(timezone.utc)
            self._progress["status"] = "failed"
            return IngestionResult(
                pipeline_name=self._pipeline.name,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
                errors=[{"type": "validation", "message": e} for e in validation_errors],
                error="; ".join(validation_errors),
            )

        execution_order = self._pipeline.get_execution_order()

        for step_idx, step in enumerate(execution_order):
            if self._cancelled.is_set():
                completed_at = datetime.now(timezone.utc)
                step_results.append(
                    PipelineStepResult(
                        step_name=step.name,
                        step_type=step.step_type,
                        status="skipped",
                        started_at=completed_at,
                        completed_at=completed_at,
                    )
                )
                self._progress["status"] = "cancelled"
                return IngestionResult(
                    pipeline_name=self._pipeline.name,
                    status="cancelled",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=(completed_at - started_at).total_seconds(),
                    step_results=step_results,
                    records_downloaded=records_downloaded,
                    records_inserted=records_inserted,
                    records_failed=records_failed,
                    errors=errors,
                    context_summary={"keys": context.keys(), **context.stats()},
                )

            self._progress["current_step"] = step.name
            self._progress["percent"] = round(
                (step_idx / len(execution_order)) * 100, 1
            )

            step_result = await self.execute_step(step, context, pool=pool, dry_run=dry_run)
            step_results.append(step_result)

            if step_result.status == "completed":
                records_downloaded += step_result.records_processed
                records_inserted += step_result.records_processed
                self._progress["completed_steps"] += 1
            elif step_result.status == "failed":
                records_failed += step_result.records_processed
                errors.append({
                    "step": step.name,
                    "step_type": step.step_type,
                    "message": step_result.error,
                    "duration_ms": step_result.duration_ms,
                })

        overall_status = self._determine_overall_status(step_results)
        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()
        self._progress["status"] = overall_status

        return IngestionResult(
            pipeline_name=self._pipeline.name,
            status=overall_status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=round(duration, 3),
            step_results=step_results,
            records_downloaded=records_downloaded,
            records_inserted=records_inserted,
            records_failed=records_failed,
            errors=errors,
            context_summary={"keys": context.keys(), **context.stats()},
        )

    async def execute_step(
        self,
        step: PipelineStep,
        context: IngestionContext,
        pool=None,
        dry_run: bool = False,
    ) -> PipelineStepResult:
        started_at = datetime.now(timezone.utc)

        if dry_run:
            return PipelineStepResult(
                step_name=step.name,
                step_type=step.step_type,
                status="skipped",
                started_at=started_at,
                completed_at=started_at,
                duration_ms=0.0,
                metadata={"dry_run": True},
            )

        max_retries = step.retry_config.get("max_retries", 3)
        backoff = step.retry_config.get("backoff", 1.0)
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            if self._cancelled.is_set():
                raise IngestionCancelledError("Execution cancelled")

            try:
                if attempt > 0:
                    wait = backoff * (2 ** (attempt - 1))
                    logger.info(
                        "retrying step '%s' (attempt %d/%d) after %.1fs",
                        step.name, attempt, max_retries, wait,
                    )
                    await asyncio.sleep(wait)

                output = await asyncio.wait_for(
                    step.handler(context, pool),
                    timeout=step.timeout_seconds,
                )

                completed_at = datetime.now(timezone.utc)
                duration_ms = (completed_at - started_at).total_seconds() * 1000

                output_keys = list(step.outputs)
                if step.outputs and output is not None:
                    if len(step.outputs) == 1:
                        context.set(step.outputs[0], output)
                    elif isinstance(output, dict):
                        for out_name in step.outputs:
                            if out_name in output:
                                context.set(out_name, output[out_name])
                    elif isinstance(output, (list, tuple)):
                        for i, out_name in enumerate(step.outputs):
                            if i < len(output):
                                context.set(out_name, output[i])

                records_processed = 0
                if output is not None:
                    if hasattr(output, "__len__"):
                        try:
                            records_processed = len(output)
                        except (TypeError, ValueError):
                            records_processed = 1
                    else:
                        records_processed = 1

                return PipelineStepResult(
                    step_name=step.name,
                    step_type=step.step_type,
                    status="completed",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=round(duration_ms, 2),
                    records_processed=records_processed,
                    output_keys=output_keys,
                    metadata={"attempt": attempt},
                )

            except asyncio.TimeoutError:
                last_error = IngestionTimeoutError(
                    f"Step '{step.name}' timed out after {step.timeout_seconds}s"
                )
                logger.warning(
                    "step '%s' timed out (attempt %d/%d)",
                    step.name, attempt, max_retries,
                )
            except IngestionCancelledError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "step '%s' failed (attempt %d/%d): %s",
                    step.name, attempt, max_retries, e,
                )

        completed_at = datetime.now(timezone.utc)
        duration_ms = (completed_at - started_at).total_seconds() * 1000
        return PipelineStepResult(
            step_name=step.name,
            step_type=step.step_type,
            status="failed",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
            error=str(last_error) if last_error else "Unknown error",
            metadata={"attempt": max_retries, "exhausted": True},
        )

    async def validate_pipeline(self) -> list[str]:
        return self._pipeline.validate()

    def get_progress(self) -> dict:
        return dict(self._progress)

    async def cancel(self):
        self._cancelled.set()
        self._progress["status"] = "cancelling"

    def _determine_overall_status(
        self, step_results: list[PipelineStepResult]
    ) -> str:
        if not step_results:
            return "failed"
        all_success = all(r.status in ("completed", "skipped") for r in step_results)
        any_failed = any(r.status == "failed" for r in step_results)
        if all_success and not any_failed:
            return "completed"
        if any_failed and any(r.status == "completed" for r in step_results):
            return "partial"
        if any_failed:
            return "failed"
        return "completed"
