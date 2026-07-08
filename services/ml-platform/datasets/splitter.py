from __future__ import annotations

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DatasetSplitter:
    def __init__(self, test_size: float = 0.2, val_size: float = 0.1, random_seed: int = 42):
        self._test_size = test_size
        self._val_size = val_size
        self._random_seed = random_seed

    @property
    def params(self) -> dict:
        return {
            "test_size": self._test_size,
            "val_size": self._val_size,
            "random_seed": self._random_seed,
        }

    def split(self, df: pd.DataFrame, target_column: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        rs = np.random.RandomState(self._random_seed)
        indices = df.index.to_numpy()
        n = len(indices)
        shuffled = rs.permutation(indices)

        n_test = int(n * self._test_size)
        n_val = int(n * self._val_size)

        test_idx = shuffled[:n_test]
        val_idx = shuffled[n_test:n_test + n_val]
        train_idx = shuffled[n_test + n_val:]

        train_df = df.loc[train_idx].reset_index(drop=True)
        val_df = df.loc[val_idx].reset_index(drop=True)
        test_df = df.loc[test_idx].reset_index(drop=True)

        X_train = train_df.drop(columns=[target_column])
        y_train = train_df[target_column]
        X_val = val_df.drop(columns=[target_column])
        y_val = val_df[target_column]
        X_test = test_df.drop(columns=[target_column])
        y_test = test_df[target_column]

        return X_train, X_val, X_test, y_train, y_val, y_test
