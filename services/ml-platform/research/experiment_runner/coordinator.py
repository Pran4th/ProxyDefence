from datetime import datetime, timezone, timedelta
from typing import Any

from backend.shared.logging_config import get_logger
from research.experiment_runner.runner import ExperimentRunner
from research.execution.errors import StageNotFoundError
from research.execution.stage import StageStatus

logger = get_logger(__name__)


class ExecutionCoordinator:
    def __init__(self):
        self._active: dict[str, dict[str, Any]] = {}
        self._completed: dict[str, dict[str, Any]] = {}

    async def submit(self, runner: ExperimentRunner, config: dict) -> str:
        execution_id = await runner.run_experiment(config)
        self._active[execution_id] = {
            "execution_id": execution_id,
            "config": config,
            "submitted_at": datetime.now(timezone.utc),
            "runner": runner,
        }
        logger.info("submitted execution: id=%s", execution_id)
        return execution_id

    async def cancel(self, execution_id: str) -> None:
        entry = self._active.get(execution_id) or self._completed.get(execution_id)
        if entry is None:
            raise StageNotFoundError(f"Execution not found: {execution_id}")
        runner = entry.get("runner")
        if runner:
            await runner.cancel_experiment(execution_id)
        if execution_id in self._active:
            data = self._active.pop(execution_id)
            data["cancelled_at"] = datetime.now(timezone.utc)
            self._completed[execution_id] = data
        logger.info("cancelled execution: id=%s", execution_id)

    async def list_active(self) -> list[dict]:
        results = []
        for eid, entry in list(self._active.items()):
            runner = entry.get("runner")
            status = {StageStatus.RUNNING.value, StageStatus.PENDING.value}
            try:
                if runner:
                    status_info = await runner.get_status(eid)
                    if status_info.get("status") not in ("running", "pending"):
                        self._completed[eid] = self._active.pop(eid)
                        self._completed[eid]["completed_at"] = datetime.now(timezone.utc)
                        continue
                    results.append(status_info)
                else:
                    results.append({"execution_id": eid, "status": "unknown"})
            except Exception:
                results.append({"execution_id": eid, "status": "error"})
        return results

    async def list_completed(self) -> list[dict]:
        results = []
        for eid, entry in list(self._completed.items()):
            runner = entry.get("runner")
            try:
                if runner:
                    status_info = await runner.get_status(eid)
                    results.append(status_info)
                else:
                    results.append({"execution_id": eid, "status": "unknown"})
            except Exception:
                results.append({"execution_id": eid, "status": "error"})
        return results

    def get_status(self, execution_id: str) -> dict:
        entry = self._active.get(execution_id) or self._completed.get(execution_id)
        if entry is None:
            return {"execution_id": execution_id, "status": "not_found"}
        return {
            "execution_id": execution_id,
            "status": "active" if execution_id in self._active else "completed",
            "submitted_at": entry.get("submitted_at").isoformat() if entry.get("submitted_at") else None,
        }

    def cleanup(self, max_age_hours: int = 72) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        expired = [
            eid for eid, entry in list(self._completed.items())
            if entry.get("submitted_at", datetime.now(timezone.utc)) < cutoff
        ]
        for eid in expired:
            del self._completed[eid]
        expired_active = [
            eid for eid, entry in list(self._active.items())
            if entry.get("submitted_at", datetime.now(timezone.utc)) < cutoff
        ]
        for eid in expired_active:
            self._completed[eid] = self._active.pop(eid)
        if expired or expired_active:
            logger.info("cleanup removed %d expired executions", len(expired) + len(expired_active))
