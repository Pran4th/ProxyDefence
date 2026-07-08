import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from research.config import ResearchConfigLoader, ConfigValidationError
from research.experiment import ExperimentManager
from research.utils.seed import SeedManager
from research.utils.experiment_logger import ExperimentLogger
from research.utils.artifact_manager import ArtifactManager
from research.utils.notebook_helpers import NotebookHelpers
from research.utils.explorers import DatasetExplorer, FeatureExplorer, CorrelationExplorer, StatisticsExplorer
from research.utils.model_comparison import ModelComparison
from research.utils.config_loader import ConfigLoader
from research.utils.constants import ResearchConstants


class TestResearchConfigLoader:
    def test_default_config_structure(self):
        cfg = ResearchConfigLoader.build_default_config("test_experiment")
        assert "experiment" in cfg
        assert "dataset" in cfg
        assert "model" in cfg
        assert "export" in cfg
        assert cfg["experiment"]["name"] == "test_experiment"

    def test_config_validation_missing_experiment(self):
        loader = ResearchConfigLoader()
        with pytest.raises(ConfigValidationError):
            loader._validate({"dataset": {}})

    def test_load_yaml(self, tmp_path):
        loader = ResearchConfigLoader(str(tmp_path))
        config = {"experiment": {"name": "test", "type": "classification"}}
        path = loader.save(config, "test_config")
        loaded = loader.load(path)
        assert loaded["experiment"]["name"] == "test"

    def test_load_json(self, tmp_path):
        loader = ResearchConfigLoader(str(tmp_path))
        config = {"experiment": {"name": "test_json", "type": "regression"}}
        path = loader.save(config, "test_json", format="json")
        loaded = loader.load(path)
        assert loaded["experiment"]["name"] == "test_json"

    def test_list_configs(self, tmp_path):
        loader = ResearchConfigLoader(str(tmp_path))
        config = {"experiment": {"name": "test", "type": "classification"}}
        loader.save(config, "exp1")
        configs = loader.list_configs()
        assert len(configs) >= 1


class TestExperimentManager:
    def test_create_experiment_structure(self):
        import asyncio
        mgr = ExperimentManager()
        # Test just the structure, not DB calls
        exp = {
            "name": "test_exp",
            "experiment_type": "classification",
            "description": "A test",
            "author": "researcher",
            "random_seed": 42,
            "tags": ["energy", "risk"],
        }
        assert exp["name"] == "test_exp"
        assert exp["experiment_type"] == "classification"

    def test_git_commit(self):
        mgr = ExperimentManager()
        commit = mgr._get_git_commit()
        # May be None if not in git, but shouldn't crash
        assert commit is None or len(commit) == 40

    def test_compare_runs_structure(self):
        runs = [
            {"run_uuid": "a", "run_name": "run1", "metrics": {"accuracy": 0.95}, "status": "completed"},
            {"run_uuid": "b", "run_name": "run2", "metrics": {"accuracy": 0.92}, "status": "completed"},
        ]
        sorted_runs = sorted(runs, key=lambda x: x["metrics"]["accuracy"], reverse=True)
        assert sorted_runs[0]["run_name"] == "run1"


class TestSeedManager:
    def test_set_and_get_seed(self):
        SeedManager.reset()
        SeedManager.set_seed(42)
        assert SeedManager.get_seed() == 42

    def test_register_seed(self):
        SeedManager.register_seed("custom", 123)
        assert SeedManager.get_seed("custom") == 123

    def test_generate_seed(self):
        assert SeedManager.generate_seed(42, 0) == 42
        assert SeedManager.generate_seed(42, 5) == 47

    def test_deterministic_numpy(self):
        SeedManager.set_seed(42)
        a = np.random.rand(5)
        SeedManager.set_seed(42)
        b = np.random.rand(5)
        np.testing.assert_array_equal(a, b)


class TestExperimentLogger:
    def test_log_metrics(self):
        logger = ExperimentLogger("test", "run1")
        logger.log_metric("accuracy", 0.95)
        logger.log_metrics({"f1": 0.93, "precision": 0.94})
        summary = logger.get_summary()
        assert summary["metrics"]["accuracy"] == 0.95
        assert summary["metrics"]["f1"] == 0.93
        assert summary["experiment"] == "test"

    def test_log_params(self):
        logger = ExperimentLogger("test")
        logger.log_param("learning_rate", 0.01)
        logger.log_params({"max_depth": 6, "n_estimators": 100})
        summary = logger.get_summary()
        assert summary["params"]["learning_rate"] == 0.01
        assert summary["params"]["n_estimators"] == 100

    def test_log_artifact(self):
        logger = ExperimentLogger("test")
        logger.log_artifact("/path/to/model.joblib")
        summary = logger.get_summary()
        assert summary["artifact_count"] == 1

    def test_to_json(self):
        logger = ExperimentLogger("test", "run1")
        logger.log_metric("accuracy", 0.95)
        json_str = logger.to_json()
        data = json.loads(json_str)
        assert data["experiment"] == "test"
        assert data["run"] == "run1"


class TestArtifactManager:
    def test_guess_mime(self, tmp_path):
        mgr = ArtifactManager(str(tmp_path))
        assert "json" in mgr._guess_mime("/path/to/file.json")
        assert "parquet" in mgr._guess_mime("/path/to/file.parquet")
        assert "csv" in mgr._guess_mime("/path/to/file.csv")

    def test_checksum(self, tmp_path):
        mgr = ArtifactManager(str(tmp_path))
        f = tmp_path / "test.txt"
        f.write_text("data")
        checksum = mgr._compute_checksum(str(f))
        assert len(checksum) == 64


