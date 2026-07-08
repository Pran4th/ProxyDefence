import numpy as np
import pandas as pd
import pytest

from pipeline.preprocessing import (
    build_numerical_pipeline,
    build_categorical_pipeline,
    build_boolean_pipeline,
    build_timestamp_pipeline,
)
from pipeline.selection import VarianceThresholdSelector, MutualInfoSelector
from pipeline.detection import IQRDetector, ZScoreDetector, IsolationForestDetector
from pipeline.reporting import ClassBalanceReport, DataQualityReport, FeatureCorrelationReport


class TestPreprocessing:
    def test_numerical_pipeline(self):
        pipe = build_numerical_pipeline(strategy="mean", scaling="standard")
        X = pd.DataFrame({"a": [1.0, 2.0, 3.0, None]})
        result = pipe.fit_transform(X)
        assert result.shape == (4, 1)
        assert not np.any(np.isnan(result))

    def test_categorical_pipeline(self):
        pipe = build_categorical_pipeline()
        X = pd.DataFrame({"cat": ["a", "b", "c", None]})
        result = pipe.fit_transform(X)
        assert result.shape[1] >= 3

    def test_boolean_pipeline(self):
        pipe = build_boolean_pipeline()
        X = pd.DataFrame({"flag": [True, False, True, None]})
        result = pipe.fit_transform(X)
        assert result.shape == (4, 1)

    def test_timestamp_pipeline(self):
        pipe = build_timestamp_pipeline()
        X = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-06-15", "2025-12-31"])})
        result = pipe.fit_transform(X)
        assert "date_year" in result.columns


class TestSelection:
    def test_variance_threshold(self):
        X = pd.DataFrame({"a": [1, 1, 1, 1], "b": [1, 2, 3, 4], "c": [1, 1, 2, 2]})
        selector = VarianceThresholdSelector(threshold=0.0)
        selector.fit(X)
        assert selector.mask is not None

    def test_mutual_info(self):
        rs = np.random.RandomState(42)
        X = pd.DataFrame({"a": rs.randn(100), "b": rs.randn(100), "c": rs.randn(100)})
        y = pd.Series((X["a"] * 2 + rs.randn(100) * 0.1).round().astype(int).clip(0, 3))
        selector = MutualInfoSelector(k=2)
        selector.fit(X, y)
        assert selector.scores.shape[0] == 3
        assert selector.mask.sum() == 2


class TestDetection:
    def test_iqr(self):
        df = pd.DataFrame({"v": [1, 2, 3, 4, 5, 100]})
        detector = IQRDetector(k=1.5)
        mask = detector.fit_detect(df)
        assert mask[5]
        assert not mask[0]

    def test_zscore(self):
        df = pd.DataFrame({"v": [1, 2, 3, 4, 5, 100]})
        detector = ZScoreDetector(threshold=2.0)
        mask = detector.fit_detect(df)
        assert mask[5]
        assert not mask[0]

    def test_isolation_forest(self):
        rs = np.random.RandomState(42)
        df = pd.DataFrame({"a": rs.randn(200), "b": rs.randn(200)})
        detector = IsolationForestDetector(contamination=0.1, random_seed=42)
        mask = detector.fit_detect(df)
        assert mask.sum() == pytest.approx(20, abs=10)


class TestReporting:
    def test_class_balance(self):
        y = pd.Series([0, 0, 0, 1, 1, 2])
        report = ClassBalanceReport(y).generate()
        assert report["num_classes"] == 3
        assert report["class_counts"] == {0: 3, 1: 2, 2: 1}

    def test_data_quality(self):
        df = pd.DataFrame({"a": [1, 2, None], "b": ["x", "y", "z"]})
        report = DataQualityReport(df).generate()
        assert report["num_rows"] == 3
        assert report["columns"]["a"]["missing_count"] == 1

    def test_feature_correlation(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [2, 4, 6], "c": [5, 6, 7]})
        report = FeatureCorrelationReport(df, threshold=0.8).generate()
        assert len(report["highly_correlated_pairs"]) >= 1
