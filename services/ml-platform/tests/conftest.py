import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.models import (
    LogisticRegressionWrapper,
    DecisionTreeWrapper,
    RandomForestWrapper,
    XGBoostWrapper,
)

try:
    from training.models import LightGBMWrapper
    _HAS_LGBM = True
except ImportError:
    _HAS_LGBM = False


@pytest.fixture
def sample_df():
    rs = np.random.RandomState(42)
    n = 200
    df = pd.DataFrame({
        "numerical_feat": rs.randn(n),
        "categorical_feat": rs.choice(["a", "b", "c"], n),
        "boolean_feat": rs.choice([True, False], n),
        "region": rs.choice(["middle_east", "europe", "asia"], n),
        "throughput": rs.exponential(50, n),
        "production": rs.exponential(200000, n),
    })
    region_risk = {"middle_east": 3, "europe": 2, "asia": 1}
    score = (
        df["throughput"] / 100 + df["production"] / 500000
        + df["region"].map(region_risk) * 2 + rs.normal(0, 0.5, n)
    )
    df["target"] = pd.qcut(score, 4, labels=[0, 1, 2, 3]).astype(int)
    return df


@pytest.fixture
def X_y(sample_df):
    X = sample_df.select_dtypes(include=[np.number]).drop(columns=["target"])
    y = sample_df["target"]
    return X, y


@pytest.fixture
def all_models():
    models = {
        "logistic_regression": LogisticRegressionWrapper(random_state=42, max_iter=500),
        "decision_tree": DecisionTreeWrapper(random_state=42, max_depth=5),
        "random_forest": RandomForestWrapper(random_state=42, n_estimators=50),
        "xgboost": XGBoostWrapper(random_state=42, n_estimators=50, verbosity=0),
    }
    if _HAS_LGBM:
        models["lightgbm"] = LightGBMWrapper(random_state=42, n_estimators=50, verbose=-1)
    return models
