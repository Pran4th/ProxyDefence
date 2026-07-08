import pytest

from pipeline.dag import PipelineDAG, PipelineStep, PipelineRunResult
from pipeline.execution import PipelineExecution, get_pipeline_execution
from pipeline.caching import PipelineCache
from pipeline.export import PipelineExporter


class TestPipelineDAG:
    def test_add_step(self):
        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("step1", lambda x: x, inputs=["data"], outputs=["result"]))
        assert dag.step_count == 1

    def test_duplicate_step_raises(self):
        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("step1", lambda: None))
        with pytest.raises(ValueError):
            dag.add_step(PipelineStep("step1", lambda: None))

    def test_execution_order(self):
        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("step1", lambda: None, outputs=["a"]))
        dag.add_step(PipelineStep("step2", lambda a: None, inputs=["a"], dependencies=["step1"]))
        dag.add_step(PipelineStep("step3", lambda a: None, inputs=["a"], dependencies=["step1"]))
        order = dag.get_execution_order()
        assert order.index("step1") < order.index("step2")
        assert order.index("step1") < order.index("step3")

    def test_validate_no_errors(self):
        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("step1", lambda: None, outputs=["a"]))
        dag.add_step(PipelineStep("step2", lambda a: None, inputs=["a"], dependencies=["step1"]))
        errors = dag.validate()
        assert len(errors) == 0

    def test_validate_missing_dependency(self):
        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("step2", lambda: None, dependencies=["step1"]))
        errors = dag.validate()
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_execute_simple(self):
        async def add_one(data=None):
            return (data or 0) + 1

        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("add", add_one, inputs=["data"], outputs=["result"]))
        results = await dag.execute(context={"data": 5})
        assert results[0].status == "completed"
        assert results[0].duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        async def failing():
            raise ValueError("test error")

        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("fail", failing))
        results = await dag.execute()
        assert results[0].status == "failed"
        assert "test error" in results[0].error

    def test_history(self):
        dag = PipelineDAG("test")
        assert len(dag.get_history()) == 0


class TestPipelineExecution:
    def test_register_and_list(self):
        exec_mgr = PipelineExecution()
        dag = PipelineDAG("test_pipeline")
        exec_mgr.register(dag)
        pipelines = exec_mgr.list_pipelines()
        names = [p["name"] for p in pipelines]
        assert "test_pipeline" in names

    def test_get_nonexistent(self):
        exec_mgr = PipelineExecution()
        dag = exec_mgr.get("nonexistent")
        assert dag is None

    def test_run_nonexistent_raises(self):
        import asyncio
        exec_mgr = PipelineExecution()
        with pytest.raises(ValueError):
            asyncio.run(exec_mgr.run("nonexistent"))


class TestPipelineCache:
    def test_cache_key_consistency(self):
        cache = PipelineCache()
        key1 = cache._make_key("step", {"param": 1}, "abc")
        key2 = cache._make_key("step", {"param": 1}, "abc")
        assert key1 == key2

    def test_cache_key_differs(self):
        cache = PipelineCache()
        key1 = cache._make_key("step", {"param": 1})
        key2 = cache._make_key("step", {"param": 2})
        assert key1 != key2

    def test_cache_not_found(self):
        cache = PipelineCache()
        result = cache.get("nonexistent_step")
        assert result is None

    def test_cache_invalidate(self):
        cache = PipelineCache()
        cache.set("test_step", pd.DataFrame({"a": [1, 2, 3]}))
        assert cache.size >= 1
        cache.invalidate("test_step")
        # After invalidation, memory cache should be cleared
        result = cache.get("test_step")
        assert result is None

    def test_disk_size(self):
        import tempfile
        cache = PipelineCache(tempfile.mkdtemp())
        assert cache.disk_size_bytes == 0


class TestPipelineExporter:
    def test_to_dict(self):
        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("step1", lambda: None, outputs=["a"], params={"p": 1}))
        data = PipelineExporter.to_dict(dag)
        assert data["name"] == "test"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["name"] == "step1"

    def test_from_dict(self):
        data = {
            "name": "imported",
            "steps": [
                {"name": "s1", "inputs": [], "outputs": ["a"], "dependencies": [], "params": {}},
            ],
        }
        func_reg = {"s1": lambda **x: None}
        dag = PipelineExporter.from_dict(data, func_reg)
        assert dag.name == "imported"
        assert dag.step_count == 1

    def test_export_yaml(self, tmp_path):
        dag = PipelineDAG("test_export")
        dag.add_step(PipelineStep("step1", lambda: None))
        path = str(tmp_path / "pipeline.yaml")
        PipelineExporter.export_yaml(dag, path)
        assert Path(path).exists()

    def test_export_json(self, tmp_path):
        dag = PipelineDAG("test_export")
        dag.add_step(PipelineStep("step1", lambda: None))
        path = str(tmp_path / "pipeline.json")
        PipelineExporter.export_json(dag, path)
        assert Path(path).exists()

    def test_replay(self):
        dag = PipelineDAG("test")
        dag.add_step(PipelineStep("s1", lambda: None, outputs=["a"]))
        dag.add_step(PipelineStep("s2", lambda a: None, inputs=["a"], outputs=["b"]))
        results = [
            {"step": "s1", "outputs": {"a": 1}},
            {"step": "s2", "outputs": {"b": 2}},
        ]
        replay = PipelineExporter.replay(dag, results)
        assert replay["pipeline"] == "test"
        assert len(replay["steps"]) == 2


# Need pd import for test
import pandas as pd
from pathlib import Path
