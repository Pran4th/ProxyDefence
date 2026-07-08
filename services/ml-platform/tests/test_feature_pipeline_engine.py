import pytest

from feature_store.pipeline_engine import (
    FeaturePipelineStep,
    FeaturePipelineDefinition,
    FeaturePipelineRunResult,
    build_pipeline_from_steps,
    pipeline_step_from_transform,
    PipelineCache,
)


class TestFeaturePipelineStep:
    def test_minimal(self):
        step = FeaturePipelineStep(
            name="s1", transform_name="scale", transform_params={},
            inputs=["a"], output="a_scaled", depends_on=[],
        )
        assert step.name == "s1"
        assert step.transform_name == "scale"
        assert step.inputs == ["a"]
        assert step.output == "a_scaled"

    def test_with_dependencies(self):
        step = FeaturePipelineStep(
            name="s2", transform_name="aggregate", transform_params={"window": 7},
            inputs=["b", "c"], output="b_agg", depends_on=["s1"],
        )
        assert step.depends_on == ["s1"]
        assert step.transform_params["window"] == 7


class TestFeaturePipelineDefinition:
    def test_minimal(self):
        steps = [
            FeaturePipelineStep(
                name="s1", transform_name="scale", transform_params={},
                inputs=["x"], output="x_scaled", depends_on=[],
            ),
        ]
        defn = FeaturePipelineDefinition(
            name="pipe1", version=1, description="test",
            steps=steps, input_columns=["x"],
            output_columns=["x_scaled"], tags=["dev"], metadata={},
        )
        assert defn.name == "pipe1"
        assert defn.version == 1
        assert len(defn.steps) == 1
        assert defn.tags == ["dev"]


class TestFeaturePipelineRunResult:
    def test_minimal(self):
        result = FeaturePipelineRunResult(
            pipeline_name="p", pipeline_version=1, status="completed",
            step_results=[], output_df_shape=(100, 5),
            cache_hits=2, cache_misses=3, duration_seconds=1.5,
            snapshot_uuid=None, error=None,
        )
        assert result.status == "completed"
        assert result.cache_hits == 2
        assert result.cache_misses == 3
        assert result.output_df_shape == (100, 5)

    def test_failed(self):
        result = FeaturePipelineRunResult(
            pipeline_name="p", pipeline_version=1, status="failed",
            step_results=[], output_df_shape=(0, 0),
            cache_hits=0, cache_misses=0, duration_seconds=0.0,
            snapshot_uuid=None, error="OOM",
        )
        assert result.error == "OOM"


class TestBuildPipelineFromSteps:
    def test_simple_chain(self):
        defn = build_pipeline_from_steps(
            pipeline_name="chain",
            steps=[
                ("raw_scaled", "scaler", {"method": "standard"}, ["raw"]),
                ("feature", "pca", {"n": 3}, ["raw_scaled"]),
            ],
            input_columns=["raw"],
            description="chain pipeline",
        )
        assert len(defn.steps) == 2
        assert defn.steps[0].name == "raw_scaled"
        assert defn.steps[1].name == "feature"
        # second step should depend on first since it uses its output
        assert "raw_scaled" in defn.steps[1].depends_on

    def test_diamond_dependency(self):
        defn = build_pipeline_from_steps(
            pipeline_name="diamond",
            steps=[
                ("base", "passthrough", {}, ["input"]),
                ("left", "passthrough", {}, ["base"]),
                ("right", "passthrough", {}, ["base"]),
                ("merged", "passthrough", {}, ["left", "right"]),
            ],
            input_columns=["input"],
        )
        assert len(defn.steps) == 4
        # base has no deps
        assert defn.steps[0].depends_on == []
        # left and right depend on base
        assert "base" in defn.steps[1].depends_on
        assert "base" in defn.steps[2].depends_on
        # merged depends on both left and right
        assert "left" in defn.steps[3].depends_on
        assert "right" in defn.steps[3].depends_on


def noop_transform(df):
    return df


class TestPipelineStepFromTransform:
    def test_basic_wrap(self):
        step = pipeline_step_from_transform(
            transform_name="scaler",
            output_column="scaled",
            input_columns=["raw"],
            transform_params={"method": "standard"},
        )
        assert step.name == "scaled"
        assert step.transform_name == "scaler"
        assert step.transform_params == {"method": "standard"}
        assert step.inputs == ["raw"]
        assert step.depends_on == []

    def test_with_depends_on(self):
        step = pipeline_step_from_transform(
            transform_name="pca",
            output_column="pca_feat",
            input_columns=["scaled"],
            depends_on=["previous_step"],
        )
        assert step.depends_on == ["previous_step"]


