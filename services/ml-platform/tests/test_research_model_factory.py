from unittest.mock import MagicMock, patch

import pytest

from research.model_factory.factory import ModelFactory, model_factory
from research.model_factory.registry import ModelTypeRegistry
from research.trainers import (
    AnomalyTrainer, ClassificationTrainer, ClusteringTrainer,
    ForecastingTrainer, RankingTrainer, RegressionTrainer,
)


class TestModelTypeRegistry:
    def test_init_contains_categories(self):
        registry = ModelTypeRegistry()
        cats = registry._categories
        assert "classification" in cats
        assert "regression" in cats
        assert "anomaly" in cats
        assert "clustering" in cats
        assert "future_ready" in cats

    def test_pre_registered_classification_types(self):
        registry = ModelTypeRegistry()
        types = registry.list_types(category="classification")
        names = [t["name"] for t in types]
        assert "xgboost" in names
        assert "lightgbm" in names
        assert "random_forest" in names
        assert "extra_trees" in names
        assert "logistic_regression" in names

    def test_pre_registered_regression_types(self):
        registry = ModelTypeRegistry()
        types = registry.list_types(category="regression")
        names = [t["name"] for t in types]
        assert "xgboost" in names
        assert "lightgbm" in names
        assert "random_forest" in names
        assert "extra_trees" in names
        assert "linear_regression" in names
        assert "elasticnet" in names

    def test_pre_registered_anomaly_types(self):
        registry = ModelTypeRegistry()
        types = registry.list_types(category="anomaly")
        names = [t["name"] for t in types]
        assert "isolation_forest" in names
        assert "one_class_svm" in names

    def test_pre_registered_clustering_types(self):
        registry = ModelTypeRegistry()
        types = registry.list_types(category="clustering")
        names = [t["name"] for t in types]
        assert "kmeans" in names
        assert "dbscan" in names

    def test_future_ready_models_registered(self):
        registry = ModelTypeRegistry()
        types = registry.list_types(category="future_ready")
        names = [t["name"] for t in types]
        assert "lstm" in names
        assert "transformer" in names
        assert "graph_neural_network" in names

    def test_future_ready_models_have_none_class(self):
        registry = ModelTypeRegistry()
        for name in ["lstm", "transformer", "graph_neural_network"]:
            cls, params = registry.get(name, category="future_ready")
            assert cls is None, f"{name} should have None class"
            assert len(params) > 0

    def test_register_new_type(self):
        registry = ModelTypeRegistry()
        registry.register("custom_cls", dict, {"a": 1}, category="classification")
        cls, params = registry.get("custom_cls")
        assert cls is dict
        assert params["a"] == 1

    def test_get_unknown_raises(self):
        registry = ModelTypeRegistry()
        with pytest.raises(KeyError, match="Unknown"):
            registry.get("nonexistent")

    def test_get_with_category(self):
        registry = ModelTypeRegistry()
        cls, _ = registry.get("xgboost", category="classification")
        assert cls is not None

    def test_get_with_wrong_category_raises(self):
        registry = ModelTypeRegistry()
        with pytest.raises(KeyError):
            registry.get("xgboost", category="anomaly")

    def test_get_default_params(self):
        registry = ModelTypeRegistry()
        params = registry.get_default_params("logistic_regression")
        assert "max_iter" in params

    def test_get_entries(self):
        registry = ModelTypeRegistry()
        entries = registry.get_entries("xgboost")
        assert len(entries) >= 2

    def test_available_types(self):
        registry = ModelTypeRegistry()
        assert "xgboost" in registry.available_types
        assert "kmeans" in registry.available_types

    def test_contains(self):
        registry = ModelTypeRegistry()
        assert "xgboost" in registry
        assert "nonexistent" not in registry

    def test_list_all_types(self):
        registry = ModelTypeRegistry()
        all_types = registry.list_types()
        assert len(all_types) >= 18

    def test_catboost_optional(self):
        registry = ModelTypeRegistry()
        with patch("research.model_factory.registry._CATBOOST_AVAILABLE", False):
            registry2 = ModelTypeRegistry()
            cls_names = [t["name"] for t in registry2.list_types(category="classification")]
            assert "catboost" not in cls_names

    def test_lstm_has_default_params(self):
        registry = ModelTypeRegistry()
        _, params = registry.get("lstm", category="future_ready")
        assert params["hidden_size"] == 128
        assert params["dropout"] == 0.2


