import pytest

from research.utils.explorers import (
    SchemaExplorer,
    MetadataExplorer,
    PipelineExplorer,
    ExperimentExplorer,
    ArtifactExplorer,
    ModelExplorer,
    DatasetExplorer,
    FeatureExplorer,
    CorrelationExplorer,
    StatisticsExplorer,
)


class TestSchemaExplorer:
    def test_can_instantiate(self):
        explorer = SchemaExplorer()
        assert isinstance(explorer, SchemaExplorer)

    def test_has_expected_methods(self):
        explorer = SchemaExplorer()
        methods = ["get_table_schema", "get_all_tables", "find_columns",
                    "get_table_statistics", "get_foreign_keys", "get_indexes"]
        for m in methods:
            assert hasattr(explorer, m), f"Missing method: {m}"


class TestMetadataExplorer:
    def test_can_instantiate(self):
        explorer = MetadataExplorer()
        assert isinstance(explorer, MetadataExplorer)

    def test_has_expected_methods(self):
        explorer = MetadataExplorer()
        methods = ["get_dataset_metadata", "get_feature_metadata",
                    "get_model_metadata", "get_experiment_metadata",
                    "get_pipeline_metadata", "get_quality_metadata"]
        for m in methods:
            assert hasattr(explorer, m), f"Missing method: {m}"


class TestPipelineExplorer:
    def test_can_instantiate(self):
        explorer = PipelineExplorer()
        assert isinstance(explorer, PipelineExplorer)

    def test_has_expected_methods(self):
        explorer = PipelineExplorer()
        methods = ["list_pipelines", "get_pipeline", "get_pipeline_runs",
                    "get_pipeline_run", "get_failed_pipelines", "get_pipeline_stats"]
        for m in methods:
            assert hasattr(explorer, m), f"Missing method: {m}"


class TestExperimentExplorer:
    def test_can_instantiate(self):
        explorer = ExperimentExplorer()
        assert isinstance(explorer, ExperimentExplorer)

    def test_has_expected_methods(self):
        explorer = ExperimentExplorer()
        methods = ["get_experiment_summary", "get_best_runs",
                    "get_experiment_comparison", "get_experiment_timeline",
                    "get_experiment_params", "get_experiment_metrics"]
        for m in methods:
            assert hasattr(explorer, m), f"Missing method: {m}"


class TestArtifactExplorer:
    def test_can_instantiate(self):
        explorer = ArtifactExplorer()
        assert isinstance(explorer, ArtifactExplorer)

    def test_has_expected_methods(self):
        explorer = ArtifactExplorer()
        methods = ["list_artifacts", "get_artifact", "get_artifact_types",
                    "get_artifact_stats", "get_recent_artifacts"]
        for m in methods:
            assert hasattr(explorer, m), f"Missing method: {m}"


class TestModelExplorer:
    def test_can_instantiate(self):
        explorer = ModelExplorer()
        assert isinstance(explorer, ModelExplorer)

    def test_has_expected_methods(self):
        explorer = ModelExplorer()
        methods = ["list_models", "get_model_detail", "get_model_versions",
                    "get_best_model", "get_model_lineage", "get_model_governance",
                    "get_model_performance_trend"]
        for m in methods:
            assert hasattr(explorer, m), f"Missing method: {m}"