class TestPipelineCache:
    def test_init(self):
        cache = PipelineCache(capacity=100)
        assert cache.size == 0
        assert cache.hit_rate == 0.0

    def test_set_and_get(self):
        cache = PipelineCache(capacity=100)
        cache.set("step1", "hash1", {"result": 42})
        result = cache.get("step1", "hash1")
        assert result == {"result": 42}

    def test_get_miss(self):
        cache = PipelineCache(capacity=100)
        result = cache.get("missing", "hash")
        assert result is None

    def test_has(self):
        cache = PipelineCache(capacity=100)
        cache.set("s", "h", "val")
        assert cache.has("s", "h") is True
        assert cache.has("s", "other") is False

    def test_invalidate_step(self):
        cache = PipelineCache(capacity=100)
        cache.set("step1", "h1", "v1")
        cache.set("step1", "h2", "v2")
        cache.set("step2", "h1", "v3")
        cache.invalidate(step_name="step1")
        assert cache.has("step1", "h1") is False
        assert cache.has("step2", "h1") is True

    def test_invalidate_all(self):
        cache = PipelineCache(capacity=100)
        cache.set("s1", "h1", "v1")
        cache.set("s2", "h2", "v2")
        cache.invalidate_all()
        assert cache.size == 0

    def test_hit_rate_tracking(self):
        cache = PipelineCache(capacity=100)
        cache.set("s", "h", "v")
        cache.get("s", "h")
        cache.get("s", "x")
        assert cache.hit_rate == 0.5

    def test_lru_eviction(self):
        cache = PipelineCache(capacity=3)
        cache.set("a", "1", "a1")
        cache.set("b", "2", "b2")
        cache.set("c", "3", "c3")
        cache.set("d", "4", "d4")
        assert cache.size == 3
        assert cache.has("a", "1") is False


class TestExecutionOrder:
    def test_get_execution_order(self):
        from feature_store.pipeline_engine import FeaturePipelineEngine
        engine = FeaturePipelineEngine()

        steps = [
            FeaturePipelineStep(name="a", transform_name="t", transform_params={},
                                inputs=[], output="a", depends_on=[]),
            FeaturePipelineStep(name="b", transform_name="t", transform_params={},
                                inputs=["a"], output="b", depends_on=["a"]),
            FeaturePipelineStep(name="c", transform_name="t", transform_params={},
                                inputs=["b"], output="c", depends_on=["b"]),
        ]
        ordered = engine.get_execution_order(steps)
        names = [s.name for s in ordered]
        # a must come before b, b before c
        assert names.index("a") < names.index("b") < names.index("c")

    def test_diamond_order(self):
        from feature_store.pipeline_engine import FeaturePipelineEngine
        engine = FeaturePipelineEngine()

        steps = [
            FeaturePipelineStep(name="base", transform_name="t", transform_params={},
                                inputs=[], output="base", depends_on=[]),
            FeaturePipelineStep(name="left", transform_name="t", transform_params={},
                                inputs=["base"], output="left", depends_on=["base"]),
            FeaturePipelineStep(name="right", transform_name="t", transform_params={},
                                inputs=["base"], output="right", depends_on=["base"]),
            FeaturePipelineStep(name="merge", transform_name="t", transform_params={},
                                inputs=["left", "right"], output="merge",
                                depends_on=["left", "right"]),
        ]
        ordered = engine.get_execution_order(steps)
        names = [s.name for s in ordered]
        assert names.index("base") < names.index("left")
        assert names.index("base") < names.index("right")
        assert names.index("left") < names.index("merge")
        assert names.index("right") < names.index("merge")

    def test_cycle_detection(self):
        from feature_store.pipeline_engine import FeaturePipelineEngine
        engine = FeaturePipelineEngine()

        steps = [
            FeaturePipelineStep(name="a", transform_name="t", transform_params={},
                                inputs=["c"], output="a", depends_on=["c"]),
            FeaturePipelineStep(name="b", transform_name="t", transform_params={},
                                inputs=["a"], output="b", depends_on=["a"]),
            FeaturePipelineStep(name="c", transform_name="t", transform_params={},
                                inputs=["b"], output="c", depends_on=["b"]),
        ]
        with pytest.raises(ValueError, match="Circular dependency"):
            engine.get_execution_order(steps)

    def test_no_dependencies(self):
        from feature_store.pipeline_engine import FeaturePipelineEngine
        engine = FeaturePipelineEngine()

        steps = [
            FeaturePipelineStep(name="a", transform_name="t", transform_params={},
                                inputs=[], output="a", depends_on=[]),
            FeaturePipelineStep(name="b", transform_name="t", transform_params={},
                                inputs=[], output="b", depends_on=[]),
        ]
        ordered = engine.get_execution_order(steps)
        assert len(ordered) == 2

    def test_disconnected_graph(self):
        from feature_store.pipeline_engine import FeaturePipelineEngine
        engine = FeaturePipelineEngine()

        steps = [
            FeaturePipelineStep(name="a", transform_name="t", transform_params={},
                                inputs=[], output="a", depends_on=[]),
            FeaturePipelineStep(name="b", transform_name="t", transform_params={},
                                inputs=["x"], output="b", depends_on=[]),
        ]
        ordered = engine.get_execution_order(steps)
        assert len(ordered) == 2
