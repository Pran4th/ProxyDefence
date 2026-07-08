import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


class IQRDetector:
    def __init__(self, k: float = 1.5):
        self._k = k

    def fit_detect(self, df: pd.DataFrame) -> np.ndarray:
        numeric = df.select_dtypes(include=[np.number])
        outlier_mask = np.zeros(len(df), dtype=bool)
        for col in numeric.columns:
            q1 = numeric[col].quantile(0.25)
            q3 = numeric[col].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - self._k * iqr
            upper = q3 + self._k * iqr
            outlier_mask |= (numeric[col] < lower) | (numeric[col] > upper)
        return outlier_mask


class ZScoreDetector:
    def __init__(self, threshold: float = 3.0):
        self._threshold = threshold

    def fit_detect(self, df: pd.DataFrame) -> np.ndarray:
        numeric = df.select_dtypes(include=[np.number])
        outlier_mask = np.zeros(len(df), dtype=bool)
        for col in numeric.columns:
            z = (numeric[col] - numeric[col].mean()) / numeric[col].std().clip(min=1e-10)
            outlier_mask |= z.abs() > self._threshold
        return outlier_mask


class IsolationForestDetector:
    def __init__(self, contamination: float = 0.1, random_seed: int = 42):
        self._model = IsolationForest(
            contamination=contamination, random_state=random_seed, n_jobs=-1,
        )

    def fit_detect(self, df: pd.DataFrame) -> np.ndarray:
        numeric = df.select_dtypes(include=[np.number]).fillna(0)
        preds = self._model.fit_predict(numeric)
        return preds == -1


class CompositeOutlierDetector:
    def __init__(self, detectors: list):
        self._detectors = detectors

    def fit_detect(self, df: pd.DataFrame) -> np.ndarray:
        masks = [d.fit_detect(df) for d in self._detectors]
        return np.any(masks, axis=0)
