import time
from datetime import datetime
from typing import Any

import joblib
import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from db import get_pool
from registry.model_registry import ModelRegistry

logger = get_logger(__name__)


class ModelPredictor:
    _cache: dict[str, dict[str, Any]] = {}

    def __init__(self):
        self._registry = ModelRegistry()

    async def predict(self, features: dict[str, Any],
                      model_name: str,
                      model_version: int | None = None) -> dict[str, Any]:
        start = time.time()

        pool = await get_pool()
        if model_version:
            mv_row = await pool.fetchrow(
                "SELECT * FROM ml.model_versions WHERE name = $1 AND version = $2",
                model_name, model_version,
            )
        else:
            mv_row = await pool.fetchrow(
                "SELECT * FROM ml.model_versions WHERE name = $1 AND stage = 'production' "
                "ORDER BY version DESC LIMIT 1",
                model_name,
            )

        if not mv_row:
            raise ValueError(f"Model '{model_name}' v{model_version or 'production'} not found")

        cache_key = f"{model_name}_{mv_row['version']}"
        if cache_key not in self._cache:
            model_path = mv_row["file_path"]
            if not model_path:
                raise ValueError(f"No file_path for model {cache_key}")
            self._cache[cache_key] = {"model": joblib.load(model_path)}

        model = self._cache[cache_key]["model"]

        input_df = pd.DataFrame([features])
        missing = [k for k in features if k not in input_df.columns]
        pred = model.predict(input_df)
        pred_value = pred[0]

        proba = getattr(model, "predict_proba", None)
        probabilities = None
        confidence = 0.0
        if proba is not None:
            proba_values = model.predict_proba(input_df)[0]
            confidence = round(float(np.max(proba_values)), 4)
            if hasattr(model, "classes_"):
                probabilities = {
                    str(cls): round(float(prob), 4)
                    for cls, prob in zip(model.classes_, proba_values)
                }

        elapsed_ms = round((time.time() - start) * 1000, 2)

        prediction_str = str(pred_value)
        if hasattr(model, "classes_") and isinstance(pred_value, (int, np.integer)):
            if pred_value < len(model.classes_):
                prediction_str = str(model.classes_[int(pred_value)])

        await pool.execute(
            "INSERT INTO ml.predictions (model_version_id, model_name, model_version, input_data, "
            "prediction, confidence, probabilities, latency_ms) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            mv_row["id"], model_name, mv_row["version"],
            features, float(pred[0]) if isinstance(pred[0], (int, float, np.number)) else 0.0,
            confidence, probabilities, elapsed_ms,
        )

        return {
            "prediction": prediction_str,
            "confidence": confidence,
            "probabilities": probabilities,
            "model_name": model_name,
            "model_version": mv_row["version"],
            "model_stage": mv_row["stage"],
            "feature_version": mv_row["feature_version"],
            "prediction_timestamp": datetime.utcnow().isoformat() + "Z",
            "latency_ms": elapsed_ms,
            "input_metadata": {
                "feature_count": len(features),
                "missing_features": missing,
            },
        }
