"""Procurement Optimization Engine — multi-objective trade-off analysis with Pareto frontier computation."""

import math
import json
import uuid
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ProcurementOptimizer:
    """Multi-objective procurement optimizer — cost, risk, and lead-time trade-offs."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def optimize(
        self,
        supply_gap_bpd: float,
        commodity_uuid: str | None = None,
        destination_region: str | None = None,
        max_cost_bbl: float = 100.0,
        max_risk_score: float = 0.8,
        max_lead_days: int = 60,
        optimization_goal: str = "balanced",
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Run multi-objective optimization to find optimal procurement options."""
        suppliers = await self._get_qualified_suppliers(commodity_uuid, max_risk_score, max_lead_days)

        if not suppliers:
            return {
                "options": [],
                "pareto_frontier": [],
                "recommended": None,
                "total_options": 0,
                "message": "No qualified suppliers found for the given constraints",
            }

        options = []
        for s in suppliers:
            option = await self._build_option(s, supply_gap_bpd, commodity_uuid, destination_region)
            if option and option["cost_bbl"] <= max_cost_bbl:
                options.append(option)

        if not options:
            return {
                "options": [],
                "pareto_frontier": [],
                "recommended": None,
                "total_options": 0,
                "message": "No options within cost constraints",
            }

        pareto = self._compute_pareto_frontier(options)
        recommended = self._select_recommended(options, optimization_goal, pareto)

        return {
            "options": sorted(options, key=lambda x: x["composite_score"], reverse=True),
            "pareto_frontier": pareto,
            "recommended": recommended,
            "total_options": len(options),
            "pareto_count": len(pareto),
            "optimization_goal": optimization_goal,
            "supply_gap_bpd": supply_gap_bpd,
        }

    async def _get_qualified_suppliers(
        self,
        commodity_uuid: str | None = None,
        max_risk: float = 0.8,
        max_lead_days: int = 60,
    ) -> list[asyncpg.Record]:
        """Get suppliers that meet qualification criteria."""
        if commodity_uuid:
            commodity = await self.pool.fetchrow(
                "SELECT api_gravity, sulfur_content FROM energy.commodities WHERE uuid = $1::uuid",
                commodity_uuid,
            )

        rows = await self.pool.fetch(
            """SELECT s.uuid, s.name, s.supplier_type, s.market_share_pct,
                      si.reliability_score, si.avg_lead_time_days,
                      si.on_time_delivery_pct, si.typical_volume_bpd,
                      si.spot_premium_bbl, si.strategic_value,
                      si.sanctions_exposure, si.country_political_stability,
                      l.name as country_name
               FROM energy.suppliers s
               LEFT JOIN energy.supplier_intelligence si ON si.supplier_uuid = s.uuid AND si.is_deleted = false
               LEFT JOIN energy.locations l ON l.uuid = s.location_id
               WHERE s.is_deleted = false
                 AND (si.sanctions_exposure IS NULL OR si.sanctions_exposure = false)
                 AND (si.avg_lead_time_days IS NULL OR si.avg_lead_time_days <= $1)
               ORDER BY si.reliability_score DESC NULLS LAST, s.market_share_pct DESC""",
            max_lead_days,
        )
        return rows

    async def _build_option(
        self,
        supplier: asyncpg.Record,
        volume_bpd: float,
        commodity_uuid: str | None = None,
        destination_region: str | None = None,
    ) -> dict[str, Any] | None:
        """Build a procurement option for a given supplier."""
        rel = supplier.get("reliability_score") or 0.5
        lead_time = supplier.get("avg_lead_time_days") or 30
        market_share = supplier["market_share_pct"] or 1.0
        stability = supplier.get("country_political_stability") or 0.5
        premium = supplier.get("spot_premium_bbl") or 0.0
        strategic = supplier.get("strategic_value") or 0.3
        on_time = (supplier.get("on_time_delivery_pct") or 80) / 100.0

        base_price = 75.0
        transport_cost = 5.0 + (1.0 - stability) * 5.0
        risk_insurance = (1.0 - rel) * 10.0
        tariff = 2.0

        cost_bbl = base_price + transport_cost + risk_insurance + tariff + premium
        risk_score = 1.0 - (rel * 0.5 + stability * 0.3 + on_time * 0.2)

        lead_time_score = max(0, 1.0 - (lead_time - 5) / 55.0)
        cost_score = max(0, 1.0 - (cost_bbl - 50) / 100.0)
        risk_component = 1.0 - risk_score

        if cost_bbl > 200 or risk_score > 0.95:
            return None

        composite = round(
            cost_score * 0.35 + risk_component * 0.30 + lead_time_score * 0.20 + strategic * 0.15,
            4,
        )

        actual_volume = min(volume_bpd, supplier.get("typical_volume_bpd") or volume_bpd * 2)
        total_cost = actual_volume * cost_bbl * 365

        return {
            "supplier_uuid": str(supplier["uuid"]),
            "supplier_name": supplier["name"],
            "supplier_type": supplier["supplier_type"],
            "country": supplier.get("country_name"),
            "market_share_pct": market_share,
            "cost_bbl": round(cost_bbl, 2),
            "base_price": round(base_price, 2),
            "transport_cost": round(transport_cost, 2),
            "risk_insurance": round(risk_insurance, 2),
            "tariff": round(tariff, 2),
            "premium": round(premium, 2),
            "risk_score": round(risk_score, 4),
            "lead_time_days": lead_time,
            "reliability": rel,
            "volume_bpd": actual_volume,
            "total_annual_cost_usd": round(total_cost, 2),
            "composite_score": composite,
            "strategic_value": strategic,
        }

    def _compute_pareto_frontier(self, options: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute Pareto-optimal frontier across cost, risk, and lead time."""
        if not options:
            return []

        pareto = []
        for i, opt in enumerate(options):
            dominated = False
            for j, other in enumerate(options):
                if i == j:
                    continue
                if (other["cost_bbl"] <= opt["cost_bbl"]
                        and other["risk_score"] <= opt["risk_score"]
                        and other["lead_time_days"] <= opt["lead_time_days"]
                        and (other["cost_bbl"] < opt["cost_bbl"]
                             or other["risk_score"] < opt["risk_score"]
                             or other["lead_time_days"] < opt["lead_time_days"])):
                    dominated = True
                    break
            if not dominated:
                pareto.append(opt)
        return sorted(pareto, key=lambda x: x["cost_bbl"])

    def _select_recommended(
        self,
        options: list[dict[str, Any]],
        goal: str,
        pareto: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Select the best option based on optimization goal."""
        if not options:
            return None

        if goal == "cost":
            return min(options, key=lambda x: x["cost_bbl"])
        if goal == "risk":
            return min(options, key=lambda x: x["risk_score"])
        if goal == "speed":
            return min(options, key=lambda x: x["lead_time_days"])

        if pareto:
            return max(pareto, key=lambda x: x["composite_score"])
        return max(options, key=lambda x: x["composite_score"])

    async def compute_route_costs(self) -> dict[str, Any]:
        """Estimate route costs from network graph and persist."""
        routes = await self.pool.fetch(
            """SELECT e.id, e.source_node_id, e.target_node_id, e.max_capacity_bpd,
                      e.travel_time_hours, e.transport_cost_bbl, e.risk_multiplier,
                      e.metadata, sn.country as origin_country, tn.country as dest_country
               FROM energy.network_edges e
               JOIN energy.network_nodes sn ON sn.id = e.source_node_id
               JOIN energy.network_nodes tn ON tn.id = e.target_node_id
               WHERE e.is_deleted = false AND e.is_active = true"""
        )

        count = 0
        for r in routes:
            dist_nm = r.get("travel_time_hours") or 100
            base_transport = r.get("transport_cost_bbl") or 2.0
            risk_mult = r.get("risk_multiplier") or 1.0
            insurance = base_transport * 0.1 * risk_mult
            risk_adj = base_transport * (risk_mult - 1.0) * 0.5
            tariff = 1.5
            total = base_transport + insurance + risk_adj + tariff

            existing = await self.pool.fetchval(
                "SELECT id FROM energy.route_costs WHERE origin_node_id = $1 AND destination_node_id = $2",
                r["source_node_id"],
                r["target_node_id"],
            )
            if existing:
                await self.pool.execute(
                    """UPDATE energy.route_costs SET transport_cost_bbl=$1, insurance_cost_bbl=$2,
                       risk_adjustment_bbl=$3, tariff_cost_bbl=$4, total_cost_bbl=$5,
                       distance_nm=$6, route_risk_score=$7, updated_at=NOW() WHERE id=$8""",
                    base_transport,
                    insurance,
                    risk_adj,
                    tariff,
                    total,
                    dist_nm * 1.15,
                    risk_mult,
                    existing,
                )
            else:
                await self.pool.execute(
                    """INSERT INTO energy.route_costs
                       (uuid, origin_node_id, destination_node_id, transport_cost_bbl,
                        insurance_cost_bbl, tariff_cost_bbl, risk_adjustment_bbl,
                        total_cost_bbl, distance_nm, transit_time_days, route_risk_score)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                    str(uuid.uuid4()),
                    r["source_node_id"],
                    r["target_node_id"],
                    base_transport,
                    insurance,
                    tariff,
                    risk_adj,
                    total,
                    dist_nm * 1.15,
                    (dist_nm or 100) / 24.0,
                    risk_mult,
                )
                count += 1

        return {"routes_evaluated": len(routes), "route_costs_created": count}
