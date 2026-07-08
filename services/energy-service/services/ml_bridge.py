"""ML Bridge — connects risk engine to ML Platform with rule-based fallback.

The bridge tries the ML Platform first, then falls back to rule-based
scoring if the platform is unavailable or the model is not deployed."""

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger
from models import ASSET_TYPE_BY_TABLE

# Reverse mapping: asset_type -> table_name
TABLE_BY_ASSET_TYPE = {v: k for k, v in ASSET_TYPE_BY_TABLE.items()}

logger = get_logger(__name__)

ML_PLATFORM_URL = "http://ml-platform:8007"
ML_TIMEOUT = 5.0


@dataclass
class PredictionResult:
    score: float
    confidence: float
    model_version: str | None = None
    feature_version: str | None = None
    latency_ms: float = 0.0
    fallback: bool = True
    probabilities: dict[str, float] | None = None


class MLBridge:
    """Interface to the ML Platform with fallback scoring."""

    def __init__(self, pool: asyncpg.Pool | None = None):
        self._pool = pool

    async def _pool_or_default(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def predict_disruption_risk(
        self,
        entity_type: str,
        entity_uuid: str,
        features: dict[str, float] | None = None,
    ) -> PredictionResult:
        t0 = time.time()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=ML_TIMEOUT) as client:
                resp = await client.post(
                    f"{ML_PLATFORM_URL}/api/v1/predict",
                    json={
                        "model_name": "disruption_risk",
                        "features": features or {},
                        "entity_type": entity_type,
                        "entity_uuid": entity_uuid,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    latency = (time.time() - t0) * 1000
                    logger.info("ml_prediction_ok", entity_type=entity_type, latency_ms=round(latency, 1))
                    return PredictionResult(
                        score=float(data.get("prediction", 0.5)),
                        confidence=float(data.get("confidence", 0.8)),
                        model_version=data.get("model_version"),
                        feature_version=data.get("feature_version"),
                        latency_ms=latency,
                        fallback=False,
                        probabilities=data.get("probabilities"),
                    )
        except Exception as exc:
            logger.warning("ml_platform_unavailable, using fallback", error=str(exc))

        latency = (time.time() - t0) * 1000
        return await self._fallback_score(entity_type, features, latency)

    async def _fallback_score(
        self,
        entity_type: str,
        features: dict[str, float] | None,
        latency_ms: float,
    ) -> PredictionResult:
        features = features or {}

        score = 0.5

        if features:
            geopolitics = features.get("geopolitical_tension", 0.0)
            conflict = features.get("regional_conflict", 0.0)
            sanctions = features.get("sanctions_impact", 0.0)
            congestion = features.get("port_congestion", 0.0)
            volatility = features.get("price_volatility", 0.0)

            weights = {
                "geopolitical_tension": 0.20,
                "regional_conflict": 0.25,
                "sanctions_impact": 0.15,
                "port_congestion": 0.15,
                "price_volatility": 0.10,
            }

            weighted = (
                geopolitics * weights["geopolitical_tension"]
                + conflict * weights["regional_conflict"]
                + sanctions * weights["sanctions_impact"]
                + congestion * weights["port_congestion"]
                + volatility * weights["price_volatility"]
            )

            score = min(1.0, max(0.05, weighted * 1.2))

        confidence = 0.6

        logger.info("fallback_score_computed", entity_type=entity_type, score=round(score, 4))

        return PredictionResult(
            score=score,
            confidence=confidence,
            latency_ms=latency_ms,
            fallback=True,
        )

    async def score_from_recent_data(self, entity_type: str, entity_uuid: str) -> PredictionResult:
        pool = await self._pool_or_default()

        features: dict[str, float] = {}

        if entity_type == "import_corridors":
            signals = await pool.fetch(
                """SELECT severity, confidence, risk_dimension
                   FROM energy.disruption_signals
                   WHERE (affected_entity_uuid = $1::uuid OR affected_entity_type = $2)
                   AND expires_at > NOW()""",
                entity_uuid, entity_type,
            )
            for s in signals:
                dim = s["risk_dimension"]
                severity_map = {"low": 0.1, "moderate": 0.25, "elevated": 0.45, "high": 0.7, "critical": 0.95}
                base = severity_map.get(s["severity"], 0.3)
                key = f"{dim}_tension" if dim != "economic" else "price_volatility"
                features[key] = max(features.get(key, 0), base * s["confidence"])

        if entity_type in ("ports", "shipping_routes"):
            congested = await pool.fetchrow(
                """SELECT congestion_pct FROM energy.port_congestion
                   WHERE recorded_at > NOW() - INTERVAL '4 hours'
                   ORDER BY recorded_at DESC LIMIT 1"""
            )
            if congested:
                features["port_congestion"] = congested["congestion_pct"] / 100.0

        return await self.predict_disruption_risk(entity_type, entity_uuid, features)


class RiskPropagator:
    """Propagates risk scores through the knowledge graph along relationships."""

    PROPAGATION_FACTOR = 0.3

    def __init__(self, pool: asyncpg.Pool | None = None):
        self._pool = pool

    async def _pool_or_default(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def propagate(self, source_uuid: str, source_type: str, risk_score: float):
        pool = await self._pool_or_default()

        # Convert table name to asset type (e.g. import_corridors -> import_corridor)
        asset_type = ASSET_TYPE_BY_TABLE.get(source_type, source_type.rstrip("s"))

        # Look up the numeric ID from the UUID
        entity_row = await pool.fetchrow(
            f"SELECT id FROM energy.{source_type} WHERE uuid = $1::uuid AND is_deleted = false",
            source_uuid,
        )
        if not entity_row:
            logger.warning("propagate_source_not_found", uuid=source_uuid, type=source_type)
            return 0

        source_id = entity_row["id"]

        related = await pool.fetch(
            """SELECT source_entity_type, source_entity_id, target_entity_type, target_entity_id
               FROM energy.entity_relationships
               WHERE (source_entity_type::text = $1 AND source_entity_id = $2)
                  OR (target_entity_type::text = $1 AND target_entity_id = $2)""",
            asset_type, source_id,
        )

        propagated = 0
        from services.risk_engine import RiskScoringEngine
        engine = RiskScoringEngine(pool)

        for rel in related:
            if rel["source_entity_type"] == asset_type and rel["source_entity_id"] == source_id:
                target_asset_type = rel["target_entity_type"]
                target_id = rel["target_entity_id"]
            else:
                target_asset_type = rel["source_entity_type"]
                target_id = rel["source_entity_id"]

            # Convert asset type back to table name
            target_table = TABLE_BY_ASSET_TYPE.get(target_asset_type, target_asset_type + "s")

            entity_row = await pool.fetchrow(
                f"SELECT uuid FROM energy.{target_table} WHERE id = $1 AND is_deleted = false",
                target_id,
            )
            if not entity_row:
                continue

            propagated_score = min(1.0, risk_score * self.PROPAGATION_FACTOR)
            await engine.persist_score(
                entity_uuid=str(entity_row["uuid"]),
                entity_type=target_asset_type,
                dimension="overall",
                score=propagated_score,
                confidence=0.4,
                breakdown={"propagated_from": source_uuid, "original_score": risk_score},
            )
            propagated += 1

        logger.info("risk_propagated", source=source_uuid, targets=propagated)
        return propagated
