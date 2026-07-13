"""Disruption-risk scoring endpoint for the energy-service ml_bridge.

Accepts high-level, human-usable signals (country, media tone, volume) and
builds the exact feature vector the trained GDELT classifier expects — the
caller never needs to know the model's 98+ dummy columns. Feature order comes
from feature_names.json saved at training time.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import asyncpg
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Scoring"])

MODEL_NAME = "gdelt-disruption-risk-classifier"

# Keyed by (model_name, version) -- mirrors inference/predictor.py's generic
# endpoint, which was already production-aware. This endpoint used to load
# a hardcoded data/artifacts/{MODEL_NAME}/v1/model.joblib regardless of which
# row was actually marked stage='production' in ml.model_versions; the DB
# flag was documentation, not a real serving switch. Caching by version means
# a newly-promoted model gets picked up automatically on the next request
# instead of requiring a process restart to clear a stale unconditioned cache.
_cache: dict[str, dict[str, Any]] = {}


async def _load_model(pool: asyncpg.Pool) -> tuple[Any, list[str], asyncpg.Record]:
    mv = await pool.fetchrow(
        "SELECT id, version, file_path FROM ml.model_versions "
        "WHERE name = $1 AND stage = 'production' ORDER BY version DESC LIMIT 1",
        MODEL_NAME,
    )
    if not mv or not mv["file_path"]:
        raise FileNotFoundError(f"no production model_version with a file_path for {MODEL_NAME}")

    cache_key = f"{MODEL_NAME}_{mv['version']}"
    if cache_key not in _cache:
        import joblib
        model_path = Path(mv["file_path"])
        feature_names_path = model_path.parent / "feature_names.json"
        _cache[cache_key] = {
            "model": joblib.load(model_path),
            "feature_names": json.loads(feature_names_path.read_text()),
        }

    cached = _cache[cache_key]
    return cached["model"], cached["feature_names"], mv


class DisruptionScoreRequest(BaseModel):
    country: str = Field("", description="ISO3/CAMEO country code, e.g. RUS, SAU, IRN")
    actor1_country: str = Field("", description="Primary actor country code (optional)")
    actor2_country: str = Field("", description="Secondary actor country code (optional)")
    avg_tone: float = Field(-2.0, description="Average media tone (GDELT scale, negative = hostile)")
    num_mentions: float = Field(10, ge=0)
    num_sources: float = Field(2, ge=0)
    num_articles: float = Field(10, ge=0)
    is_root_event: int = Field(1, ge=0, le=1)
    entity_type: str | None = None
    entity_uuid: str | None = None


def _build_vector(req: DisruptionScoreRequest, feature_names: list[str]) -> pd.DataFrame:
    row = {name: 0.0 for name in feature_names}
    row["avg_tone"] = req.avg_tone
    row["num_mentions"] = req.num_mentions
    row["num_sources"] = req.num_sources
    row["num_articles"] = req.num_articles
    row["is_root_event"] = req.is_root_event

    def set_dummy(prefix: str, code: str):
        code = (code or "").strip().upper()
        col = f"{prefix}_{code}"
        if code and col in row:
            row[col] = 1.0
        elif f"{prefix}_OTHER" in row:
            row[f"{prefix}_OTHER"] = 1.0

    set_dummy("actor1_country", req.actor1_country or req.country)
    set_dummy("actor2_country", req.actor2_country)
    set_dummy("action_geo_country", req.country)

    return pd.DataFrame([row], columns=feature_names)


@router.post("/disruption-score")
async def disruption_score(req: DisruptionScoreRequest) -> dict[str, Any]:
    pool = await get_pool()
    try:
        model, feature_names, mv = await _load_model(pool)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"model artifact not available: {e}")

    X = _build_vector(req, feature_names)
    proba = model.predict_proba(X)[0]
    score = float(proba[1])  # P(escalation)

    await pool.execute(
        "INSERT INTO ml.predictions (model_version_id, model_name, model_version, input_data, "
        "prediction, confidence, probabilities, latency_ms) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
        mv["id"], MODEL_NAME, mv["version"], req.model_dump(),
        score, float(np.max(proba)),
        {"no_escalation": round(float(proba[0]), 4), "escalation": round(score, 4)}, 0.0,
    )

    return {
        "prediction": round(score, 4),
        "confidence": round(float(np.max(proba)), 4),
        "probabilities": {"no_escalation": round(float(proba[0]), 4), "escalation": round(score, 4)},
        "model_name": MODEL_NAME,
        "model_version": mv["version"],
        "feature_version": 1,
    }
