"""Geopolitical Risk Intelligence Agent — core scoring, detection, and escalation."""

import json
import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from db import get_pool
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


def _ensure_dict(val: Any) -> dict:
    """asyncpg doesn't auto-decode jsonb columns to Python objects on this
    pool, so a jsonb column comes back as a raw JSON string unless parsed
    here (same pattern as procurement/spr_engine.py::_ensure_dict)."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


# ── Data types ──────────────────────────────────────────────────────────────

RISK_DIMENSIONS = ["geopolitical", "operational", "economic", "environmental"]
RISK_LEVELS = ["low", "moderate", "elevated", "high", "critical"]


@dataclass
class RiskFactor:
    name: str
    dimension: str
    weight: float = 1.0
    description: str = ""
    source: str = ""
    ttl_hours: int = 48


@dataclass
class RiskScore:
    entity_uuid: str
    entity_type: str
    dimension: str
    score: float  # 0.0 – 1.0
    confidence: float
    factors: list[dict] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)
    expires_at: datetime | None = None


@dataclass
class DisruptionSignal:
    title: str
    description: str
    source: str
    severity: str  # low / moderate / elevated / high / critical
    affected_entity_type: str | None = None
    affected_entity_uuid: str | None = None
    risk_dimension: str = "operational"
    affected_commodities: list[str] = field(default_factory=list)
    affected_regions: list[str] = field(default_factory=list)
    confidence: float = 0.7
    evidence_urls: list[str] = field(default_factory=list)
    ttl_hours: int = 72


# ── Built-in risk factors ───────────────────────────────────────────────────

RISK_FACTORS: list[RiskFactor] = [
    RiskFactor("chokepoint_blockage", "geopolitical", 1.5, "Strait of Hormuz / Malacca closure risk"),
    RiskFactor("sanctions_impact", "geopolitical", 1.3, "Active or pending sanctions on supplier country"),
    RiskFactor("regional_conflict", "geopolitical", 1.4, "Military conflict or civil unrest in producing region"),
    RiskFactor("port_disruption", "operational", 1.2, "Port closure, congestion, or reduced throughput"),
    RiskFactor("pipeline_outage", "operational", 1.3, "Pipeline damage, maintenance, or sabotage"),
    RiskFactor("refinery_maintenance", "operational", 1.1, "Planned or unplanned refinery downtime"),
    RiskFactor("production_cut", "operational", 1.2, "OPEC+ or national production reduction"),
    RiskFactor("price_volatility", "economic", 1.0, "Abnormal commodity price movement"),
    RiskFactor("supply_shortage", "economic", 1.3, "Observed or forecast supply deficit"),
    RiskFactor("freight_spike", "economic", 1.1, "Sharp increase in tanker freight rates"),
    RiskFactor("extreme_weather", "environmental", 1.2, "Hurricane, typhoon, or storm affecting operations"),
    RiskFactor("geological_hazard", "environmental", 1.0, "Earthquake, tsunami, or volcanic activity"),
    RiskFactor("cyber_attack", "operational", 1.4, "Cyber intrusion affecting ICS or SCADA systems"),
    RiskFactor("regulatory_change", "geopolitical", 1.1, "New tariffs, embargoes, or environmental regulations"),
    RiskFactor("tanker_shortage", "economic", 1.2, "Insufficient available tanker capacity"),
]


# ── Scoring engine ──────────────────────────────────────────────────────────


class RiskScoringEngine:
    """Computes and persists risk scores for energy entities."""

    def __init__(self, pool: asyncpg.Pool | None = None):
        self._pool = pool

    async def _pool_or_default(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def score_entity(
        self,
        entity_uuid: str,
        entity_type: str,
        dimension: str = "overall",
    ) -> dict[str, Any]:
        pool = await self._pool_or_default()

        active_signals = await pool.fetch(
            """SELECT * FROM energy.disruption_signals
               WHERE (affected_entity_uuid = $1 OR $1 IS NULL)
               AND expires_at > NOW()
               AND severity IN ('elevated','high','critical')""",
            entity_uuid if dimension == "overall" else None,
        )

        risk_factors = await pool.fetch(
            """SELECT * FROM energy.risk_factors
               WHERE is_active = true"""
        )

        if entity_uuid == "*" or dimension == "overall":
            scores = {}
            for dim in RISK_DIMENSIONS:
                dim_signals = [s for s in active_signals if s["risk_dimension"] == dim]
                scores[dim] = self._compute_dimension_score(dim_signals, risk_factors)
            scores["overall"] = max(scores.values()) if scores else 0.5
            return await self._blend_with_ml(scores, entity_uuid, entity_type, active_signals)

        dim_signals = [s for s in active_signals if s["risk_dimension"] == dimension]
        score = self._compute_dimension_score(dim_signals, risk_factors)
        return {dimension: score, "overall": score}

    ML_BLEND_WEIGHT = 0.4  # trained-model share of the blended overall score

    async def _blend_with_ml(
        self,
        scores: dict[str, Any],
        entity_uuid: str,
        entity_type: str,
        active_signals: list[asyncpg.Record],
    ) -> dict[str, Any]:
        """Blends the formula-based overall score with the trained GDELT
        disruption classifier via MLBridge. Falls back silently to the
        formula score if the ML Platform is unreachable."""
        try:
            from services.ml_bridge import MLBridge

            tension = float(scores.get("geopolitical") or 0.0)
            bridge = MLBridge(self._pool)
            result = await bridge.predict_disruption_risk(
                entity_type, entity_uuid,
                features={
                    "geopolitical_tension": tension,
                    "regional_conflict": float(scores.get("operational") or 0.0),
                },
            )
            if not result.fallback:
                formula_overall = scores["overall"]
                scores["overall"] = round(
                    (1 - self.ML_BLEND_WEIGHT) * formula_overall
                    + self.ML_BLEND_WEIGHT * result.score, 4,
                )
                scores["ml"] = {
                    "score": round(result.score, 4),
                    "formula_score": round(formula_overall, 4),
                    "blend_weight": self.ML_BLEND_WEIGHT,
                    "model_version": result.model_version,
                    "latency_ms": round(result.latency_ms, 1),
                }
        except Exception as exc:
            logger.warning("ml_blend_skipped", error=str(exc))
        return scores

    def _compute_dimension_score(
        self,
        active_signals: list[asyncpg.Record],
        risk_factors: list[asyncpg.Record],
    ) -> float:
        if not active_signals and not risk_factors:
            return 0.05

        signal_scores = []
        for s in active_signals:
            severity_map = {"low": 0.1, "moderate": 0.25, "elevated": 0.45, "high": 0.7, "critical": 0.95}
            base = severity_map.get(s["severity"], 0.3)
            confidence = s.get("confidence", 0.7)
            signal_scores.append(base * confidence)

        factor_scores = []
        for f in risk_factors:
            rf = next((x for x in RISK_FACTORS if x.name == f.get("name")), None)
            if rf:
                factor_scores.append(rf.weight * 0.1)

        all_scores = signal_scores + factor_scores
        if not all_scores:
            return 0.05

        weighted_sum = sum(all_scores)
        count = len(all_scores)

        raw = weighted_sum / (count * 0.95) if count > 0 else 0.05
        return min(1.0, max(0.0, raw * 1.3))

    async def persist_score(
        self,
        entity_uuid: str,
        entity_type: str,
        dimension: str,
        score: float,
        confidence: float = 0.7,
        breakdown: dict | None = None,
    ) -> int:
        pool = await self._pool_or_default()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        row = await pool.fetchrow(
            """INSERT INTO energy.risk_scores
               (uuid, entity_uuid, entity_type, dimension, score, confidence, breakdown, expires_at)
               VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8)
               RETURNING id""",
            str(uuid.uuid4()),
            entity_uuid,
            entity_type,
            dimension,
            round(score, 4),
            round(confidence, 4),
            json.dumps(breakdown or {}),
            expires_at,
        )
        return row["id"]

    async def score_and_persist(self, entity_uuid: str, entity_type: str) -> dict[str, Any]:
        scores = await self.score_entity(entity_uuid, entity_type)
        for dim, val in scores.items():
            if not isinstance(val, (int, float)):
                continue  # e.g. the "ml" blend-metadata block _blend_with_ml() adds, not a score
            await self.persist_score(entity_uuid, entity_type, dim, val)
        return scores


# ── Signal detection ────────────────────────────────────────────────────────


class SignalDetector:
    """Detects disruption signals from data streams and external ingestors."""

    def __init__(self, pool: asyncpg.Pool | None = None):
        self._pool = pool

    async def _pool_or_default(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def ingest_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        pool = await self._pool_or_default()

        required = {"title", "description", "source", "severity"}
        missing = required - set(signal)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        severity = signal.get("severity", "moderate")
        if severity not in RISK_LEVELS:
            raise ValueError(f"Invalid severity: {severity}")

        asset_type = signal.get("affected_entity_type")
        asset_uuid = signal.get("affected_entity_uuid")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=signal.get("ttl_hours", 72))

        signal_uuid = str(uuid.uuid4())
        await pool.execute(
            """INSERT INTO energy.disruption_signals
               (uuid, title, description, source, severity, risk_dimension,
                affected_entity_type, affected_entity_uuid,
                affected_commodities, affected_regions,
                confidence, evidence_urls, expires_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8::uuid,$9,$10,$11,$12,$13)""",
            signal_uuid,
            signal["title"],
            signal["description"],
            signal["source"],
            severity,
            signal.get("risk_dimension", "operational"),
            asset_type,
            asset_uuid,
            signal.get("affected_commodities", []),
            signal.get("affected_regions", []),
            float(signal.get("confidence", 0.7)),
            signal.get("evidence_urls", []),
            expires_at,
        )

        row = await pool.fetchrow(
            "SELECT * FROM energy.disruption_signals WHERE uuid = $1",
            signal_uuid,
        )

        await self._auto_score_entity(asset_type, asset_uuid, severity, signal.get("risk_dimension", "operational"))

        return dict(row)

    async def _auto_score_entity(
        self,
        entity_type: str | None,
        entity_uuid: str | None,
        severity: str,
        dimension: str,
    ) -> None:
        if not entity_type or not entity_uuid:
            return
        engine = RiskScoringEngine(self._pool)
        await engine.score_and_persist(entity_uuid, entity_type)

    async def evaluate_scenario(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Evaluates a what-if scenario against the real current risk picture:
        baseline dimension scores come from actual active disruption_signals
        and risk_factors (same query RiskScoringEngine.score_entity uses),
        the scenario's assumptions apply as a stress modulation on top of
        that real baseline (not as the sole input), and the overall score is
        blended with the trained ML classifier via MLBridge -- the same
        real-scoring path used everywhere else in this engine."""
        pool = await self._pool_or_default()

        scenario_uuid = str(uuid.uuid4())
        assumptions = scenario.get("assumptions", {})
        risk_dimensions = scenario.get("risk_dimensions", RISK_DIMENSIONS)

        row = await pool.fetchrow(
            """INSERT INTO energy.scenario_assumptions
               (uuid, name, description, assumptions, risk_dimensions, created_by)
               VALUES ($1,$2,$3,$4,$5,$6)
               RETURNING id, uuid, created_at""",
            scenario_uuid,
            scenario.get("name", "Unnamed Scenario"),
            scenario.get("description", ""),
            json.dumps(assumptions),
            risk_dimensions,
            scenario.get("created_by", "system"),
        )

        active_signals = await pool.fetch(
            """SELECT * FROM energy.disruption_signals
               WHERE expires_at > NOW() AND severity IN ('elevated','high','critical')"""
        )
        risk_factors = await pool.fetch(
            "SELECT * FROM energy.risk_factors WHERE is_active = true"
        )

        engine = RiskScoringEngine(self._pool)
        scores = {}
        for dim in risk_dimensions:
            dim_signals = [s for s in active_signals if s["risk_dimension"] == dim]
            baseline = engine._compute_dimension_score(dim_signals, risk_factors)

            # Assumption values > 0.5 represent a stress condition the user
            # is asking "what if" about for this dimension -- modulate the
            # real baseline upward rather than replacing it outright.
            stress = max(
                (float(v) for k, v in assumptions.items() if isinstance(v, (int, float)) and v > 0.5),
                default=0.0,
            )
            scores[dim] = min(1.0, baseline + stress * (1 - baseline) * 0.6)

        scores["overall"] = max(scores.values()) if scores else 0.05
        scores = await engine._blend_with_ml(scores, scenario_uuid, "scenario", active_signals)

        risk_level = self._score_to_level(scores["overall"])
        return {
            "scenario_id": row["id"],
            "scenario_uuid": row["uuid"],
            "created_at": row["created_at"].isoformat(),
            "name": scenario.get("name", "Unnamed Scenario"),
            "risk_scores": scores,
            "risk_level": risk_level,
            "assessment": self._generate_assessment(risk_level, assumptions),
        }

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score < 0.1:
            return "low"
        if score < 0.3:
            return "moderate"
        if score < 0.5:
            return "elevated"
        if score < 0.75:
            return "high"
        return "critical"

    @staticmethod
    def _generate_assessment(risk_level: str, assumptions: dict) -> str:
        templates = {
            "low": "Supply chain stability maintained. No immediate action required.",
            "moderate": "Minor disruptions possible. Monitoring recommended.",
            "elevated": "Supply chain under moderate stress. Review contingency plans.",
            "high": "Significant disruption likely. Activate mitigation protocols.",
            "critical": "Supply chain integrity at risk. Immediate intervention required.",
        }
        return templates.get(risk_level, "Assessment pending.")

    async def get_dashboard(self) -> dict[str, Any]:
        pool = await self._pool_or_default()

        active_signals = await pool.fetch(
            "SELECT COUNT(*) as cnt FROM energy.disruption_signals WHERE expires_at > NOW()"
        )
        high_signals = await pool.fetchrow(
            """SELECT COUNT(*) as cnt FROM energy.disruption_signals
               WHERE expires_at > NOW() AND severity IN ('high','critical')"""
        )
        latest_signals = await pool.fetch(
            """SELECT * FROM energy.disruption_signals
               ORDER BY created_at DESC LIMIT 20"""
        )
        avg_risk = await pool.fetchrow(
            """SELECT COALESCE(AVG(score), 0) as avg_score FROM energy.risk_scores
               WHERE expires_at > NOW()"""
        )
        risk_by_dim = await pool.fetch(
            """SELECT dimension, COALESCE(AVG(score), 0) as avg_score
               FROM energy.risk_scores WHERE expires_at > NOW()
               GROUP BY dimension ORDER BY avg_score DESC"""
        )

        return {
            "total_active_signals": active_signals[0]["cnt"] if active_signals else 0,
            "high_severity_signals": high_signals["cnt"] if high_signals else 0,
            "average_risk_score": round(float(avg_risk["avg_score"]), 4) if avg_risk else 0.0,
            "latest_signals": [dict(s) for s in latest_signals],
            "risk_by_dimension": [
                {"dimension": r["dimension"], "score": round(float(r["avg_score"]), 4)}
                for r in risk_by_dim
            ],
        }