class TestModelFactory:
    def test_create_model_xgboost(self):
        factory = ModelFactory()
        model = factory.create_model("logistic_regression", params={"max_iter": 100})
        assert model is not None

    def test_create_model_future_ready_raises(self):
        factory = ModelFactory()
        with pytest.raises(ValueError, match="future-ready"):
            factory.create_model("lstm")

    def test_create_model_unknown_raises(self):
        factory = ModelFactory()
        with pytest.raises(KeyError):
            factory.create_model("nonexistent")

    def test_create_trainer_classification(self):
        factory = ModelFactory()
        trainer = factory.create_trainer("logistic_regression", params={"max_iter": 100})
        assert isinstance(trainer, ClassificationTrainer)

    def test_create_trainer_anomaly(self):
        factory = ModelFactory()
        trainer = factory.create_trainer("isolation_forest")
        assert isinstance(trainer, AnomalyTrainer)

    def test_create_trainer_clustering(self):
        factory = ModelFactory()
        trainer = factory.create_trainer("kmeans")
        assert isinstance(trainer, ClusteringTrainer)

    def test_create_trainer_regression(self):
        factory = ModelFactory()
        trainer = factory.create_trainer("linear_regression")
        assert isinstance(trainer, RegressionTrainer)

    def test_create_from_config(self):
        factory = ModelFactory()
        config = {
            "experiment": {"name": "test", "type": "classification"},
            "dataset": {"name": "data"},
            "model": {"type": "logistic_regression", "parameters": {"max_iter": 500}},
        }
        model, trainer = factory.create_from_config(config)
        assert model is not None
        assert isinstance(trainer, ClassificationTrainer)

    def test_create_from_config_forecasting(self):
        factory = ModelFactory()
        config = {
            "experiment": {"name": "test", "type": "forecasting"},
            "dataset": {"name": "data"},
            "model": {"type": "xgboost"},
        }
        model, trainer = factory.create_from_config(config)
        assert isinstance(trainer, RegressionTrainer)

    def test_get_supported_types(self):
        factory = ModelFactory()
        types = factory.get_supported_types()
        assert len(types) >= 18

    def test_validate_config_correct(self):
        factory = ModelFactory()
        errors = factory.validate_config("logistic_regression", {"max_iter": 100})
        assert errors == []

    def test_validate_config_wrong_type(self):
        factory = ModelFactory()
        errors = factory.validate_config("logistic_regression", {"max_iter": "not_int"})
        assert len(errors) >= 1

    def test_validate_config_unknown_model(self):
        factory = ModelFactory()
        errors = factory.validate_config("nonexistent", {})
        assert len(errors) >= 1

    def test_detect_category_multi_entry_defaults(self):
        factory = ModelFactory()
        category = factory._detect_category("xgboost")
        assert category in ("classification", "regression")

    def test_resolve_category_from_experiment_type(self):
        factory = ModelFactory()
        assert factory._resolve_category_from_experiment_type("classification") == "classification"
        assert factory._resolve_category_from_experiment_type("regression") == "regression"
        assert factory._resolve_category_from_experiment_type("forecasting") == "regression"
        assert factory._resolve_category_from_experiment_type("anomaly_detection") == "anomaly"
        assert factory._resolve_category_from_experiment_type("clustering") == "clustering"
        assert factory._resolve_category_from_experiment_type("ranking") == "classification"
        assert factory._resolve_category_from_experiment_type("unknown") == "classification"

    def test_model_factory_singleton(self):
        assert isinstance(model_factory, ModelFactory)

    def test_create_trainer_with_config_override(self):
        factory = ModelFactory()
        trainer = factory.create_trainer("logistic_regression", config={"extra": True})
        assert trainer._config.get("extra") is True

    def test_validate_config_contamination(self):
        factory = ModelFactory()
        errors = factory.validate_config("isolation_forest", {"contamination": "bad"})
        assert len(errors) >= 1
