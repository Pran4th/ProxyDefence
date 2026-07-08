from __future__ import annotations

from enum import Enum
from typing import Any

import numpy as np
from sklearn.model_selection import (
    GroupKFold,
    KFold,
    RepeatedKFold,
    StratifiedKFold,
    TimeSeriesSplit,
    train_test_split as sklearn_train_test_split,
)


class CVStrategy(Enum):
    HOLDOUT = "holdout"
    KFOLD = "kfold"
    STRATIFIED_KFOLD = "stratified_kfold"
    TIMESERIES = "timeseries"
    GROUP_KFOLD = "group_kfold"
    REPEATED_KFOLD = "repeated_kfold"
    NESTED = "nested"


class _HoldoutSplitter:
    def __init__(self, test_size: float = 0.2, random_state: int = 42, shuffle: bool = True, stratify: bool = False):
        self.test_size = test_size
        self.random_state = random_state
        self.shuffle = shuffle
        self.stratify = stratify

    def split(self, X, y=None, groups=None):
        n = X.shape[0] if hasattr(X, "shape") else len(X)
        indices = np.arange(n)
        stratify_arg = y if self.stratify else None
        train_idx, test_idx = sklearn_train_test_split(
            indices,
            test_size=self.test_size,
            random_state=self.random_state,
            shuffle=self.shuffle,
            stratify=stratify_arg,
        )
        yield train_idx, test_idx

    def get_n_splits(self, X=None, y=None, groups=None):
        return 1


class _NestedSplitter:
    def __init__(self, outer_cv, inner_cv):
        self.outer_cv = outer_cv
        self.inner_cv = inner_cv

    def split(self, X, y=None, groups=None):
        return self.outer_cv.split(X, y, groups)

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.outer_cv.get_n_splits(X, y, groups)


def create_cv_splitter(strategy: CVStrategy, params: dict[str, Any] | None = None) -> Any:
    _params = params or {}
    if strategy == CVStrategy.HOLDOUT:
        return _HoldoutSplitter(
            test_size=_params.get("test_size", 0.2),
            random_state=_params.get("random_state", 42),
            shuffle=_params.get("shuffle", True),
            stratify=_params.get("stratify", False),
        )
    elif strategy == CVStrategy.KFOLD:
        return KFold(
            n_splits=_params.get("n_splits", 5),
            shuffle=_params.get("shuffle", True),
            random_state=_params.get("random_state", 42),
        )
    elif strategy == CVStrategy.STRATIFIED_KFOLD:
        return StratifiedKFold(
            n_splits=_params.get("n_splits", 5),
            shuffle=_params.get("shuffle", True),
            random_state=_params.get("random_state", 42),
        )
    elif strategy == CVStrategy.TIMESERIES:
        return TimeSeriesSplit(
            n_splits=_params.get("n_splits", 5),
            gap=_params.get("gap", 0),
            max_train_size=_params.get("max_train_size"),
            test_size=_params.get("test_size"),
        )
    elif strategy == CVStrategy.GROUP_KFOLD:
        return GroupKFold(
            n_splits=_params.get("n_splits", 5),
        )
    elif strategy == CVStrategy.REPEATED_KFOLD:
        return RepeatedKFold(
            n_splits=_params.get("n_splits", 5),
            n_repeats=_params.get("n_repeats", 10),
            random_state=_params.get("random_state", 42),
        )
    elif strategy == CVStrategy.NESTED:
        outer_cv = create_cv_splitter(CVStrategy.KFOLD, _params.get("outer_params", {"n_splits": 5}))
        inner_cv = create_cv_splitter(CVStrategy.KFOLD, _params.get("inner_params", {"n_splits": 3}))
        return _NestedSplitter(outer_cv, inner_cv)
    else:
        raise ValueError(f"Unknown CV strategy: {strategy}")