# ── Data ingestor interface ─────────────────────────────────────────────────


class DataIngestor:
    """Base interface for all data source adapters."""

    source_name: str = "base"

    def __init__(self, pool: asyncpg.Pool | None = None):
        self._pool = pool

    async def _pool_or_default(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def ingest(self) -> int:
        raise NotImplementedError

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        raise NotImplementedError


# ── Commodity price ingestor ────────────────────────────────────────────────


class CommodityPriceIngestor(DataIngestor):
    """Commodity benchmark price ingestion -- not yet wired to a live source.

    Previously generated fabricated prices via hash-based jitter around
    hardcoded base values, presented as if real. Removed rather than left
    running: the only live price data currently ingested anywhere in this
    platform is ml-platform's crude-price-api dataset (Brent spot only, one
    of the ten benchmarks this class claimed to cover), so a real
    implementation needs either per-commodity live sources or an honest
    reduction in scope to what's actually available -- not fake numbers for
    the other nine."""

    source_name = "commodity_prices"

    async def ingest(self) -> int:
        raise NotImplementedError("CommodityPriceIngestor has no live data source wired yet")

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        raise NotImplementedError("CommodityPriceIngestor has no live data source wired yet")


# ── Sanctions ingestor ──────────────────────────────────────────────────────


class SanctionsIngestor(DataIngestor):
    """Country-level sanctions program ingestion -- not yet wired to a live source.

    Previously upserted a static hand-typed 10-country list every time it ran,
    entirely disconnected from the real ~330k-record OFAC/EU/OpenSanctions
    catalog ml-platform already ingests. That catalog is individual/entity
    level (specific designated persons and companies), not the country-program
    summary shape (country_code, scope, imposed_by) this table expects, so a
    real implementation needs an aggregation step, not a direct swap."""

    source_name = "sanctions"

    async def ingest(self) -> int:
        raise NotImplementedError("SanctionsIngestor has no live data source wired yet")

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        raise NotImplementedError("SanctionsIngestor has no live data source wired yet")


# ── AIS / Port congestion ingestor ──────────────────────────────────────────


class AISIngestor(DataIngestor):
    """AIS vessel position / port congestion ingestion -- not yet wired to a live source.

    Previously generated fabricated congestion percentages, vessel counts,
    and tanker availability via hash-based jitter, presented as if real. The
    genuinely live equivalent (ml-platform's scripts/ingest_aisstream.py,
    real AISstream.io vessel positions near major chokepoints) writes to a
    flat CSV file, not a queryable table energy-service can join against per
    request -- a real implementation needs that data exposed through an API
    (or registered in ml.dataset_catalog and read via ml-platform's HTTP
    surface), not a direct swap."""

    source_name = "ais"

    async def ingest(self) -> int:
        raise NotImplementedError("AISIngestor has no live data source wired yet")

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        raise NotImplementedError("AISIngestor has no live data source wired yet")


# ── Article-derived signal ingestor (real) ──────────────────────────────────


class ArticleSignalIngestor(DataIngestor):
    """Generates real disruption signals from the live news pipeline.

    Unlike the three disabled ingestors above, this one has a genuinely live
    source already flowing through this same database: processed_articles
    carries real ML output (trained XGBoost topic classifier + GDELT-blended
    threat score, see ml-platform/consumer/article_enrichment.py), and
    energy_entity_mappings already links articles to real energy.* catalog
    entities (ports/pipelines/refineries/SPRs/etc, matched by
    database-service/services/energy_enrichment.py on ingest). This reuses
    that pipeline instead of adding a new external source -- every field on
    the resulting signal traces back to a real article, not a fabrication.
    """

    source_name = "news_signals"

    MIN_THREAT_SCORE = 40.0
    LOOKBACK_HOURS = 24 * 14
    ARTICLE_SCAN_LIMIT = 150
    MAX_ENTITIES_PER_ARTICLE = 3
    SIGNAL_TTL_HOURS = 72

    TOPIC_TO_DIMENSION = {
        "war": "geopolitical",
        "diplomacy": "geopolitical",
        "economics": "economic",
        "cyber": "operational",
        "general": "operational",
    }

    async def ingest(self) -> int:
        """Scans recent, high-threat, energy-matched articles that haven't
        produced a signal yet and inserts one real disruption_signals row
        per (article, matched entity) pair, capped per article. Returns the
        number of signals created."""
        pool = await self._pool_or_default()
        # processed_articles.published_at/created_at are naive TIMESTAMP
        # columns (unlike energy.* which is TIMESTAMPTZ throughout), so the
        # cutoff passed to that comparison must be naive UTC too, or asyncpg
        # errors on offset-aware vs offset-naive comparison.
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=self.LOOKBACK_HOURS)

        rows = await pool.fetch(
            """
            WITH candidate_articles AS (
                SELECT pa.id, pa.title, pa.summary, pa.content, pa.url,
                       COALESCE(pa.published_at, pa.created_at) AS published_at,
                       pa.threat_score, pa.topic, pa.confidence
                FROM processed_articles pa
                WHERE pa.threat_score >= $1
                  AND COALESCE(pa.published_at, pa.created_at) > $2
                  AND EXISTS (SELECT 1 FROM energy_entity_mappings eem WHERE eem.article_id = pa.id)
                  AND NOT EXISTS (
                      SELECT 1 FROM energy.disruption_signals ds
                      WHERE ds.source = 'article:' || pa.id::text
                  )
                ORDER BY pa.threat_score DESC
                LIMIT $3
            )
            SELECT DISTINCT ON (ca.id, eem.energy_asset_uuid)
                ca.id AS article_id, ca.title, ca.summary, ca.content, ca.url,
                ca.published_at, ca.threat_score, ca.topic, ca.confidence,
                eem.energy_asset_type, eem.energy_asset_uuid, eem.energy_asset_name,
                eem.match_method, aee.context
            FROM candidate_articles ca
            JOIN energy_entity_mappings eem ON eem.article_id = ca.id
            LEFT JOIN article_energy_enrichments aee ON aee.article_id = ca.id
            ORDER BY ca.id, eem.energy_asset_uuid,
                     CASE WHEN eem.match_method = 'exact' THEN 0 ELSE 1 END
            """,
            self.MIN_THREAT_SCORE,
            cutoff,
            self.ARTICLE_SCAN_LIMIT,
        )

        detector = SignalDetector(self._pool)
        per_article_count: dict[int, int] = {}
        created = 0

        for r in rows:
            article_id = r["article_id"]
            if per_article_count.get(article_id, 0) >= self.MAX_ENTITIES_PER_ARTICLE:
                continue
            per_article_count[article_id] = per_article_count.get(article_id, 0) + 1

            severity = self._severity_from_threat_score(r["threat_score"])
            dimension = self.TOPIC_TO_DIMENSION.get(r["topic"], "operational")
            context = _ensure_dict(r["context"])
            regions = [str(x) for x in (context.get("countries_mentioned") or [])][:10]
            commodities = [str(x) for x in (context.get("commodities_mentioned") or [])][:10]

            description = (r["summary"] or (r["content"] or "")[:280]).strip()
            if not description:
                description = f"Elevated threat signal detected involving {r['energy_asset_name']}."

            try:
                await detector.ingest_signal({
                    "title": r["title"] or f"Disruption risk: {r['energy_asset_name']}",
                    "description": description,
                    "source": f"article:{article_id}",
                    "severity": severity,
                    "risk_dimension": dimension,
                    "affected_entity_type": r["energy_asset_type"],
                    "affected_entity_uuid": str(r["energy_asset_uuid"]),
                    "affected_commodities": commodities,
                    "affected_regions": regions,
                    "confidence": float(r["confidence"] or 0.7),
                    "evidence_urls": [r["url"]] if r["url"] else [],
                    "ttl_hours": self.SIGNAL_TTL_HOURS,
                })
                created += 1
            except Exception as exc:
                logger.warning("article_signal_ingest_failed", article_id=article_id, error=str(exc))

        logger.info("article_signal_ingest_complete", created=created, scanned_articles=len(per_article_count))
        return created

    @staticmethod
    def _severity_from_threat_score(threat_score: float | None) -> str:
        score = float(threat_score or 0)
        if score >= 75:
            return "critical"
        if score >= 55:
            return "high"
        if score >= 40:
            return "elevated"
        if score >= 20:
            return "moderate"
        return "low"

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        raise NotImplementedError("Signals are created directly by ingest() -- there is no separate detection pass")
