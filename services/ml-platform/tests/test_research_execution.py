from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research.execution.errors import (
    ConfigurationError, DependencyError, ExecutionCancelledError,
    ExecutionError, PipelineExecutionError, StageExecutionError, StageNotFoundError,
)
from research.execution.engine import ExecutionContext, ExecutionEngine, ExecutionResult
from research.execution.pipeline import ExecutionPipeline
from research.execution.registry import DEFAULT_STAGE_ORDER, StageRegistry, stage_registry
from research.execution.stage import ExecutionStage, StageResult, StageStatus


class TestStageStatus:
    def test_enum_values(self):
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.RUNNING.value == "running"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.SKIPPED.value == "skipped"
        assert StageStatus.CANCELLED.value == "cancelled"

    def test_enum_members(self):
        assert len(StageStatus) == 6


class TestExecutionStage:
    def test_default_values(self):
        stage = ExecutionStage(name="test", stage_type="training")
        assert stage.status == StageStatus.PENDING
        assert stage.started_at is None
        assert stage.completed_at is None
        assert stage.duration_ms is None
        assert stage.inputs == []
        assert stage.outputs == []
        assert stage.config == {}
        assert stage.error is None
        assert stage.metadata == {}

    def test_custom_values(self):
        now = datetime.now()
        stage = ExecutionStage(
            name="train", stage_type="training", status=StageStatus.RUNNING,
            started_at=now, completed_at=None, duration_ms=1500.0,
            inputs=["data"], outputs=["model"], config={"lr": 0.01},
            error=None, metadata={"gpu": True},
        )
        assert stage.name == "train"
        assert stage.started_at == now
        assert stage.duration_ms == 1500.0


class TestStageResult:
    def test_default_values(self):
        now = datetime.now()
        result = StageResult(
            stage_name="test", stage_type="training",
            status=StageStatus.COMPLETED,
            started_at=now, completed_at=now, duration_ms=0.0,
        )
        assert result.metrics == {}
        assert result.artifacts == []
        assert result.output_data == {}
        assert result.error is None
        assert result.metadata == {}

    def test_all_fields(self):
        now = datetime.now()
        result = StageResult(
            stage_name="test", stage_type="training",
            status=StageStatus.FAILED,
            started_at=now, completed_at=now, duration_ms=500.0,
            metrics={"acc": 0.9}, artifacts=["model.pkl"],
            output_data={"preds": [1]}, error="fail", metadata={"key": "val"},
        )
        assert result.error == "fail"
        assert result.metrics["acc"] == 0.9


class TestExecutionContext:
    def test_default_values(self):
        ctx = ExecutionContext(experiment_name="exp1", config={})
        assert ctx.experiment_name == "exp1"
        assert ctx.dataset is None
        assert ctx.model is None
        assert ctx.metrics == {}
        assert ctx.artifacts == []
        assert ctx.errors == []

    def test_custom_values(self):
        ctx = ExecutionContext(
            experiment_name="exp1", config={"lr": 0.01}, dataset="data",
            X_train=[1, 2], model="model", metrics={"acc": 0.9},
            artifacts=["a.pkl"], feature_names=["f1", "f2"],
            errors=["err1"], metadata={"key": "val"},
        )
        assert ctx.metrics["acc"] == 0.9
        assert ctx.feature_names == ["f1", "f2"]
        assert ctx.errors == ["err1"]


class TestExceptionClasses:
    def test_execution_error(self):
        assert issubclass(StageExecutionError, ExecutionError)
        assert issubclass(PipelineExecutionError, ExecutionError)
        assert issubclass(ConfigurationError, ExecutionError)
        assert issubclass(ExecutionCancelledError, ExecutionError)
        assert issubclass(StageNotFoundError, ExecutionError)
        assert issubclass(DependencyError, ExecutionError)

    def test_exception_messages(self):
        e1 = StageExecutionError("stage failed")
        assert str(e1) == "stage failed"
        e2 = ConfigurationError("bad config")
        assert str(e2) == "bad config"


