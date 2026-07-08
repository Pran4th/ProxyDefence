import numpy as np
import pandas as pd
from sklearn.feature_selection import (
    VarianceThreshold,
    SelectKBest,
    mutual_info_classif,
    RFE,
)
from sklearn.ensemble import RandomForestClassifier


class VarianceThresholdSelector:
    def __init__(self, threshold: float = 0.0):
        self._selector = VarianceThreshold(threshold=threshold)
        self._mask: np.ndarray | None = None
        self._scores: np.ndarray | None = None

    def fit(self, X: pd.DataFrame):
        self._selector.fit(X)
        self._mask = self._selector.get_support()
        return self

    @property
    def mask(self) -> np.ndarray:
        return self._mask if self._mask is not None else np.array([])

    @property
    def selected_columns(self) -> list[str]:
        return []


class MutualInfoSelector:
    def __init__(self, k: int = 10, random_seed: int = 42):
        self._k = k
        self._seed = random_seed
        self._scores: np.ndarray | None = None
        self._mask: np.ndarray | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self._scores = mutual_info_classif(X, y, random_state=self._seed)
        top_k = np.argsort(self._scores)[-self._k:]
        self._mask = np.zeros(X.shape[1], dtype=bool)
        self._mask[top_k] = True
        return self

    @property
    def scores(self) -> np.ndarray:
        return self._scores if self._scores is not None else np.array([])

    @property
    def mask(self) -> np.ndarray:
        return self._mask if self._mask is not None else np.array([])


class SelectKBestSelector:
    def __init__(self, k: int = 10, score_func=mutual_info_classif, random_seed: int = 42):
        self._selector = SelectKBest(score_func=score_func, k=k)
        self._k = k

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self._selector.fit(X, y)
        return self

    @property
    def scores(self) -> np.ndarray:
        return self._selector.scores_ if hasattr(self._selector, "scores_") else np.array([])

    @property
    def mask(self) -> np.ndarray:
        return self._selector.get_support() if hasattr(self._selector, "get_support") else np.array([])


class RFESelector:
    def __init__(self, n_features_to_select: int = 10, step: int = 1):
        self._estimator = RandomForestClassifier(random_state=42)
        self._selector = RFE(estimator=self._estimator, n_features_to_select=n_features_to_select, step=step)

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self._selector.fit(X, y)
        return self

    @property
    def mask(self) -> np.ndarray:
        return self._selector.get_support() if hasattr(self._selector, "get_support") else np.array([])

    @property
    def ranking(self) -> np.ndarray:
        return self._selector.ranking_ if hasattr(self._selector, "ranking_") else np.array([])
