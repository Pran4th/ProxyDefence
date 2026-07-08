import yaml

import pytest

from ingestion.errors import (
    IngestionError,
    IngestionStepError,
    IngestionPipelineError,
    IngestionTimeoutError,
    IngestionConfigError,
    IngestionScheduleError,
    IngestionCancelledError,
)
from ingestion.pipeline import PipelineStep, PipelineStepResult, IngestionPipeline
from ingestion.engine import IngestionContext, IngestionResult
from ingestion.scheduler import ScheduleDefinition, IngestionScheduler


def _dummy_handler(ctx, pool):
    return None


class TestPipelineStep:
    def test_minimal_step(self):
        step = PipelineStep(name="fetch", step_type="source", handler=_dummy_handler)
        assert step.name == "fetch"
        assert step.step_type == "source"
        assert step.inputs == []
        assert step.outputs == []
        assert step.config == {}
        assert step.retry_config == {"max_retries": 3, "backoff": 1.0}
        assert step.timeout_seconds == 300

    def test_full_step(self):
        step = PipelineStep(
            name="transform", step_type="process", handler=_dummy_handler,
            inputs=["raw"], outputs=["clean"], config={"mode": "strict"},
            retry_config={"max_retries": 5, "backoff": 2.0}, timeout_seconds=600,
        )
        assert step.inputs == ["raw"]
        assert step.outputs == ["clean"]
        assert step.config["mode"] == "strict"