class TestStageRegistry:
    def test_register_and_get(self):
        registry = StageRegistry()
        handler = MagicMock(return_value="ok")
        registry.register("test_stage", handler)
        assert registry.get("test_stage") == handler

    def test_get_unknown_raises(self):
        registry = StageRegistry()
        with pytest.raises(StageNotFoundError, match="No handler registered"):
            registry.get("nonexistent")

    def test_list_types(self):
        registry = StageRegistry()
        assert registry.list_types() == []
        registry.register("a", MagicMock())
        registry.register("b", MagicMock())
        assert set(registry.list_types()) == {"a", "b"}

    def test_remove(self):
        registry = StageRegistry()
        registry.register("x", MagicMock())
        registry.remove("x")
        assert "x" not in registry.list_types()
        registry.remove("nonexistent")

    def test_get_default_stages(self):
        registry = StageRegistry()
        stages = registry.get_default_stages()
        assert stages == DEFAULT_STAGE_ORDER
        assert len(stages) == 14

    def test_pre_registered_defaults(self):
        registered = stage_registry.list_types()
        for st in DEFAULT_STAGE_ORDER:
            assert st in registered, f"{st} not pre-registered"

    def test_default_handler_creates_stage_result(self):
        handler = stage_registry.get("dataset")
        result = handler({"name": "test_data"}, None)
        assert isinstance(result, StageResult)
        assert result.status == StageStatus.COMPLETED
        assert result.stage_type == "dataset"
        assert result.output_data["dataset_name"] == "test_data"

    def test_default_handler_config_error(self):
        handler = stage_registry.get("dataset")
        with pytest.raises(ConfigurationError, match="requires 'name'"):
            handler({}, None)

    def test_default_handler_all_types(self):
        for stage_type in DEFAULT_STAGE_ORDER:
            handler = stage_registry.get(stage_type)
            config = {}
            if stage_type == "dataset":
                config = {"name": "test"}
            if stage_type == "validation":
                config = {"name": "test"}
            result = handler(config, None)
            assert isinstance(result, StageResult)
            assert result.stage_type == stage_type
            assert result.status == StageStatus.COMPLETED

    def test_default_handler_validation_stage(self):
        handler = stage_registry.get("validation")
        with pytest.raises(ConfigurationError, match="requires 'name'"):
            handler({}, None)

    def test_default_handler_training_stage(self):
        handler = stage_registry.get("training")
        result = handler({"type": "xgboost", "parameters": {"lr": 0.01}}, None)
        assert result.output_data["model_type"] == "xgboost"
        assert result.output_data["parameters"]["lr"] == 0.01


