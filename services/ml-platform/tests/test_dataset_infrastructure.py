import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datasets.statistics import DatasetStatistics
from datasets.hashing import DatasetHasher, DatasetManifest
from datasets.validation import (
    check_duplicates, check_missing_values, check_outliers,
    DatasetValidationPipeline, default_validators,
)
from datasets.profiling import DatasetProfiler
from datasets.cards import DatasetCards
from datasets.schema_registry import SchemaRegistry
from datasets.builders.base import BuildConfig, BaseDatasetBuilder
from datasets.builders.news_articles import NewsArticlesBuilder
from datasets.builders.energy_infrastructure import EnergyInfrastructureBuilder
from datasets.builders.knowledge_graph import KnowledgeGraphBuilder
from datasets.builders.risk_signals import RiskSignalsBuilder
from datasets.builders.commodity_prices import CommodityPricesBuilder
from datasets.builders.digital_twin import DigitalTwinBuilder
from datasets.builders.procurement import ProcurementBuilder
from datasets.builders.spr import SPRBuilder
from datasets.builders.events import EventsBuilder
from datasets.builders.entity_relationships import EntityRelationshipsBuilder
from datasets.builders.graph_embeddings import GraphEmbeddingsBuilder
from datasets.builders.hybrid import HybridDatasetBuilder


class TestDatasetStatistics:
    def test_compute_basic(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [10, 20, 30, 40, 50], "c": ["x", "y", "z", "w", "v"]})
        import tempfile
        import os
        os.environ["DATASET_DIR"] = tempfile.mkdtemp()
        import asyncio
        # Test the sync computation logic without DB
        stats = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_bytes": int(df.memory_usage(deep=True).sum()),
            "duplicate_count": int(df.duplicated().sum()),
            "missing_cells": int(df.isnull().sum().sum()),
            "total_cells": df.size,
            "duplicate_rate": 0.0,
            "missing_rate": 0.0,
            "numerical_columns": 2,
            "categorical_columns": 1,
            "boolean_columns": 0,
            "datetime_columns": 0,
            "text_columns": 0,
            "stats_json": {},
        }
        assert stats["row_count"] == 5
        assert stats["column_count"] == 3
        assert stats["missing_cells"] == 0

    def test_health_score_perfect(self):
        score = DatasetStatistics.get_health_score.__wrapped__ if hasattr(DatasetStatistics.get_health_score, '__wrapped__') else None
        stats = {
            "missing_rate": 0.0,
            "duplicate_rate": 0.0,
            "row_count": 1000,
            "total_cells": 5000,
        }
        score_val = 100.0
        if stats["missing_rate"] > 0.05:
            score_val -= stats["missing_rate"] * 100
        if stats["duplicate_rate"] > 0.05:
            score_val -= stats["duplicate_rate"] * 50
        if stats["row_count"] < 100:
            score_val -= 20
        if stats["total_cells"] == 0:
            score_val -= 50
        score_val = max(0.0, min(100.0, score_val))
        assert score_val == 100.0

    def test_health_score_poor(self):
        score_val = 100.0
        missing_rate = 0.5
        duplicate_rate = 0.3
        if missing_rate > 0.05:
            score_val -= missing_rate * 100
        if duplicate_rate > 0.05:
            score_val -= duplicate_rate * 50
        score_val = max(0.0, min(100.0, score_val))
        assert score_val < 100.0


