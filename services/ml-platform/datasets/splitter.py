from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split


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

    def split(self, df: pd.DataFrame, target_column: str):
        feature_cols = [c for c in df.columns if c != target_column]
        X = df[feature_cols]
        y = df[target_column] if target_column in df.columns else pd.Series(dtype=object)

        X_rest, X_test, y_rest, y_test = train_test_split(
            X, y, test_size=self._test_size, random_state=self._random_seed,
        )

        rest_fraction = 1.0 - self._test_size
        val_fraction_of_rest = min(self._val_size / rest_fraction, 1.0) if rest_fraction > 0 else 0.0

        if val_fraction_of_rest > 0:
            X_train, X_val, y_train, y_val = train_test_split(
                X_rest, y_rest, test_size=val_fraction_of_rest, random_state=self._random_seed,
            )
        else:
            X_train, y_train = X_rest, y_rest
            X_val, y_val = X_rest.iloc[0:0], y_rest.iloc[0:0]

        return X_train, X_val, X_test, y_train, y_val, y_test