class TestPipelineStepResult:
    def test_defaults(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        r = PipelineStepResult(
            step_name="s1", step_type="src", status="completed",
            started_at=now, completed_at=now,
        )
        assert r.duration_ms == 0.0
        assert r.records_processed == 0
        assert r.error is None

    def test_with_error(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        r = PipelineStepResult(
            step_name="s1", step_type="src", status="failed",
            started_at=now, completed_at=now, error="OOM",
        )
        assert r.error == "OOM"
        assert r.status == "failed"


class TestIngestionPipeline:
    def test_add_step_and_get_steps(self):
        pipe = IngestionPipeline(name="test")
        step = PipelineStep(name="s1", step_type="src", handler=_dummy_handler)
        pipe.add_step(step)
        steps = pipe.get_steps()
        assert len(steps) == 1
        assert steps[0].name == "s1"

    def test_duplicate_name_raises(self):
        pipe = IngestionPipeline(name="test")
        step = PipelineStep(name="s1", step_type="src", handler=_dummy_handler)
        pipe.add_step(step)
        with pytest.raises(IngestionConfigError, match="already exists"):
            pipe.add_step(step)

    def test_to_dict_roundtrip(self):
        pipe = IngestionPipeline(name="testpipe", description="desc")
        s1 = PipelineStep(
            name="s1", step_type="src", handler=_dummy_handler,
            outputs=["raw_data"],
        )
        s2 = PipelineStep(
            name="s2", step_type="proc", handler=_dummy_handler,
            inputs=["raw_data"], outputs=["clean_data"],
        )
        pipe.add_step(s1)
        pipe.add_step(s2)
        d = pipe.to_dict()
        assert d["name"] == "testpipe"
        assert len(d["steps"]) == 2

        pipe2 = IngestionPipeline.from_dict(d)
        assert pipe2.name == "testpipe"
        assert len(pipe2.get_steps()) == 2
        assert pipe2.get_steps()[1].inputs == ["raw_data"]

    def test_to_yaml_roundtrip(self):
        pipe = IngestionPipeline(name="ypipe")
        s1 = PipelineStep(name="load", step_type="loader", handler=_dummy_handler, outputs=["data"])
        pipe.add_step(s1)
        y = pipe.to_yaml()
        assert "ypipe" in y
        assert "load" in y

        pipe2 = IngestionPipeline.from_yaml(y)
        assert pipe2.name == "ypipe"
        assert len(pipe2.get_steps()) == 1

    def test_validate_detects_missing_dependency(self):
        pipe = IngestionPipeline(name="depcheck")
        s1 = PipelineStep(name="s1", step_type="a", handler=_dummy_handler, inputs=["missing"])
        pipe.add_step(s1)
        errors = pipe.validate()
        assert any("requires input" in e for e in errors)

    def test_validate_clean_pipeline(self):
        pipe = IngestionPipeline(name="clean")
        s1 = PipelineStep(name="gen", step_type="src", handler=_dummy_handler, outputs=["x"])
        s2 = PipelineStep(name="use", step_type="proc", handler=_dummy_handler, inputs=["x"])
        pipe.add_step(s1)
        pipe.add_step(s2)
        errors = pipe.validate()
        assert errors == []

    def test_validate_detects_cycle(self):
        pipe = IngestionPipeline(name="cycle")
        s1 = PipelineStep(name="a", step_type="t", handler=_dummy_handler, inputs=["b"], outputs=["a"])
        s2 = PipelineStep(name="b", step_type="t", handler=_dummy_handler, inputs=["a"], outputs=["b"])
        pipe.add_step(s1)
        pipe.add_step(s2)
        errors = pipe.validate()
        assert any("cycle" in e for e in errors)


class TestIngestionContext:
    def test_set_get(self):
        ctx = IngestionContext()
        ctx.set("key1", "value1")
        assert ctx.get("key1") == "value1"

    def test_get_default(self):
        ctx = IngestionContext()
        assert ctx.get("nonexistent", "default") == "default"

    def test_has(self):
        ctx = IngestionContext()
        ctx.set("a", 1)
        assert ctx.has("a") is True
        assert ctx.has("b") is False

    def test_keys(self):
        ctx = IngestionContext()
        ctx.set("x", 1)
        ctx.set("y", 2)
        assert set(ctx.keys()) == {"x", "y"}

    def test_stats(self):
        ctx = IngestionContext()
        stats = ctx.stats()
        assert "records_processed" in stats
        assert "errors_count" in stats
        assert stats["records_processed"] == 0


class TestIngestionResult:
    def test_minimal(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        r = IngestionResult(
            pipeline_name="p", status="completed",
            started_at=now, completed_at=now,
        )
        assert r.duration_seconds == 0.0
        assert r.step_results == []
        assert r.records_downloaded == 0


class TestScheduleDefinition:
    def test_minimal(self):
        s = ScheduleDefinition(name="sched1", pipeline_name="pipe1", cron_expression="0 * * * *")
        assert s.is_active is True
        assert s.config is None
        assert s.last_run_at is None

    def test_full(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        s = ScheduleDefinition(
            name="s2", pipeline_name="p2", cron_expression="*/5 * * * *",
            config={"retries": 3}, is_active=False, last_run_at=now,
        )
        assert s.config["retries"] == 3
        assert s.is_active is False


class TestIngestionScheduler:
    def test_next_cron_every_5_minutes(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("*/5 * * * *", after=base)
        assert result == base + __import__("datetime").timedelta(minutes=5)

    def test_next_cron_every_2_hours_weekdays(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone, timedelta
        base = datetime(2025, 1, 6, 0, 0, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("0 */2 * * 1-5", after=base)
        assert result.hour in (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
        assert result.weekday() < 5

    def test_next_cron_daily_at_midnight(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone, timedelta
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("0 0 * * *", after=base)
        assert result == base + timedelta(days=1)

    def test_next_cron_specific_minute(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone
        base = datetime(2025, 1, 1, 10, 15, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("30 10 * * *", after=base)
        assert result.minute == 30
        assert result.hour == 10

    def test_invalid_cron_expression_raises(self):
        scheduler = IngestionScheduler()
        with pytest.raises(IngestionScheduleError, match="5 fields"):
            scheduler.next_cron_trigger("invalid")

    def test_next_cron_respects_dom(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone
        base = datetime(2025, 1, 14, 12, 0, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("0 0 15 * *", after=base)
        assert result.day == 15

    def test_next_cron_wildcard_dom_and_dow(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("0 0 * * 0", after=base)
        assert result.hour == 0
        assert result.minute == 0

    def test_register_schedule_in_memory(self):
        scheduler = IngestionScheduler()
        sched_def = ScheduleDefinition(
            name="test_sched", pipeline_name="pipe", cron_expression="0 * * * *"
        )

        async def test():
            result = await scheduler.register_schedule(sched_def)
            assert result == "test_sched"
            schedules = await scheduler.list_schedules()
            assert len(schedules) == 1
            assert schedules[0]["name"] == "test_sched"

        import asyncio
        asyncio.run(test())

    def test_register_duplicate_raises(self):
        scheduler = IngestionScheduler()
        s1 = ScheduleDefinition(name="dup", pipeline_name="p", cron_expression="0 * * * *")

        async def test():
            await scheduler.register_schedule(s1)
            with pytest.raises(IngestionScheduleError):
                await scheduler.register_schedule(s1)

        import asyncio
        asyncio.run(test())

    def test_pause_resume_schedule(self):
        scheduler = IngestionScheduler()
        s = ScheduleDefinition(name="pr", pipeline_name="p", cron_expression="0 * * * *")

        async def test():
            await scheduler.register_schedule(s)
            await scheduler.pause_schedule("pr")
            schedules = await scheduler.list_schedules()
            assert schedules[0]["is_active"] is False
            await scheduler.resume_schedule("pr")
            schedules = await scheduler.list_schedules()
            assert schedules[0]["is_active"] is True

        import asyncio
        asyncio.run(test())

    def test_delete_schedule(self):
        scheduler = IngestionScheduler()
        s = ScheduleDefinition(name="del", pipeline_name="p", cron_expression="0 * * * *")

        async def test():
            await scheduler.register_schedule(s)
            await scheduler.delete_schedule("del")
            schedules = await scheduler.list_schedules()
            assert len(schedules) == 0

        import asyncio
        asyncio.run(test())

    def test_next_cron_january_to_february(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone
        base = datetime(2025, 1, 31, 23, 59, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("0 0 1 * *", after=base)
        assert result.month == 2
        assert result.day == 1

    def test_next_cron_multiple_comma_values(self):
        scheduler = IngestionScheduler()
        from datetime import datetime, timezone
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = scheduler.next_cron_trigger("15,45 9 * * *", after=base)
        assert result.minute in (15, 45)
        assert result.hour == 9


class TestIngestionExceptions:
    def test_hierarchy(self):
        assert issubclass(IngestionStepError, IngestionError)
        assert issubclass(IngestionPipelineError, IngestionError)
        assert issubclass(IngestionTimeoutError, IngestionError)
        assert issubclass(IngestionConfigError, IngestionError)
        assert issubclass(IngestionScheduleError, IngestionError)
        assert issubclass(IngestionCancelledError, IngestionError)