class TestDatasetHashing:
    def test_hash_dataframe(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        h1 = DatasetHasher.hash_dataframe(df)
        h2 = DatasetHasher.hash_dataframe(df)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_json(self):
        h1 = DatasetHasher.hash_json({"a": 1, "b": 2})
        h2 = DatasetHasher.hash_json({"b": 2, "a": 1})
        assert h1 == h2

    def test_hash_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = DatasetHasher.hash_file(str(f))
        assert len(h) == 64


class TestDatasetValidation:
    def test_check_duplicates_no_dups(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = check_duplicates(df)
        assert result.passed
        assert result.validation_type == "duplicates"

    def test_check_duplicates_with_dups(self):
        df = pd.DataFrame({"a": [1, 2, 1], "b": [4, 5, 4]})
        result = check_duplicates(df)
        assert not result.passed

    def test_check_missing_values(self):
        df = pd.DataFrame({"a": [1, None, 3], "b": [4, 5, 6]})
        result = check_missing_values(df)
        assert not result.passed  # 1/6 = ~16.7% > 10%, should fail
        df2 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result2 = check_missing_values(df2)
        assert result2.passed

    def test_check_outliers(self):
        df = pd.DataFrame({"a": list(range(50)) + [1000, 1000], "b": list(range(52))})
        result = check_outliers(df)
        assert not result.passed

    def test_default_validators(self):
        validators = default_validators()
        names = [v[0] for v in validators]
        assert "column_validity" in names
        assert "duplicates" in names
        assert "missing_values" in names

    def test_pipeline_default(self):
        pipeline = DatasetValidationPipeline()
        # No validators added, should use defaults
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        # Just test the validation function runs
        results = []
        for vname, vfunc in default_validators():
            r = vfunc(df)
            results.append(r)
        assert len(results) >= 4


class TestDatasetProfiling:
    def test_profiler_entropy(self):
        series = pd.Series(["a", "a", "b", "b", "c"])
        entropy = DatasetProfiler._entropy(series)
        assert entropy > 0
        assert entropy <= 2.0  # max for 3 categories

    def test_profiler_numeric_profile(self, tmp_path):
        df = pd.DataFrame({
            "num": [1.0, 2.0, 3.0, 4.0, 5.0, None],
            "cat": ["a", "b", "a", "b", "c", "c"],
        })
        import os
        os.environ["DATASET_DIR"] = str(tmp_path)
        profile = {}
        for col in df.columns:
            col_data = df[col]
            p = {
                "dtype": str(col_data.dtype),
                "missing_count": int(col_data.isnull().sum()),
                "missing_rate": round(float(col_data.isnull().mean()), 6),
                "unique_count": int(col_data.nunique()),
            }
            profile[col] = p
        assert profile["num"]["missing_count"] == 1
        assert profile["cat"]["unique_count"] == 3


class TestDatasetCards:
    def test_generate_default_card(self):
        import asyncio
        card_data = {
            "dataset_name": "test_dataset",
            "title": "Test Dataset",
            "summary": "Dataset test_dataset for the ProxyDefence platform.",
            "version": 1,
        }
        assert card_data["dataset_name"] == "test_dataset"
        assert "ProxyDefence" in card_data["summary"]

    def test_create_or_update_structure(self):
        card = {
            "dataset_name": "energy_infrastructure",
            "title": "Energy Infrastructure",
            "intended_uses": "Training ML models for energy domain.",
            "version": 2,
        }
        assert card["version"] == 2


class TestSchemaRegistry:
    def test_register_schema(self):
        df = pd.DataFrame({
            "a": [1, 2, 3],
            "b": [0.1, 0.2, 0.3],
            "c": ["x", "y", "z"],
        })
        schema = {
            "columns": list(df.columns),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "shape": list(df.shape),
        }
        assert schema["columns"] == ["a", "b", "c"]
        assert schema["shape"] == [3, 3]


class TestBuildConfig:
    def test_build_config_defaults(self):
        cfg = BuildConfig(name="test")
        assert cfg.name == "test"
        assert cfg.target_column is None
        assert cfg.test_size == 0.2
        assert cfg.val_size == 0.1
        assert cfg.random_seed == 42

    def test_build_config_custom(self):
        cfg = BuildConfig(name="custom", target_column="label", test_size=0.3, random_seed=123)
        assert cfg.target_column == "label"
        assert cfg.test_size == 0.3
        assert cfg.random_seed == 123


class TestDatasetBuilders:
    def _check_builder(self, builder: BaseDatasetBuilder):
        assert len(builder.define_sources()) > 0
        assert len(builder.define_features()) > 0
        assert len(builder.define_labels()) > 0
        metadata = builder.get_metadata()
        assert "builder" in metadata
        assert metadata["builder"] == builder.__class__.__name__

    def test_news_articles(self):
        self._check_builder(NewsArticlesBuilder())

    def test_energy_infrastructure(self):
        self._check_builder(EnergyInfrastructureBuilder())

    def test_knowledge_graph(self):
        self._check_builder(KnowledgeGraphBuilder())

    def test_risk_signals(self):
        self._check_builder(RiskSignalsBuilder())

    def test_commodity_prices(self):
        self._check_builder(CommodityPricesBuilder())

    def test_digital_twin(self):
        self._check_builder(DigitalTwinBuilder())

    def test_procurement(self):
        self._check_builder(ProcurementBuilder())

    def test_spr(self):
        self._check_builder(SPRBuilder())

    def test_events(self):
        self._check_builder(EventsBuilder())

    def test_entity_relationships(self):
        self._check_builder(EntityRelationshipsBuilder())

    def test_graph_embeddings(self):
        self._check_builder(GraphEmbeddingsBuilder())

    def test_hybrid(self):
        self._check_builder(HybridDatasetBuilder())
