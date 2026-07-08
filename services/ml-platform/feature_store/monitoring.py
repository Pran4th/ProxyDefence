from typing import Any

import numpy as np

from backend.shared.logging_config import get_logger
from db import get_pool
from monitoring.drift import PSIDetector, KSDetector, DriftResult

logger = get_logger(__name__)


class FeatureMonitor:
    def __init__(self, psi_threshold: float = 0.2, ks_threshold: float = 0.05):
        self._psi = PSIDetector()
        self._ks = KSDetector()
        self._psi_threshold = psi_threshold
        self._ks_threshold = ks_threshold

    async def check_feature_drift(self, feature_name: str, expected_values: np.ndarray,
                                    actual_values: np.ndarray) -> DriftResult:
        combined = PSIDetector()
        psi_result = combined.compute_psi(expected_values, actual_values)
        ks_result = self._ks.detect(expected_values, actual_values, feature_name, self._ks_threshold)
        is_drift = psi_result > self._psi_threshold or ks_result.is_drift
        return DriftResult(
            feature_name=feature_name,
            drift_type="feature_monitor",
            drift_score=round(float(psi_result), 6),
            threshold=self._psi_threshold,
            is_drift=is_drift,
            n_expected=len(expected_values),
            n_actual=len(actual_values),
            details={"psi": round(psi_result, 6), "ks_statistic": ks_result.drift_score},
        )

    async def get_feature_stats(self, feature_name: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.drift_baselines WHERE feature_name = $1 ORDER BY computed_at DESC LIMIT 1",
            feature_name,
        )
        return dict(row) if row else None

    async def list_monitored_features(self, limit: int = 100) -> list[dict[str, Any]]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT DISTINCT feature_name, baseline_type, COUNT(*) as check_count "
            "FROM ml.drift_baselines GROUP BY feature_name, baseline_type ORDER BY feature_name LIMIT $1",
            limit,
        )
        return [dict(r) for r in rows]
