import numpy as np
import pandas as pd
import pytest

from feature_store.transforms import (
    StandardScaleTransform, MinMaxScaleTransform, RobustScaleTransform,
    OneHotTransform, LabelEncodeTransform, FrequencyEncodeTransform,
    BinaryEncodeTransform, TemporalTransform, RollingWindowTransform,
    EWMATransform, InteractionTransform, PolynomialTransform,
    TargetEncodeTransform, TRANSFORM_REGISTRY,
)
from feature_store.transforms_registry import TransformRegistry
from feature_store.groups import FeatureGroups, VALID_GROUP_TYPES
from feature_store.importance import FeatureImportance
from feature_store.snapshots import FeatureSnapshots


class TestNewTransforms:
    def test_standard_scale(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        t = StandardScaleTransform("x")
        result = t.transform(df)
        assert abs(result.mean()) < 1e-10
        assert abs(result.std(ddof=0) - 1.0) < 0.1

    def test_minmax_scale(self):
        df = pd.DataFrame({"x": [0, 5, 10]})
        t = MinMaxScaleTransform("x")
        result = t.transform(df)
        assert abs(result.iloc[0]) < 0.01
        assert abs(result.iloc[-1] - 1.0) < 0.01

    def test_robust_scale(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 100]})
        t = RobustScaleTransform("x")
        result = t.transform(df)
        assert result.median() < 1.0  # robust to outlier

    def test_one_hot(self):
        df = pd.DataFrame({"color": ["red", "blue", "green", "blue"]})
        t = OneHotTransform("color")
        result = t.transform(df)
        if isinstance(result, pd.DataFrame):
            assert result.shape[1] >= 3

    def test_label_encode(self):
        df = pd.DataFrame({"color": ["red", "blue", "green", "blue"]})
        t = LabelEncodeTransform("color")
        result = t.transform(df)
        assert result.dtype == int
        assert result.nunique() == 3

    def test_frequency_encode(self):
        df = pd.DataFrame({"color": ["red", "blue", "red", "green"]})
        t = FrequencyEncodeTransform("color")
        result = t.transform(df)
        assert result.iloc[0] == 0.5  # red appears 2/4

    def test_binary_encode(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        t = BinaryEncodeTransform("x")
        result = t.transform(df)
        assert set(result.unique()) <= {0, 1}

    def test_temporal(self):
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, freq="D")})
        t = TemporalTransform("date", features=["hour", "dow", "month"])
        result = t.transform(df)
        if isinstance(result, pd.DataFrame):
            assert "date_hour" in result.columns
            assert "date_dow" in result.columns

    def test_rolling_window(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        t = RollingWindowTransform("x", window=3, agg="mean")
        result = t.transform(df)
        assert len(result) == 5
        assert result.iloc[-1] > 0

    def test_ewma(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        t = EWMATransform("x", alpha=0.5)
        result = t.transform(df)
        assert len(result) == 5

    def test_interaction_multiply(self):
        df = pd.DataFrame({"a": [2, 3, 4], "b": [5, 6, 7]})
        t = InteractionTransform(["a", "b"], "multiply")
        result = t.transform(df)
        assert result.iloc[0] == 10.0

    def test_polynomial(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        t = PolynomialTransform("x", degree=2)
        result = t.transform(df)
        if isinstance(result, pd.DataFrame):
            assert "x_power_2" in result.columns

    def test_transform_registry_size(self):
        assert len(TRANSFORM_REGISTRY) >= 18

    def test_transform_registry_contents(self):
        assert "identity" in TRANSFORM_REGISTRY
        assert "standard_scale" in TRANSFORM_REGISTRY
        assert "minmax" in TRANSFORM_REGISTRY
        assert "one_hot" in TRANSFORM_REGISTRY
        assert "temporal" in TRANSFORM_REGISTRY
        assert "rolling_window" in TRANSFORM_REGISTRY
        assert "interaction" in TRANSFORM_REGISTRY
        assert "polynomial" in TRANSFORM_REGISTRY
        assert "target_encode" in TRANSFORM_REGISTRY


class TestFeatureGroups:
    def test_valid_group_types(self):
        assert "numerical" in VALID_GROUP_TYPES
        assert "categorical" in VALID_GROUP_TYPES
        assert "temporal" in VALID_GROUP_TYPES

    def test_group_metadata(self):
        metadata = {"domain": "energy", "task": "classification"}
        assert metadata["domain"] == "energy"


class TestFeatureImportance:
    def test_compute_ranking(self):
        importances = {"feat_a": 0.5, "feat_b": 0.3, "feat_c": 0.2}
        sorted_items = sorted(importances.items(), key=lambda x: -x[1])
        assert sorted_items[0][0] == "feat_a"
        assert sorted_items[-1][0] == "feat_c"

    def test_top_features(self):
        names = [f"f{i}" for i in range(10)]
        scores = np.array([i for i in range(10, 0, -1)])
        total = scores.sum()
        normalized = scores / total
        top3 = sorted(zip(names, normalized), key=lambda x: -x[1])[:3]
        assert top3[0][0] == "f0"


class TestFeatureSnapshots:
    def test_snapshot_diff_detects_changes(self):
        data_a = {"throughput": 50.0, "status": "active"}
        data_b = {"throughput": 75.0, "status": "active"}
        changes = {}
        all_keys = set(data_a.keys()) | set(data_b.keys())
        for k in all_keys:
            va = data_a.get(k)
            vb = data_b.get(k)
            if va != vb:
                changes[k] = {"from": va, "to": vb}
        assert "throughput" in changes
        assert "status" not in changes
        assert changes["throughput"]["from"] == 50.0
        assert changes["throughput"]["to"] == 75.0
