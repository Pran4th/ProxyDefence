from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research.experiment_runner.coordinator import ExecutionCoordinator
from research.experiment_runner.runner import ExperimentRunner
from research.execution.errors import StageNotFoundError


class TestExperimentRunner:
    def test_default_construction(self):
        runner = ExperimentRunner()
        assert runner._engine is not None
        assert runner._manager is not None
        assert runner._config_loader is not None

    def test_construction_with_mocks(self):
        engine = MagicMock()
        manager = MagicMock()
        runner = ExperimentRunner(engine=engine, experiment_manager=manager)
        assert runner._engine is engine
        assert runner._manager is manager

    @pytest.mark.asyncio
    async def test_run_experiment_with_config_dict(self):
        config = {
            "experiment": {"name": "test_exp", "type": "classification"},
            "dataset": {"name": "data"},
            "model": {"type": "xgboost"},
        }
        runner = ExperimentRunner()
        runner._manager.create_experiment = AsyncMock(return_value={"uuid": "exp_uuid"})
        runner._manager.start_run = AsyncMock(return_value={"uuid": "run_uuid"})
        runner._manager.finish_run = AsyncMock(return_value={})
        execution_id = await runner.run_experiment(config)
        assert execution_id is not None
        assert isinstance(execution_id, str)

    @pytest.mark.asyncio
    async def test_run_experiment_with_string_path(self):
        runner = ExperimentRunner()
        runner._config_loader.load = MagicMock(return_value={
            "experiment": {"name": "test", "type": "classification"},
        })
        runner._manager.create_experiment = AsyncMock(return_value={"uuid": "eu1"})
        runner._manager.start_run = AsyncMock(return_value={"uuid": "ru1"})
        runner._manager.finish_run = AsyncMock(return_value={})
        eid = await runner.run_experiment("some/path.yaml")
        assert eid is not None

    @pytest.mark.asyncio
    async def test_cancel_experiment(self):
        runner = ExperimentRunner()
        runner._engine.cancel_execution = AsyncMock()
        await runner.cancel_experiment("some_id")
        runner._engine.cancel_execution.assert_called_once_with("some_id")

    @pytest.mark.asyncio
    async def test_get_status_not_found(self):
        runner = ExperimentRunner()
        status = await runner.get_status("bad_id")
        assert status["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_status_found(self):
        runner = ExperimentRunner()
        mock_execution = MagicMock()
        mock_execution.execution_id = "e1"
        mock_execution.experiment_name = "exp"
        mock_execution.pipeline_name = "pipe"
        mock_execution.status = MagicMock()
        mock_execution.status.value = "completed"
        mock_execution.started_at = MagicMock()
        mock_execution.started_at.isoformat = MagicMock(return_value="now")
        mock_execution.completed_at = MagicMock()
        mock_execution.completed_at.isoformat = MagicMock(return_value="now")
        mock_execution.duration_seconds = 10.0
        mock_execution.current_stage = None
        mock_execution.error = None
        mock_execution.stages = []
        mock_execution.artifacts = []
        mock_execution.model_uuids = []
        runner._engine.get_execution = MagicMock(return_value=mock_execution)
        status = await runner.get_status("e1")
        assert status["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_execution_logs(self):
        runner = ExperimentRunner()
        runner._engine.get_execution_log = MagicMock(return_value=[{"msg": "test"}])
        logs = await runner.get_execution_logs("e1")
        assert logs == [{"msg": "test"}]

    @pytest.mark.asyncio
    async def test_get_execution_logs_empty(self):
        runner = ExperimentRunner()
        runner._engine.get_execution_log = MagicMock(return_value=[])
        logs = await runner.get_execution_logs("e1")
        assert logs == []

    @pytest.mark.asyncio
    async def test_compare_experiments(self):
        runner = ExperimentRunner()
        runner._engine.get_execution = MagicMock(return_value=MagicMock(
            status=MagicMock(value="completed"), duration_seconds=5.0,
            stages=[MagicMock(stage_name="s1", stage_type="t1", status=MagicMock(value="ok"))],
            error=None,
        ))
        result = await runner.compare_experiments(["e1", "e2"])
        assert result["execution_count"] == 2
        assert "e1" in result["executions"]

    @pytest.mark.asyncio
    async def test_resume_experiment_not_found(self):
        runner = ExperimentRunner()
        with pytest.raises(ValueError, match="not found"):
            await runner.resume_experiment("bad_id")

    @pytest.mark.asyncio
    async def test_get_execution_history(self):
        runner = ExperimentRunner()
        runner._manager.list_experiments = AsyncMock(return_value=([], 0))
        history = await runner.get_execution_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_run_experiment_cancelled_status(self):
        config = {"experiment": {"name": "test", "type": "classification"}}
        runner = ExperimentRunner()
        runner._manager.create_experiment = AsyncMock(return_value={"uuid": "eu1"})
        runner._manager.start_run = AsyncMock(return_value={"uuid": "ru1"})
        runner._manager.finish_run = AsyncMock(return_value={})
        runner._engine.execute_pipeline = AsyncMock(return_value=MagicMock(
            execution_id="e1", status=MagicMock(value="cancelled"),
            context_summary={}, error="cancelled",
            artifacts=[], model_uuids=[],
        ))
        eid = await runner.run_experiment(config)
        assert eid == "e1"


class TestExecutionCoordinator:
    def test_init(self):
        coord = ExecutionCoordinator()
        assert coord._active == {}
        assert coord._completed == {}

    @pytest.mark.asyncio
    async def test_submit(self):
        coord = ExecutionCoordinator()
        runner = MagicMock()
        runner.run_experiment = AsyncMock(return_value="exec_1")
        eid = await coord.submit(runner, {"key": "val"})
        assert eid == "exec_1"
        assert "exec_1" in coord._active

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        coord = ExecutionCoordinator()
        with pytest.raises(StageNotFoundError):
            await coord.cancel("bad_id")

    @pytest.mark.asyncio
    async def test_cancel_active(self):
        coord = ExecutionCoordinator()
        runner = MagicMock()
        runner.run_experiment = AsyncMock(return_value="e1")
        runner.cancel_experiment = AsyncMock()
        await coord.submit(runner, {})
        await coord.cancel("e1")
        assert "e1" not in coord._active
        assert "e1" in coord._completed

    def test_get_status_not_found(self):
        coord = ExecutionCoordinator()
        status = coord.get_status("bad")
        assert status["status"] == "not_found"

    def test_get_status_active(self):
        coord = ExecutionCoordinator()
        coord._active["e1"] = {
            "execution_id": "e1", "config": {},
            "submitted_at": MagicMock(isoformat=MagicMock(return_value="now")),
        }
        status = coord.get_status("e1")
        assert status["status"] == "active"

    def test_get_status_completed(self):
        coord = ExecutionCoordinator()
        coord._completed["e1"] = {
            "execution_id": "e1", "config": {},
            "submitted_at": MagicMock(isoformat=MagicMock(return_value="now")),
        }
        status = coord.get_status("e1")
        assert status["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_active(self):
        coord = ExecutionCoordinator()
        runner = MagicMock()
        runner.run_experiment = AsyncMock(return_value="e1")
        runner.get_status = AsyncMock(return_value={"status": "running"})
        await coord.submit(runner, {})
        active = await coord.list_active()
        assert len(active) >= 1

    @pytest.mark.asyncio
    async def test_list_completed_empty(self):
        coord = ExecutionCoordinator()
        completed = await coord.list_completed()
        assert completed == []

    def test_cleanup_removes_old(self):
        coord = ExecutionCoordinator()
        from datetime import datetime, timezone, timedelta
        old_time = datetime.now(timezone.utc) - timedelta(hours=100)
        coord._completed["old"] = {
            "execution_id": "old", "config": {}, "submitted_at": old_time,
        }
        coord.cleanup(max_age_hours=72)
        assert "old" not in coord._completed

    def test_cleanup_keeps_recent(self):
        coord = ExecutionCoordinator()
        from datetime import datetime, timezone
        recent_time = datetime.now(timezone.utc)
        coord._completed["new"] = {
            "execution_id": "new", "config": {}, "submitted_at": recent_time,
        }
        coord.cleanup(max_age_hours=72)
        assert "new" in coord._completed