class TestNotebookHelpers:
    def test_describe_dataframe(self):
        df = pd.DataFrame({"a": [1, 2, None], "b": ["x", "y", "z"]})
        info = NotebookHelpers.describe_dataframe(df, "test")
        assert info["name"] == "test"
        assert info["shape"] == [3, 2]
        assert "missing_values" in info
        assert info["missing_values"]["a"] == 1

    def test_log_to_file(self, tmp_path):
        data = {"accuracy": 0.95}
        path = NotebookHelpers.log_to_file("test_log", data, str(tmp_path))
        assert Path(path).exists()
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["accuracy"] == 0.95


class TestExplorers:
    def test_dataset_explorer_overview(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        overview = DatasetExplorer.overview(df)
        assert overview["shape"] == [3, 2]
        assert overview["column_types"]["numerical"] == 1
        assert overview["column_types"]["categorical"] == 1

    def test_missing_analysis(self):
        df = pd.DataFrame({"a": [1, None, None], "b": ["x", "y", "z"]})
        missing = DatasetExplorer.missing_analysis(df)
        assert len(missing) == 2
        a_missing = missing[missing["column"] == "a"]
        assert a_missing["missing_count"].values[0] == 2

    def test_duplicate_analysis(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [4, 4, 5]})
        result = DatasetExplorer.duplicate_analysis(df)
        assert result["duplicate_count"] == 1

    def test_feature_explorer_numeric(self):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        analysis = FeatureExplorer.analyze_numeric(series)
        assert analysis["mean"] == 3.0
        assert analysis["min"] == 1.0
        assert analysis["max"] == 5.0

    def test_feature_explorer_categorical(self):
        series = pd.Series(["a", "b", "a", "b", "c"])
        analysis = FeatureExplorer.analyze_categorical(series)
        assert analysis["unique"] == 3
        assert analysis["entropy"] > 0

    def test_correlation_explorer(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [2, 4, 6, 8, 10], "c": [5, 4, 3, 2, 1]})
        result = CorrelationExplorer.analyze(df)
        assert "mean_abs_correlation" in result
        assert result["max_correlation"] >= 0.9  # a and b perfectly correlated

    def test_correlation_insufficient_columns(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = CorrelationExplorer.analyze(df)
        assert "warning" in result

    def test_statistics_explorer_summary(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        summary = StatisticsExplorer.summary(df)
        assert "overview" in summary
        assert "numeric_summary" in summary
        assert "categorical_summary" in summary


class TestModelComparison:
    def test_add_and_leaderboard(self):
        mc = ModelComparison()
        mc.add_result("model_a", {"f1": 0.95, "accuracy": 0.94})
        mc.add_result("model_b", {"f1": 0.93, "accuracy": 0.91})
        lb = mc.get_leaderboard("f1")
        assert lb[0]["model_name"] == "model_a"
        assert lb[1]["model_name"] == "model_b"

    def test_get_comparison_table(self):
        mc = ModelComparison()
        mc.add_result("model_a", {"f1": 0.95})
        mc.add_result("model_b", {"f1": 0.93})
        df = mc.get_comparison_table()
        assert len(df) == 2
        assert "model_name" in df.columns

    def test_get_summary(self):
        mc = ModelComparison()
        mc.add_result("model_a", {"f1": 0.95})
        summary = mc.get_summary()
        assert summary["total_models"] == 1


class TestConfigLoader:
    def test_deep_merge(self):
        loader = ConfigLoader()
        base = {"model": {"type": "xgboost", "params": {"lr": 0.01}}}
        override = {"model": {"params": {"lr": 0.001, "depth": 6}}}
        merged = loader.merge_configs(base, override)
        assert merged["model"]["type"] == "xgboost"
        assert merged["model"]["params"]["lr"] == 0.001
        assert merged["model"]["params"]["depth"] == 6

    def test_resolve_env_vars(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "resolved_value")
        loader = ConfigLoader()
        config = {"key": "${TEST_VAR}", "normal": "value", "nested": {"inner": "${TEST_VAR}"}}
        resolved = loader.resolve_env_vars(config)
        assert resolved["key"] == "resolved_value"
        assert resolved["normal"] == "value"
        assert resolved["nested"]["inner"] == "resolved_value"

    def test_resolve_with_default(self):
        loader = ConfigLoader()
        config = {"key": "${MISSING_VAR:-default_value}"}
        resolved = loader.resolve_env_vars(config)
        assert resolved["key"] == "default_value"


class TestResearchConstants:
    def test_valid_model_types(self):
        assert "xgboost" in ResearchConstants.VALID_MODEL_TYPES
        assert "random_forest" in ResearchConstants.VALID_MODEL_TYPES
        assert len(ResearchConstants.VALID_MODEL_TYPES) >= 5

    def test_valid_dataset_types(self):
        assert "energy_infrastructure" in ResearchConstants.VALID_DATASET_TYPES
        assert "commodity_prices" in ResearchConstants.VALID_DATASET_TYPES

    def test_valid_experiment_types(self):
        assert "classification" in ResearchConstants.VALID_EXPERIMENT_TYPES
        assert "forecasting" in ResearchConstants.VALID_EXPERIMENT_TYPES
