"""Supplier Intelligence — extend suppliers with procurement-relevant attributes, find alternatives, score reliability."""

import uuid
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class SupplierIntelligence:
    """Supplier intelligence engine: enrich, score, and find alternative suppliers."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def enrich_all(self) -> int:
        """Auto-generate supplier_intelligence records for suppliers that lack one."""
        existing = await self.pool.fetch(
            "SELECT supplier_uuid FROM energy.supplier_intelligence WHERE is_deleted = false"
        )
        existing_set = {r["supplier_uuid"] for r in existing}

        suppliers = await self.pool.fetch(
            "SELECT uuid, slug, name, supplier_type, criticality FROM energy.suppliers WHERE is_deleted = false"
        )

        count = 0
        for s in suppliers:
            if s["uuid"] in existing_set:
                continue
            country_stability = 0.5
            reliability = 0.7
            sanctions = False
            compliance = "low"
            credit = "BBB"
            lead_time = 30
            on_time = 85.0

            if s["supplier_type"] == "national_oil_company":
                reliability = 0.85
                country_stability = 0.6
                lead_time = 25
                on_time = 90.0
            elif s["supplier_type"] == "international_oil_company":
                reliability = 0.8
                country_stability = 0.7
                credit = "A"
                lead_time = 20
                on_time = 92.0
            elif s["supplier_type"] == "trader":
                reliability = 0.6
                lead_time = 15
                on_time = 80.0

            if s["criticality"] == "critical":
                strategic_value = 0.9
            elif s["criticality"] == "high":
                strategic_value = 0.7
            else:
                strategic_value = 0.4

            await self.pool.execute(
                """INSERT INTO energy.supplier_intelligence
                   (uuid, supplier_uuid, country_political_stability, reliability_score,
                    sanctions_exposure, compliance_risk, credit_rating,
                    avg_lead_time_days, on_time_delivery_pct, strategic_value, contract_type)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                str(uuid.uuid4()),
                s["uuid"],
                country_stability,
                reliability,
                sanctions,
                compliance,
                credit,
                lead_time,
                on_time,
                strategic_value,
                "spot",
            )
            count += 1
        return count

    async def find_alternatives(
        self,
        commodity_uuid: str,
        exclude_supplier_uuid: str,
        min_reliability: float = 0.5,
        max_risk_delta: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Find alternative suppliers for a commodity, excluding a given supplier."""
        commodity = await self.pool.fetchrow(
            "SELECT api_gravity, sulfur_content, commodity_type FROM energy.commodities WHERE uuid = $1::uuid",
            commodity_uuid,
        )
        if not commodity:
            return []

        api = commodity["api_gravity"]
        sulfur = commodity["sulfur_content"]
        ctype = commodity["commodity_type"]

        candidates = await self.pool.fetch(
            """SELECT s.uuid, s.name, s.supplier_type, s.market_share_pct,
                      si.reliability_score, si.country_political_stability,
                      si.sanctions_exposure, si.avg_lead_time_days, si.strategic_value,
                      l.name as country_name
               FROM energy.suppliers s
               LEFT JOIN energy.supplier_intelligence si ON si.supplier_uuid = s.uuid AND si.is_deleted = false
               LEFT JOIN energy.locations l ON l.uuid = s.location_id
               WHERE s.uuid != $1::uuid
                 AND s.is_deleted = false
                 AND (si.reliability_score IS NULL OR si.reliability_score >= $2)
                 AND (si.sanctions_exposure IS NULL OR si.sanctions_exposure = false)
               ORDER BY si.reliability_score DESC NULLS LAST, s.market_share_pct DESC
               LIMIT 20""",
            exclude_supplier_uuid,
            min_reliability,
        )

        results = []
        for c in candidates:
            score = self._compute_match_score(commodity, c)
            price_premium = abs(10 - score * 10)
            risk_delta = 1.0 - c.get("reliability_score") if c.get("reliability_score") else 0.2
            if risk_delta > max_risk_delta:
                continue
            results.append({
                "supplier_uuid": str(c["uuid"]),
                "supplier_name": c["name"],
                "supplier_type": c["supplier_type"],
                "country": c.get("country_name"),
                "market_share_pct": c["market_share_pct"],
                "reliability_score": c.get("reliability_score"),
                "country_stability": c.get("country_political_stability"),
                "lead_time_days": c.get("avg_lead_time_days"),
                "strategic_value": c.get("strategic_value"),
                "match_score": round(score, 4),
                "price_premium_bbl": round(price_premium, 2),
                "risk_delta": round(risk_delta, 4),
            })

        results.sort(key=lambda r: r["match_score"], reverse=True)
        return results

    def _compute_match_score(self, commodity: asyncpg.Record, candidate: asyncpg.Record) -> float:
        """Compute a 0-1 match score between commodity requirements and supplier capability."""
        score = 0.5

        reliability = candidate.get("reliability_score") or 0.5
        score += reliability * 0.15
        stability = candidate.get("country_political_stability") or 0.5
        score += stability * 0.1
        strategic = candidate.get("strategic_value") or 0.3
        score += strategic * 0.1
        mkt_share = (candidate["market_share_pct"] or 0) / 20.0
        score += min(mkt_share, 0.15)

        if candidate["supplier_type"] in ("national_oil_company",):
            score += 0.1
        elif candidate["supplier_type"] in ("trader",):
            score -= 0.05

        return min(max(score, 0.0), 1.0)

    async def get_supplier_profile(self, supplier_uuid: str) -> dict[str, Any] | None:
        """Get a supplier with its intelligence profile."""
        row = await self.pool.fetchrow(
            """SELECT s.*, si.*, l.name as country_name
               FROM energy.suppliers s
               LEFT JOIN energy.supplier_intelligence si ON si.supplier_uuid = s.uuid AND si.is_deleted = false
               LEFT JOIN energy.locations l ON l.uuid = s.location_id
               WHERE s.uuid = $1::uuid AND s.is_deleted = false""",
            supplier_uuid,
        )
        if not row:
            return None
        return dict(row)

    async def score_suppliers(self) -> list[dict[str, Any]]:
        """Score all suppliers by composite procurement index."""
        rows = await self.pool.fetch(
            """SELECT s.uuid, s.name, s.supplier_type, s.market_share_pct, s.criticality,
                      si.reliability_score, si.country_political_stability,
                      si.sanctions_exposure, si.strategic_value, si.avg_lead_time_days,
                      si.on_time_delivery_pct, l.name as country_name
               FROM energy.suppliers s
               LEFT JOIN energy.supplier_intelligence si ON si.supplier_uuid = s.uuid AND si.is_deleted = false
               LEFT JOIN energy.locations l ON l.uuid = s.location_id
               WHERE s.is_deleted = false
               ORDER BY si.reliability_score DESC NULLS LAST, s.market_share_pct DESC"""
        )
        results = []
        for r in rows:
            rel = r.get("reliability_score") or 0.5
            stable = r.get("country_political_stability") or 0.5
            strategic = r.get("strategic_value") or 0.3
            on_time = (r.get("on_time_delivery_pct") or 80) / 100.0
            lead_time_score = max(0, 1.0 - ((r.get("avg_lead_time_days") or 30) - 5) / 45.0)

            composite = round(
                rel * 0.30 + stable * 0.20 + strategic * 0.20 + on_time * 0.15 + lead_time_score * 0.15,
                4,
            )
            results.append({
                "uuid": str(r["uuid"]),
                "name": r["name"],
                "supplier_type": r["supplier_type"],
                "country": r.get("country_name"),
                "market_share_pct": r["market_share_pct"],
                "criticality": r["criticality"],
                "reliability_score": rel,
                "composite_score": composite,
                "sanctions_exposure": r.get("sanctions_exposure", False),
            })
        return sorted(results, key=lambda x: x["composite_score"], reverse=True)