class TestExecutionPipeline:
    def test_init(self):
        p = ExecutionPipeline({"experiment": {"name": "test"}})
        assert p.name == "test"
        assert p.stages == []

    def test_init_no_config(self):
        p = ExecutionPipeline()
        assert p.name == "default_pipeline"
        assert p.config == {}

    def test_add_stage(self):
        p = ExecutionPipeline()
        p.add_stage("dataset", {"name": "data"})
        assert len(p.stages) == 1
        assert p.stages[0]["stage_type"] == "dataset"

    def test_add_duplicate_stage_raises(self):
        p = ExecutionPipeline()
        p.add_stage("dataset")
        with pytest.raises(ConfigurationError, match="already exists"):
            p.add_stage("dataset")

    def test_add_stage_with_deps(self):
        p = ExecutionPipeline()
        p.add_stage("training", depends_on=["dataset"])
        assert p.stages[0]["depends_on"] == ["dataset"]

    def test_remove_stage(self):
        p = ExecutionPipeline()
        p.add_stage("dataset").add_stage("training")
        p.remove_stage("dataset")
        assert len(p.stages) == 1
        assert p.stages[0]["stage_type"] == "training"

    def test_remove_nonexistent(self):
        p = ExecutionPipeline()
        p.add_stage("dataset")
        p.remove_stage("nonexistent")
        assert len(p.stages) == 1

    def test_get_execution_order_no_deps(self):
        p = ExecutionPipeline()
        p.add_stage("a").add_stage("b").add_stage("c")
        order = p.get_execution_order()
        assert len(order) == 3

    def test_get_execution_order_with_deps(self):
        p = ExecutionPipeline()
        p.add_stage("a").add_stage("b", depends_on=["a"]).add_stage("c", depends_on=["b"])
        order = p.get_execution_order()
        assert order == ["a", "b", "c"]

    def test_validate_no_errors(self):
        p = ExecutionPipeline()
        p.add_stage("a").add_stage("b", depends_on=["a"])
        assert p.validate() == []

    def test_validate_missing_dep(self):
        p = ExecutionPipeline()
        p.add_stage("b", depends_on=["a"])
        errors = p.validate()
        assert any("depends on unknown" in e for e in errors)

    def test_validate_cycle(self):
        p = ExecutionPipeline()
        p.add_stage("a", depends_on=["b"])
        p.add_stage("b", depends_on=["a"])
        errors = p.validate()
        assert any("Circular dependency" in e for e in errors)

    def test_build_default_pipeline(self):
        p = ExecutionPipeline()
        p.build_default_pipeline()
        assert len(p.stages) == 14
        types = [s["stage_type"] for s in p.stages]
        assert types == DEFAULT_STAGE_ORDER

    def test_build_default_pipeline_with_config(self):
        config = {
            "experiment": {"name": "test"},
            "dataset": {"name": "energy_data"},
            "model": {"type": "xgboost", "evaluation": {"metrics": ["f1"]}},
        }
        p = ExecutionPipeline(config=config)
        p.build_default_pipeline()
        dataset_stage = p.stages[0]
        assert dataset_stage["stage_type"] == "dataset"
        assert dataset_stage["config"]["name"] == "energy_data"

    def test_build_from_config(self):
        config = {"experiment": {"name": "test"}}
        p = ExecutionPipeline()
        p.build_from_config(config)
        assert p.name == "test"
        assert len(p.stages) == 14

    def test_to_dict(self):
        p = ExecutionPipeline({"experiment": {"name": "test"}})
        p.add_stage("dataset")
        d = p.to_dict()
        assert d["name"] == "test"
        assert len(d["stages"]) == 1

    def test_from_dict(self):
        data = {
            "name": "test",
            "config": {"experiment": {"name": "test"}},
            "stages": [{"stage_type": "dataset", "config": {}, "depends_on": []}],
        }
        p = ExecutionPipeline.from_dict(data)
        assert p.name == "test"
        assert len(p.stages) == 1
        assert p.stages[0]["stage_type"] == "dataset"

    def test_from_dict_with_deps(self):
        data = {
            "config": {},
            "stages": [
                {"stage_type": "a", "config": {}, "depends_on": []},
                {"stage_type": "b", "config": {}, "depends_on": ["a"]},
            ],
        }
        p = ExecutionPipeline.from_dict(data)
        assert p.stages[1]["depends_on"] == ["a"]


