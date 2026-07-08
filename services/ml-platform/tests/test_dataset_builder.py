import numpy as np
import pandas as pd

from datasets.splitter import DatasetSplitter
from datasets.loader import MockDataLoader


class TestDatasetSplitter:
    def test_split_ratios(self):
        rs = np.random.RandomState(42)
        df = pd.DataFrame({
            "feat1": rs.randn(1000),
            "feat2": rs.randn(1000),
            "target": rs.randint(0, 4, 1000),
        })
        splitter = DatasetSplitter(test_size=0.2, val_size=0.1, random_seed=42)
        X_train, X_val, X_test, y_train, y_val, y_test = splitter.split(df, "target")

        total = len(df)
        assert len(X_train) == pytest.approx(total * 0.7, abs=10)
        assert len(X_val) == pytest.approx(total * 0.1, abs=5)
        assert len(X_test) == pytest.approx(total * 0.2, abs=5)

    def test_deterministic(self):
        rs = np.random.RandomState(42)
        df = pd.DataFrame({
            "feat1": rs.randn(500),
            "target": rs.randint(0, 4, 500),
        })
        splitter1 = DatasetSplitter(random_seed=42)
        splitter2 = DatasetSplitter(random_seed=42)
        r1 = splitter1.split(df, "target")
        r2 = splitter2.split(df, "target")
        for a, b in zip(r1, r2):
            assert (a.values == b.values).all()

    def test_params(self):
        splitter = DatasetSplitter(test_size=0.3, val_size=0.1, random_seed=99)
        p = splitter.params
        assert p["test_size"] == 0.3
        assert p["val_size"] == 0.1
        assert p["random_seed"] == 99


class TestMockDataLoader:
    def test_load_returns_dataframe(self):
        loader = MockDataLoader(random_seed=42, n_samples=200)
        df = loader.load()
        assert len(df) == 200
        assert "criticality_score" in df.columns
        assert "region" in df.columns
        assert "throughput_mtpa" in df.columns

    def test_deterministic(self):
        loader1 = MockDataLoader(random_seed=42, n_samples=100)
        loader2 = MockDataLoader(random_seed=42, n_samples=100)
        df1 = loader1.load()
        df2 = loader2.load()
        assert (df1["criticality_score"].values == df2["criticality_score"].values).all()


import pytest
