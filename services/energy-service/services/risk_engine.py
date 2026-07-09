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

        engine = RiskScoringEngine(self._pool)
        scores = {}
        for dim in risk_dimensions:
            mock_signals = []
            for assumption, value in assumptions.items():
                if isinstance(value, (int, float)) and value > 0.5:
                    mock_signals.append({
                        "severity": "elevated" if value < 0.7 else "high",
                        "confidence": min(value, 0.95),
                        "risk_dimension": dim,
                    })
            scores[dim] = engine._compute_dimension_score(mock_signals, [])

        scores["overall"] = max(scores.values()) if scores else 0.5

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
    """Ingests commodity benchmark prices and detects price volatility signals."""

    source_name = "commodity_prices"

    async def ingest(self) -> int:
        pool = await self._pool_or_default()

        benchmarks = [
            ("Brent Crude", "crude", 85.0, "USD/bbl"),
            ("WTI Crude", "crude", 78.0, "USD/bbl"),
            ("Dubai Crude", "crude", 82.0, "USD/bbl"),
            ("LNG Japan-Korea Marker", "lng", 12.5, "USD/MMBtu"),
            ("TTF Natural Gas", "natural_gas", 35.0, "EUR/MWh"),
            ("Henry Hub Natural Gas", "natural_gas", 3.2, "USD/MMBtu"),
            ("Gasoline RBOB", "refined", 2.5, "USD/gal"),
            ("ULSD Diesel", "refined", 2.8, "USD/gal"),
            ("Jet Fuel", "refined", 2.6, "USD/gal"),
            ("Fuel Oil 3.5%", "refined", 450.0, "USD/MT"),
        ]

        count = 0
        now = datetime.now(timezone.utc)
        for name, family, base_price, unit in benchmarks:
            jitter = (hash(name + str(now.hour)) % 100) / 100 * 2 - 1
            price = round(base_price * (1 + jitter * 0.03), 2)
            change_pct = round(jitter * 3, 2)
            await pool.execute(
                """INSERT INTO energy.commodity_prices
                   (uuid, commodity_name, commodity_family, price, unit,
                    change_pct, source, recorded_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                str(uuid.uuid4()), name, family, price, unit,
                change_pct, f"{self.source_name}/simulated", now,
            )
            count += 1

        logger.info("ingested commodity prices", count=count)
        return count

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        pool = await self._pool_or_default()
        signals = []

        rows = await pool.fetch(
            """SELECT commodity_name, price, change_pct, recorded_at
               FROM energy.commodity_prices
               WHERE recorded_at > NOW() - INTERVAL '1 hour'
               ORDER BY ABS(change_pct) DESC LIMIT 5"""
        )

        for row in rows:
            if abs(row["change_pct"]) > 5:
                severity = "high" if abs(row["change_pct"]) > 10 else "elevated"
                signal_data = {
                    "title": f"Price spike detected: {row['commodity_name']}",
                    "description": f"{row['commodity_name']} moved {row['change_pct']:+.1f}% to ${row['price']:.2f}",
                    "source": self.source_name,
                    "severity": severity,
                    "risk_dimension": "economic",
                    "affected_entity_type": "commodities",
                    "affected_commodities": [row["commodity_name"]],
                    "confidence": min(abs(row["change_pct"]) / 20, 0.95),
                }
                created = await detector.ingest_signal(signal_data)
                signals.append(created)

        return signals


# ── Sanctions ingestor ──────────────────────────────────────────────────────


class SanctionsIngestor(DataIngestor):
    """Ingests sanctions data and creates geopolitical risk signals."""

    source_name = "sanctions"

    async def ingest(self) -> int:
        pool = await self._pool_or_default()

        sanctions = [
            ("IR", "Iran", "Comprehensive", "US, EU, UN", "crude, petrochemicals", "primary"),
            ("RU", "Russia", "Energy Sector", "US, EU, UK, G7", "crude, refined products, lng", "primary"),
            ("VE", "Venezuela", "Comprehensive", "US", "crude, refined products", "primary"),
            ("SD", "Sudan", "Restricted", "US, EU", "crude", "primary"),
            ("KP", "North Korea", "Comprehensive", "UN, US, EU, Japan, ROK", "all energy", "primary"),
            ("MM", "Myanmar", "Sectoral", "US, EU, UK", "gas", "secondary"),
            ("SY", "Syria", "Comprehensive", "US, EU, Arab League", "crude, refined products", "primary"),
            ("LB", "Libya", "Arms Embargo", "UN, EU", "crude (indirect)", "secondary"),
            ("IQ", "Iraq", "Restricted", "UN (historic)", "crude", "expired"),
            ("BY", "Belarus", "Sectoral", "US, EU, UK", "refined products", "secondary"),
        ]

        count = 0
        for code, country, scope, imposed_by, affected_commodities, status in sanctions:
            await pool.execute(
                """INSERT INTO energy.sanctions
                   (uuid, country_code, country_name, sanction_scope, imposed_by,
                    affected_commodities, status, source)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (country_code, sanction_scope) DO UPDATE
                   SET imposed_by = EXCLUDED.imposed_by,
                       status = EXCLUDED.status,
                       updated_at = NOW()""",
                str(uuid.uuid4()), code, country, scope, imposed_by,
                affected_commodities, status, self.source_name,
            )
            count += 1

        logger.info("ingested sanctions", count=count)
        return count

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        pool = await self._pool_or_default()
        signals = []

        rows = await pool.fetch(
            """SELECT * FROM energy.sanctions
               WHERE status = 'primary' AND is_active = true"""
        )

        for row in rows:
            signal_data = {
                "title": f"Active sanctions: {row['country_name']}",
                "description": f"{row['sanction_scope']} sanctions by {row['imposed_by']} affecting {row['affected_commodities']}",
                "source": self.source_name,
                "severity": "high",
                "risk_dimension": "geopolitical",
                "affected_regions": [row["country_code"]],
                "confidence": 0.9,
            }
            created = await detector.ingest_signal(signal_data)
            signals.append(created)

        return signals


# ── AIS / Port congestion ingestor ──────────────────────────────────────────


class AISIngestor(DataIngestor):
    """Simulates AIS vessel position and port congestion data."""

    source_name = "ais"

    async def ingest(self) -> int:
        pool = await self._pool_or_default()
        now = datetime.now(timezone.utc)

        chokepoints = [
            ("Strait of Hormuz", 25.2959, 56.2993, "chokepoint"),
            ("Strait of Malacca", 1.4358, 102.4487, "chokepoint"),
            ("Bab-el-Mandeb", 12.5916, 43.4223, "chokepoint"),
            ("Suez Canal", 30.5054, 32.5524, "chokepoint"),
            ("Turkish Straits", 41.1072, 29.0637, "chokepoint"),
            ("Panama Canal", 9.0810, -79.6844, "chokepoint"),
            ("Cape of Good Hope", -34.3571, 18.4744, "chokepoint"),
            ("Danish Straits", 55.6949, 10.6666, "chokepoint"),
        ]

        ports = [
            ("Ras Tanura", 26.6420, 50.1620, "Saudi Arabia", 500000),
            ("Fujairah", 25.1198, 56.3389, "UAE", 400000),
            ("Rotterdam", 51.8985, 4.5012, "Netherlands", 350000),
            ("Singapore", 1.2833, 103.8333, "Singapore", 600000),
            ("Shanghai", 31.2304, 121.4737, "China", 800000),
            ("Houston", 29.7589, -94.9867, "USA", 450000),
            ("Antwerp", 51.2657, 4.3488, "Belgium", 300000),
            ("Mina Al Ahmadi", 29.0769, 48.0833, "Kuwait", 350000),
            ("Basra", 30.5154, 47.8314, "Iraq", 250000),
            ("Tianjin", 38.9985, 117.7087, "China", 500000),
            ("Yanbu", 24.0908, 38.0641, "Saudi Arabia", 300000),
            ("Port Arthur", 29.8833, -93.9333, "USA", 350000),
            ("Marseille", 43.2965, 5.3698, "France", 200000),
            ("Sikka", 22.4360, 69.8000, "India", 250000),
            ("Ulsan", 35.5384, 129.3169, "South Korea", 400000),
        ]

        count = 0
        for name, lat, lng, country, congestion_base in ports:
            congestion_pct = min(100, max(10, congestion_base / 10000 + (hash(name + str(now.hour)) % 50 - 25)))
            await pool.execute(
                """INSERT INTO energy.port_congestion
                   (uuid, port_name, country, latitude, longitude,
                    congestion_pct, waiting_vessels, avg_wait_hours, recorded_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                str(uuid.uuid4()), name, country, lat, lng,
                round(congestion_pct, 1),
                int(congestion_pct / 5),
                round(congestion_pct / 10, 1),
                now,
            )
            count += 1

        for name, lat, lng, kind in chokepoints:
            vessel_count = hash(name + str(now.hour)) % 25 + 5
            avg_speed_knots = round(8 + (hash(name + str(now.hour+1)) % 100) / 100 * 8, 1)
            await pool.execute(
                """INSERT INTO energy.ais_positions
                   (uuid, location_name, latitude, longitude, location_type,
                    vessel_count, avg_speed_knots, recorded_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                str(uuid.uuid4()), name, lat, lng, kind,
                vessel_count, avg_speed_knots, now,
            )
            count += 1

        tanker_data = [
            ("VLCC", 42, 310, 3.8),
            ("Suezmax", 28, 200, 4.2),
            ("Aframax", 35, 250, 3.5),
            ("LR2", 18, 80, 5.1),
            ("LR1", 22, 95, 4.8),
            ("MR", 30, 120, 4.0),
        ]

        for vessel_type, available, total, avg_rate in tanker_data:
            utilization = 1 - (available / total)
            await pool.execute(
                """INSERT INTO energy.tanker_availability
                   (uuid, vessel_type, vessels_available, total_vessels,
                    avg_daily_rate_usd, utilization_pct, recorded_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()), vessel_type, available, total,
                round(avg_rate * 10000), round(utilization * 100, 1), now,
            )

        return count

    async def detect_signals(self, detector: SignalDetector) -> list[dict]:
        pool = await self._pool_or_default()
        signals = []

        congested = await pool.fetch(
            """SELECT * FROM energy.port_congestion
               WHERE congestion_pct > 70 AND recorded_at > NOW() - INTERVAL '2 hours'
               ORDER BY congestion_pct DESC LIMIT 5"""
        )

        for row in congested:
            severity = "critical" if row["congestion_pct"] > 90 else "high"
            signal_data = {
                "title": f"Port congestion: {row['port_name']}",
                "description": f"{row['port_name']} at {row['congestion_pct']:.0f}% capacity with {row['waiting_vessels']} vessels waiting (avg {row['avg_wait_hours']:.1f}h)",
                "source": self.source_name,
                "severity": severity,
                "risk_dimension": "operational",
                "affected_regions": [row["country"]],
                "confidence": 0.85,
            }
            created = await detector.ingest_signal(signal_data)
            signals.append(created)

        return signals
