import json
from datetime import datetime, timezone
from typing import Any

import numpy as np

from backend.shared.logging_config import get_logger
from db import get_pool
from monitoring.drift import PSIDetector, KSDetector, DriftResult

logger = get_logger(__name__)


class ModelMonitor:
    def __init__(self, window_size: int = 1000):
        self._window_size = window_size

    async def compute_baseline(self, model_name: str, model_version: int,
                               n_bins: int = 20) -> dict[str, Any]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT input_data, prediction, confidence FROM ml.predictions "
            "WHERE model_name = $1 AND model_version = $2 "
            "ORDER BY created_at ASC LIMIT $3",
            model_name, model_version, self._window_size,
        )
        if not rows:
            logger.warning("no predictions found for baseline", model=model_name, version=model_version)
            return {}

        baselines: dict[str, Any] = {}
        feature_values: dict[str, list[float]] = {}
        predictions: list[float] = []
        confidences: list[float] = []

        for row in rows:
            inp = json.loads(row["input_data"]) if isinstance(row["input_data"], str) else row["input_data"]
            if isinstance(inp, dict):
                for k, v in inp.items():
                    if isinstance(v, (int, float)):
                        feature_values.setdefault(k, []).append(float(v))
            pred = row["prediction"]
            if pred is not None:
                predictions.append(float(pred))
            conf = row["confidence"]
            if conf is not None:
                confidences.append(float(conf))

        for fname, vals in feature_values.items():
            arr = np.array(vals)
            counts, edges = np.histogram(arr, bins=n_bins)
            baselines[fname] = {
                "type": "feature",
                "distribution": {"counts": counts.tolist(), "edges": edges.tolist()},
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "n_samples": len(vals),
            }

        if predictions:
            parr = np.array(predictions)
            pcounts, pedges = np.histogram(parr, bins=n_bins)
            baselines["@prediction"] = {
                "type": "prediction",
                "distribution": {"counts": pcounts.tolist(), "edges": pedges.tolist()},
                "mean": float(np.mean(parr)),
                "std": float(np.std(parr)),
                "n_samples": len(predictions),
            }

        if confidences:
            carr = np.array(confidences)
            ccounts, cedges = np.histogram(carr, bins=n_bins)
            baselines["@confidence"] = {
                "type": "confidence",
                "distribution": {"counts": ccounts.tolist(), "edges": cedges.tolist()},
                "mean": float(np.mean(carr)),
                "std": float(np.std(carr)),
                "n_samples": len(confidences),
            }

        pool = await get_pool()
        for fname, bl in baselines.items():
            await pool.execute(
                "INSERT INTO ml.drift_baselines (model_name, model_version, feature_name, baseline_type, distribution, n_samples) "
                "VALUES ($1, $2, $3, $4, $5, $6) "
                "ON CONFLICT DO NOTHING",
                model_name, model_version, fname, bl["type"],
                json.dumps(bl["distribution"]), bl["n_samples"],
            )

        logger.info("baseline computed for %s v%d (%d features)", model_name, model_version, len(baselines))
        return baselines

    async def detect_drift(self, model_name: str, model_version: int | None = None,
                           threshold_psi: float = 0.2, threshold_ks: float = 0.05,
                           window_size: int | None = None) -> list[DriftResult]:
        ws = window_size or self._window_size
        pool = await get_pool()

        if model_version:
            mv = model_version
        else:
            mv_row = await pool.fetchrow(
                "SELECT version FROM ml.model_versions WHERE name = $1 AND stage = 'production' ORDER BY version DESC LIMIT 1",
                model_name,
            )
            if not mv_row:
                raise ValueError(f"No production model found for '{model_name}'")
            mv = mv_row["version"]

        baseline_rows = await pool.fetch(
            "SELECT * FROM ml.drift_baselines WHERE model_name = $1 AND model_version = $2",
            model_name, mv,
        )
        if not baseline_rows:
            logger.warning("no baseline found for %s v%d, computing now", model_name, mv)
            await self.compute_baseline(model_name, mv)
            baseline_rows = await pool.fetch(
                "SELECT * FROM ml.drift_baselines WHERE model_name = $1 AND model_version = $2",
                model_name, mv,
            )
            if not baseline_rows:
                return []

        recent_rows = await pool.fetch(
            "SELECT input_data, prediction, confidence FROM ml.predictions "
            "WHERE model_name = $1 AND model_version = $2 "
            "ORDER BY created_at DESC LIMIT $3",
            model_name, mv, ws,
        )
        if not recent_rows:
            return []

        psi = PSIDetector()
        ks = KSDetector()
        results: list[DriftResult] = []

        for bl_row in baseline_rows:
            fname = bl_row["feature_name"]
            dist = json.loads(bl_row["distribution"]) if isinstance(bl_row["distribution"], str) else bl_row["distribution"]
            baseline_counts = np.array(dist.get("counts", []))
            baseline_edges = dist.get("edges")
            if len(baseline_counts) == 0 or not baseline_edges:
                continue

            recent_vals: list[float] = []
            for rrow in recent_rows:
                inp = json.loads(rrow["input_data"]) if isinstance(rrow["input_data"], str) else rrow["input_data"]
                if fname.startswith("@"):
                    if fname == "@prediction" and rrow["prediction"] is not None:
                        recent_vals.append(float(rrow["prediction"]))
                    elif fname == "@confidence" and rrow["confidence"] is not None:
                        recent_vals.append(float(rrow["confidence"]))
                elif isinstance(inp, dict):
                    v = inp.get(fname)
                    if isinstance(v, (int, float)):
                        recent_vals.append(float(v))

            if len(recent_vals) < 10:
                continue

            recent_arr = np.array(recent_vals)
            psi_result = psi.detect(
                np.repeat(baseline_edges[:-1], baseline_counts.astype(int)),
                recent_arr, fname, threshold_psi,
            )
            ks_result = ks.detect(
                np.repeat(baseline_edges[:-1], baseline_counts.astype(int)),
                recent_arr, fname, threshold_ks,
            )

            for dr in [psi_result, ks_result]:
                results.append(dr)
                await pool.execute(
                    "INSERT INTO ml.drift_results (model_name, model_version, feature_name, drift_type, "
                    "drift_score, threshold, is_drift, window_size, n_expected, n_actual, details) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
                    model_name, mv, fname, dr.drift_type, dr.drift_score,
                    dr.threshold, dr.is_drift, ws, dr.n_expected, dr.n_actual,
                    json.dumps(dr.details),
                )

        n_drift = sum(1 for r in results if r.is_drift)
        logger.info("drift detection complete for %s v%d: %d/%d drifted",
                     model_name, mv, n_drift, len(results))
        return results

    async def get_recent_predictions(self, model_name: str, model_version: int | None = None,
                                     limit: int = 100) -> list[dict[str, Any]]:
        pool = await get_pool()
        if model_version:
            rows = await pool.fetch(
                "SELECT * FROM ml.predictions WHERE model_name = $1 AND model_version = $2 "
                "ORDER BY created_at DESC LIMIT $3",
                model_name, model_version, limit,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM ml.predictions WHERE model_name = $1 "
                "ORDER BY created_at DESC LIMIT $2",
                model_name, limit,
            )
        return [dict(r) for r in rows]

    async def get_drift_summary(self, model_name: str, model_version: int | None = None,
                                limit: int = 50) -> list[dict[str, Any]]:
        pool = await get_pool()
        if model_version:
            rows = await pool.fetch(
                "SELECT * FROM ml.drift_results WHERE model_name = $1 AND model_version = $2 "
                "ORDER BY detected_at DESC LIMIT $3",
                model_name, model_version, limit,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM ml.drift_results WHERE model_name = $1 "
                "ORDER BY detected_at DESC LIMIT $2",
                model_name, limit,
            )
        return [dict(r) for r in rows]
