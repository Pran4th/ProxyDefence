from pathlib import Path

import numpy as np
import pytest

from monitoring.drift import PSIDetector, KSDetector, DistributionShiftDetector


class TestPSIDetector:
    def test_identical_distributions(self):
        detector = PSIDetector(bins=10)
        data = np.random.normal(0, 1, 1000)
        psi = detector.compute_psi(data, data)
        assert psi < 0.05

    def test_different_distributions(self):
        detector = PSIDetector(bins=10)
        expected = np.random.normal(0, 1, 1000)
        actual = np.random.normal(5, 1, 1000)
        psi = detector.compute_psi(expected, actual)
        assert psi > 0.2

    def test_detect_no_drift(self):
        detector = PSIDetector()
        data = np.random.normal(0, 1, 1000)
        result = detector.detect(data, data, feature_name="test")
        assert not result.is_drift

    def test_detect_drift(self):
        detector = PSIDetector()
        expected = np.random.normal(0, 1, 1000)
        actual = np.random.normal(5, 1, 1000)
        result = detector.detect(expected, actual, feature_name="test", threshold=0.1)
        assert result.is_drift
        assert result.feature_name == "test"
        assert result.drift_type == "psi"


class TestKSDetector:
    def test_identical_distributions(self):
        detector = KSDetector()
        data = np.random.normal(0, 1, 500)
        result = detector.detect(data, data, feature_name="test", threshold=0.05)
        assert not result.is_drift

    def test_different_distributions(self):
        detector = KSDetector()
        expected = np.random.normal(0, 1, 500)
        actual = np.random.normal(3, 1, 500)
        result = detector.detect(expected, actual, feature_name="test", threshold=0.05)
        assert result.is_drift

    def test_empty_data_returns_drift(self):
        detector = KSDetector()
        result = detector.detect(np.array([]), np.array([1, 2, 3]), feature_name="test")
        assert result.is_drift

    def test_p_value_in_details(self):
        detector = KSDetector()
        a = np.random.normal(0, 1, 500)
        b = np.random.normal(0, 1, 500)
        result = detector.detect(a, b, feature_name="test")
        assert "p_value" in result.details


class TestDistributionShiftDetector:
    def test_combined_no_drift(self):
        detector = DistributionShiftDetector(psi_threshold=0.3, ks_threshold=0.01)
        data = np.random.normal(0, 1, 1000)
        result = detector.detect(data, data, feature_name="test")
        assert result.drift_type == "combined"
        assert "psi" in result.details
        assert "ks" in result.details

    def test_combined_drift(self):
        detector = DistributionShiftDetector(psi_threshold=0.1, ks_threshold=0.05)
        expected = np.random.normal(0, 1, 1000)
        actual = np.random.normal(5, 1, 1000)
        result = detector.detect(expected, actual, feature_name="test")
        assert result.is_drift


class TestFeatureCache:
    def test_cache_hit_and_miss(self):
        from feature_store.cache import FeatureCache
        cache = FeatureCache(capacity=100, ttl_seconds=3600)
        result = cache.get("port", "abc123", 1)
        assert result is None
        assert cache.hit_rate == 0.0
        cache.set("port", "abc123", 1, {"throughput": 50.0, "region": "middle_east"})
        result = cache.get("port", "abc123", 1)
        assert result is not None
        assert result["throughput"] == 50.0

    def test_cache_eviction(self):
        from feature_store.cache import FeatureCache
        cache = FeatureCache(capacity=2, ttl_seconds=3600)
        cache.set("port", "a", 1, {"v": 1})
        cache.set("port", "b", 1, {"v": 2})
        cache.set("port", "c", 1, {"v": 3})
        assert cache.get("port", "a", 1) is None
        assert cache.get("port", "c", 1) is not None

    def test_cache_invalidation(self):
        from feature_store.cache import FeatureCache
        cache = FeatureCache(capacity=100, ttl_seconds=3600)
        cache.set("port", "abc", 1, {"v": 1})
        cache.invalidate("port", "abc")
        assert cache.get("port", "abc", 1) is None

    def test_cache_hit_rate(self):
        from feature_store.cache import FeatureCache
        cache = FeatureCache(ttl_seconds=3600)
        cache.get("port", "x", 1)
        cache.set("port", "x", 1, {"v": 1})
        cache.get("port", "x", 1)
        assert cache.hit_rate == 0.5

    def test_capacity_property(self):
        from feature_store.cache import FeatureCache
        cache = FeatureCache(capacity=42)
        assert cache.capacity == 42


class TestAlertManager:
    def test_alert_fires_on_threshold(self):
        from monitoring.alerts import AlertRule, AlertManager
        am = AlertManager()
        rule = AlertRule("test_rule", "test_metric", "gt", 0.5, cooldown_seconds=0)
        am.add_rule(rule)
        fired = am.evaluate("test_metric", 0.8)
        assert len(fired) == 1
        assert fired[0].rule.name == "test_rule"

    def test_alert_does_not_fire_below_threshold(self):
        from monitoring.alerts import AlertRule, AlertManager
        am = AlertManager()
        rule = AlertRule("test_rule", "test_metric", "gt", 0.5, cooldown_seconds=0)
        am.add_rule(rule)
        fired = am.evaluate("test_metric", 0.3)
        assert len(fired) == 0

    def test_cooldown_suppresses_duplicate(self):
        from monitoring.alerts import AlertRule, AlertManager
        am = AlertManager()
        rule = AlertRule("test_rule", "test_metric", "gt", 0.5, cooldown_seconds=3600)
        am.add_rule(rule)
        am.evaluate("test_metric", 0.8)
        fired = am.evaluate("test_metric", 0.9)
        assert len(fired) == 0


class TestResearchExporter:
    def test_export_creates_directory(self, tmp_path):
        from deployment.research_exporter import ResearchExporter, ResearchConfig
        import json
        import joblib
        from sklearn.linear_model import LogisticRegression

        config_path = tmp_path / "config.json"
        config = {
            "model_name": "test_model",
            "model_type": "logistic_regression",
            "experiment_id": "exp_001",
            "run_id": "run_001",
            "parameters": {"C": 1.0},
            "metrics": {"accuracy": 0.95},
            "feature_version": 1,
            "dataset_version": 1,
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        cfg = ResearchConfig(str(config_path))
        exporter = ResearchExporter(output_dir=str(tmp_path / "exports"))
        model = LogisticRegression()
        import numpy as np
        model.fit(np.random.rand(10, 2), np.random.randint(0, 2, 10))
        export_path = exporter.export(model, cfg)
        assert (Path(export_path) / "model.joblib").exists()
        assert (Path(export_path) / "config.json").exists()
        assert (Path(export_path) / "README.md").exists()

    def test_list_exports_empty(self, tmp_path):
        from deployment.research_exporter import ResearchExporter
        exporter = ResearchExporter(output_dir=str(tmp_path / "exports"))
        exports = exporter.list_exports()
        assert exports == []

    def test_export_config_schema(self):
        from deployment.research_exporter import export_config_schema
        schema = export_config_schema()
        assert "model_name" in schema
        assert "model_type" in schema