class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_execute_stage_with_handler(self):
        engine = ExecutionEngine()
        context = ExecutionContext(experiment_name="test", config={})
        result = await engine.execute_stage("dataset", {"name": "data"}, context)
        assert result.status == StageStatus.COMPLETED
        assert result.stage_type == "dataset"

    @pytest.mark.asyncio
    async def test_execute_stage_not_found(self):
        engine = ExecutionEngine()
        context = ExecutionContext(experiment_name="test", config={})
        result = await engine.execute_stage("nonexistent", {}, context)
        assert result.status == StageStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_pipeline_basic_flow(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("dataset", {"name": "data"})
        result = await engine.execute_pipeline(pipeline, "test_exp")
        assert isinstance(result, ExecutionResult)
        assert result.status == StageStatus.COMPLETED
        assert result.experiment_name == "test_exp"
        assert len(result.stages) == 1

    @pytest.mark.asyncio
    async def test_execute_pipeline_validation_failure(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("b", depends_on=["a"])
        result = await engine.execute_pipeline(pipeline, "test")
        assert result.status == StageStatus.FAILED
        assert "validation failed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_cancel_execution(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("dataset", {"name": "data"})
        result = await engine.execute_pipeline(pipeline, "test")
        await engine.cancel_execution(result.execution_id)
        cancelled = engine.get_execution(result.execution_id)
        assert cancelled is not None

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        engine = ExecutionEngine()
        with pytest.raises(StageNotFoundError):
            await engine.cancel_execution("nonexistent")

    @pytest.mark.asyncio
    async def test_cancel_completed_does_nothing(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("dataset", {"name": "data"})
        result = await engine.execute_pipeline(pipeline, "test")
        await engine.cancel_execution(result.execution_id)
        assert result.status == StageStatus.COMPLETED

    def test_get_execution_nonexistent(self):
        engine = ExecutionEngine()
        assert engine.get_execution("bad") is None

    @pytest.mark.asyncio
    async def test_list_executions(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("dataset", {"name": "data"})
        await engine.execute_pipeline(pipeline, "exp1")
        assert len(engine.list_executions()) == 1

    def test_list_executions_empty(self):
        engine = ExecutionEngine()
        assert engine.list_executions() == []

    def test_list_executions_by_status(self):
        engine = ExecutionEngine()
        assert engine.list_executions("running") == []

    @pytest.mark.asyncio
    async def test_get_execution_log(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("dataset", {"name": "data"})
        result = await engine.execute_pipeline(pipeline, "test")
        logs = engine.get_execution_log(result.execution_id)
        assert len(logs) > 0
        assert any("Pipeline execution started" in l["message"] for l in logs)

    def test_get_execution_log_nonexistent(self):
        engine = ExecutionEngine()
        assert engine.get_execution_log("bad") == []

    @pytest.mark.asyncio
    async def test_execution_result_fields(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("dataset", {"name": "data"})
        result = await engine.execute_pipeline(pipeline, "exp1", context={"key": "val"})
        assert result.execution_id is not None
        assert result.pipeline_name == "default_pipeline"
        assert result.context_summary.get("key") == "val"
        assert result.duration_seconds is not None
        assert result.completed_at is not None
        assert result.artifacts == []

    @pytest.mark.asyncio
    async def test_execution_error_handled(self):
        engine = ExecutionEngine()
        pipeline = ExecutionPipeline()
        pipeline.add_stage("dataset")  # missing name, will fail
        result = await engine.execute_pipeline(pipeline, "test")
        assert result.status == StageStatus.FAILED


class TestExecutionResult:
    def test_default_values(self):
        now = datetime.now()
        er = ExecutionResult(
            execution_id="id1", experiment_name="exp",
            pipeline_name="pipe", status=StageStatus.RUNNING,
            started_at=now,
        )
        assert er.completed_at is None
        assert er.stages == []
        assert er.current_stage is None
        assert er.error is None
        assert er.artifacts == []
        assert er.model_uuids == []

    def test_full_values(self):
        now = datetime.now()
        er = ExecutionResult(
            execution_id="id1", experiment_name="exp",
            pipeline_name="pipe", status=StageStatus.COMPLETED,
            started_at=now, completed_at=now, duration_seconds=10.5,
            stages=[], current_stage=None, context_summary={"k": "v"},
            error=None, artifacts=["a.pkl"], model_uuids=["uuid1"],
        )
        assert er.duration_seconds == 10.5
        assert er.artifacts == ["a.pkl"]
