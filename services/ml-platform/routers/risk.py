"""Disruption-risk scoring endpoint for the energy-service ml_bridge.

Accepts high-level, human-usable signals (country, media tone, volume) and
builds the exact feature vector the trained GDELT classifier expects — the
caller never needs to know the model's 98 dummy columns. Feature order comes
from feature_names.json saved at training time.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.shared.logging_config import get_logger
from db import get_pool

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Scoring"])

MODEL_NAME = "gdelt-disruption-risk-classifier"
ARTIFACT_DIR = Path("data/artifacts") / MODEL_NAME / "v1"

_cache: dict[str, Any] = {}


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


def _load_model():
    if "model" not in _cache:
        import joblib
        _cache["model"] = joblib.load(ARTIFACT_DIR / "model.joblib")
        _cache["feature_names"] = json.loads((ARTIFACT_DIR / "feature_names.json").read_text())
    return _cache["model"], _cache["feature_names"]


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
    try:
        model, feature_names = _load_model()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"model artifact not available: {e}")

    X = _build_vector(req, feature_names)
    proba = model.predict_proba(X)[0]
    score = float(proba[1])  # P(escalation)

    pool = await get_pool()
    mv = await pool.fetchrow(
        "SELECT id, version FROM ml.model_versions WHERE name=$1 AND stage='production' "
        "ORDER BY version DESC LIMIT 1", MODEL_NAME,
    )
    if mv:
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
        "model_version": mv["version"] if mv else None,
        "feature_version": 1,
    }
