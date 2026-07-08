from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import stats

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DriftResult:
    feature_name: str
    drift_type: str
    drift_score: float
    threshold: float
    is_drift: bool
    n_expected: int = 0
    n_actual: int = 0
    details: dict[str, Any] = field(default_factory=dict)


class PSIDetector:
    def __init__(self, bins: int = 10, epsilon: float = 1e-6):
        self._bins = bins
        self._epsilon = epsilon

    def _histogram(self, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        data = np.asarray(data, dtype=float)
        data = data[~np.isnan(data)]
        if len(data) == 0:
            return np.array([]), np.array([])
        counts, edges = np.histogram(data, bins=self._bins)
        return counts, edges

    def compute_psi(self, expected: np.ndarray, actual: np.ndarray) -> float:
        exp_counts, edges = self._histogram(expected)
        if len(exp_counts) == 0:
            return 0.0
        act_counts, _ = np.histogram(actual, bins=edges)
        exp_pct = exp_counts / exp_counts.sum()
        act_pct = act_counts / act_counts.sum()
        exp_pct = np.clip(exp_pct, self._epsilon, 1.0)
        act_pct = np.clip(act_pct, self._epsilon, 1.0)
        psi = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
        return float(psi)

    def detect(self, expected: np.ndarray, actual: np.ndarray,
               feature_name: str = "", threshold: float = 0.2) -> DriftResult:
        psi = self.compute_psi(expected, actual)
        return DriftResult(
            feature_name=feature_name,
            drift_type="psi",
            drift_score=round(psi, 6),
            threshold=threshold,
            is_drift=psi > threshold,
            n_expected=len(expected),
            n_actual=len(actual),
            details={"bins": self._bins, "psi_interpretation": "low" if psi < 0.1 else "medium" if psi < 0.25 else "high"},
        )


class KSDetector:
    def __init__(self, alternative: str = "two-sided"):
        self._alternative = alternative

    def detect(self, expected: np.ndarray, actual: np.ndarray,
               feature_name: str = "", threshold: float = 0.05) -> DriftResult:
        expected = np.asarray(expected, dtype=float)
        actual = np.asarray(actual, dtype=float)
        expected = expected[~np.isnan(expected)]
        actual = actual[~np.isnan(actual)]
        if len(expected) == 0 or len(actual) == 0:
            return DriftResult(
                feature_name=feature_name, drift_type="ks_test",
                drift_score=1.0, threshold=threshold, is_drift=True,
                n_expected=len(expected), n_actual=len(actual),
                details={"error": "insufficient_data"},
            )
        statistic, p_value = stats.ks_2samp(expected, actual, alternative=self._alternative)
        return DriftResult(
            feature_name=feature_name,
            drift_type="ks_test",
            drift_score=round(float(statistic), 6),
            threshold=threshold,
            is_drift=p_value < threshold,
            n_expected=len(expected),
            n_actual=len(actual),
            details={"p_value": round(float(p_value), 6), "alternative": self._alternative},
        )


class DistributionShiftDetector:
    def __init__(self, psi_threshold: float = 0.2, ks_threshold: float = 0.05):
        self._psi = PSIDetector()
        self._ks = KSDetector()
        self._psi_threshold = psi_threshold
        self._ks_threshold = ks_threshold

    def detect(self, expected: np.ndarray, actual: np.ndarray,
               feature_name: str = "") -> DriftResult:
        psi_result = self._psi.detect(expected, actual, feature_name, self._psi_threshold)
        ks_result = self._ks.detect(expected, actual, feature_name, self._ks_threshold)
        combined_score = max(psi_result.drift_score, ks_result.drift_score)
        is_drift = psi_result.is_drift or ks_result.is_drift
        return DriftResult(
            feature_name=feature_name,
            drift_type="combined",
            drift_score=round(combined_score, 6),
            threshold=min(self._psi_threshold, self._ks_threshold),
            is_drift=is_drift,
            n_expected=len(expected),
            n_actual=len(actual),
            details={
                "psi": {"score": psi_result.drift_score, "is_drift": psi_result.is_drift},
                "ks": {"score": ks_result.drift_score, "is_drift": ks_result.is_drift},
            },
        )
