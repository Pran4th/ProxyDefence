"""Procurement Orchestrator — runs end-to-end procurement optimization from simulation results or direct input."""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger
from services.procurement.supplier_intel import SupplierIntelligence
from services.procurement.compatibility import RefineryCompatibility
from services.procurement.optimizer import ProcurementOptimizer

logger = get_logger(__name__)


def _ensure_dict(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    if val is None:
        return {}
    return val if hasattr(val, "get") else {}


def _ensure_list(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def normalize_executive_card(card: dict) -> dict:
    """asyncpg doesn't auto-decode jsonb columns to Python objects on this
    pool (no codec registered), so executive_recommendations' jsonb columns
    come back as raw JSON strings unless explicitly parsed here."""
    card["financial_impact"] = _ensure_dict(card.get("financial_impact"))
    card["operational_impact"] = _ensure_dict(card.get("operational_impact"))
    card["recommended_actions"] = _ensure_list(card.get("recommended_actions"))
    card["supporting_data"] = _ensure_dict(card.get("supporting_data"))
    return card


class ProcurementOrchestrator:
    """End-to-end procurement orchestration — from disruption signals to executable recommendations."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.supplier_intel = SupplierIntelligence(pool)
        self.compatibility = RefineryCompatibility(pool)
        self.optimizer = ProcurementOptimizer(pool)

    async def run_procurement(
        self,
        simulation_run_uuid: str | None = None,
        name: str = "Procurement Optimization Run",
        description: str = "",
        supply_gap_bpd: float | None = None,
        commodity_uuid: str | None = None,
        destination_region: str | None = None,
        optimization_goal: str = "balanced",
        max_cost_bbl: float = 100.0,
        max_risk_score: float = 0.8,
        max_lead_days: int = 60,
    ) -> dict[str, Any]:
        """Execute a full procurement optimization run."""
        t0 = time.time()
        run_uuid = str(uuid.uuid4())

        if simulation_run_uuid:
            sim = await self.pool.fetchrow(
                "SELECT * FROM energy.digital_twin_runs WHERE uuid = $1::uuid",
                simulation_run_uuid,
            )
            if not sim:
                raise ValueError(f"Simulation run {simulation_run_uuid} not found")
            impacts = _ensure_dict(sim.get("aggregate_impacts"))
            supply_gap_bpd = supply_gap_bpd or impacts.get("supply_gap_bpd", 0) or sim.get("supply_gap_bpd", 0)
        elif supply_gap_bpd is None:
            supply_gap_bpd = 100000

        await self.pool.execute(
            """INSERT INTO energy.procurement_runs
               (uuid, simulation_run_uuid, name, description, status, priority,
                optimization_goal, total_supply_gap_bpd, started_at)
               VALUES ($1,$2,$3,$4,'active','high',$5,$6,NOW())""",
            run_uuid,
            simulation_run_uuid,
            name,
            description,
            optimization_goal,
            supply_gap_bpd,
        )

        assumptions = []

        if simulation_run_uuid:
            assumptions.append({
                "key": "simulation_source",
                "value": simulation_run_uuid,
                "type": "reference",
                "source": "digital_twin",
            })
        assumptions.append({
            "key": "optimization_goal",
            "value": optimization_goal,
            "type": "parameter", "source": "user",
        })
        assumptions.append({
            "key": "max_cost_bbl",
            "value": str(max_cost_bbl),
            "type": "constraint", "source": "user",
        })
        assumptions.append({
            "key": "max_risk_score",
            "value": str(max_risk_score),
            "type": "constraint", "source": "user",
        })
        assumptions.append({
            "key": "supply_gap_bpd",
            "value": str(supply_gap_bpd),
            "type": "parameter", "source": "simulation",
        })

        for a in assumptions:
            await self.pool.execute(
                """INSERT INTO energy.procurement_assumptions
                   (uuid, procurement_run_uuid, assumption_key, assumption_value, assumption_type, source)
                   VALUES ($1,$2,$3,$4,$5,$6)""",
                str(uuid.uuid4()),
                run_uuid,
                a["key"],
                a["value"],
                a["type"],
                a["source"],
            )

        opt_result = await self.optimizer.optimize(
            supply_gap_bpd=supply_gap_bpd,
            commodity_uuid=commodity_uuid,
            destination_region=destination_region,
            max_cost_bbl=max_cost_bbl,
            max_risk_score=max_risk_score,
            max_lead_days=max_lead_days,
            optimization_goal=optimization_goal,
        )

        pareto_options = opt_result.get("pareto_frontier", [])
        recommended = opt_result.get("recommended")

        total_risk = 0.0
        for o in opt_result.get("options", []):
            await self._create_recommendation(run_uuid, o, supply_gap_bpd, optimization_goal)
            total_risk += o.get("risk_score", 0) * o.get("volume_bpd", 0)

        total_volume = sum(o.get("volume_bpd", 0) for o in opt_result.get("options", []))
        total_cost = sum(o.get("total_annual_cost_usd", 0) for o in opt_result.get("options", []))
        avg_risk = total_risk / total_volume if total_volume > 0 else 0

        exec_summary = self._generate_executive_summary(
            name, supply_gap_bpd, opt_result, optimization_goal,
        )

        # Create executive recommendation cards
        await self._create_executive_cards(run_uuid, name, supply_gap_bpd, opt_result)

        elapsed = (time.time() - t0) * 1000
        await self.pool.execute(
            """UPDATE energy.procurement_runs
               SET status='completed', total_recommended_bpd=$2, total_cost_estimate_usd=$3,
                   total_risk_score=$4, pareto_options=$5, executive_summary=$6,
                   completed_at=NOW(), execution_time_ms=$7, updated_at=NOW()
               WHERE uuid=$1::uuid""",
            run_uuid,
            total_volume,
            total_cost,
            round(avg_risk, 4),
            json.dumps(pareto_options),
            exec_summary,
            round(elapsed, 2),
        )

        return {
            "run_uuid": run_uuid,
            "name": name,
            "supply_gap_bpd": supply_gap_bpd,
            "total_recommended_bpd": total_volume,
            "total_cost_estimate_usd": total_cost,
            "total_risk_score": round(avg_risk, 4),
            "recommendations_count": len(opt_result.get("options", [])),
            "pareto_count": len(pareto_options),
            "executive_summary": exec_summary,
            "recommended": recommended,
            "execution_time_ms": round(elapsed, 2),
        }

    async def _create_recommendation(
        self,
        run_uuid: str,
        option: dict[str, Any],
        supply_gap: float,
        goal: str,
    ):
        """Create a procurement recommendation from an optimizer option."""
        prio = "medium"
        urgency = "normal"
        risk = option.get("risk_score", 0.5)
        cost = option.get("cost_bbl", 80)
        vol = option.get("volume_bpd", 0)
        rel = option.get("reliability", 0.7)

        if option.get("composite_score", 0) >= 0.75:
            prio = "high"
            urgency = "immediate"
        elif option.get("composite_score", 0) <= 0.3:
            prio = "low"
            urgency = "optional"

        title = f"Procure from {option['supplier_name']}"
        desc = (
            f"{option['supplier_name']} ({option['country']}) can supply "
            f"{vol:,.0f} bpd at ${cost:.2f}/bbl. "
            f"Risk score: {risk:.2f}, lead time: {option.get('lead_time_days', 30)} days."
        )

        coverage_pct = round((vol / supply_gap * 100), 1) if supply_gap > 0 else 0
        expected_impact = f"Covers {coverage_pct}% of supply gap ({vol:,.0f} of {supply_gap:,.0f} bpd)"

        await self.pool.execute(
            """INSERT INTO energy.procurement_recommendations
               (uuid, procurement_run_uuid, recommendation_type, priority, title, description,
                volume_bpd, unit_cost_usd, total_cost_usd, risk_score, confidence,
                urgency, expected_impact, data_sources)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
            str(uuid.uuid4()),
            run_uuid,
            "supplier_selection",
            prio,
            title,
            desc,
            vol,
            cost,
            vol * cost * 365,
            round(risk, 4),
            round(rel, 4),
            urgency,
            expected_impact,
            ["supplier_intelligence", "route_costs", "optimization_engine"],
        )

    async def _create_executive_cards(
        self,
        run_uuid: str,
        name: str,
        supply_gap: float,
        opt_result: dict[str, Any],
    ):
        """Generate executive-level recommendation cards."""
        now = datetime.now(timezone.utc)

        options = opt_result.get("options", [])
        pareto = opt_result.get("pareto_frontier", [])
        recommended = opt_result.get("recommended")

        total_vol = sum(o.get("volume_bpd", 0) for o in options)
        total_cost = sum(o.get("total_annual_cost_usd", 0) for o in options)
        avg_cost = sum(o.get("cost_bbl", 0) for o in options) / len(options) if options else 0
        avg_risk = sum(o.get("risk_score", 0) for o in options) / len(options) if options else 0

        gap_covered = min(total_vol / supply_gap * 100, 100) if supply_gap > 0 else 0
        remaining = max(0, supply_gap - total_vol)

        cards = [
            {
                "title": "Supply Gap Analysis",
                "summary": (
                    f"Total supply disruption: {supply_gap:,.0f} bpd. "
                    f"Procurement options cover {gap_covered:.1f}% ({total_vol:,.0f} bpd). "
                    f"Remaining gap: {remaining:,.0f} bpd."
                ),
                "severity": "critical" if remaining > supply_gap * 0.5 else "warning",
                "category": "supply_gap",
                "financial_impact": {"total_cost_usd": total_cost, "avg_cost_bbl": avg_cost},
                "operational_impact": {"gap_covered_pct": gap_covered, "remaining_gap_bpd": remaining},
                "strategic_importance": 0.9,
                "confidence": 0.8,
                "time_horizon": "immediate",
                "recommended_actions": [
                    f"Authorize procurement of {total_vol:,.0f} bpd from {len(options)} qualified suppliers",
                    f"Initiate SPR drawdown for remaining {remaining:,.0f} bpd gap",
                    f"Fast-track contracts with top-3 suppliers covering {gap_covered:.0f}% of gap",
                ],
            },
            {
                "title": f"Recommended Supplier Strategy — {name}",
                "summary": (
                    f"Recommended option: {recommended['supplier_name']} at ${recommended['cost_bbl']:.2f}/bbl "
                    f"with risk score {recommended['risk_score']:.2f}. "
                    f"Pareto frontier has {len(pareto)} non-dominated options across cost, risk, and lead time."
                ),
                "severity": "info",
                "category": "supplier_strategy",
                "financial_impact": {
                    "recommended_cost_bbl": recommended["cost_bbl"] if recommended else 0,
                    "recommended_annual_cost": recommended["total_annual_cost_usd"] if recommended else 0,
                },
                "operational_impact": {
                    "pareto_options": len(pareto),
                    "recommended_volume_bpd": recommended["volume_bpd"] if recommended else 0,
                },
                "strategic_importance": 0.85,
                "confidence": 0.75,
                "time_horizon": "short_term",
                "recommended_actions": [
                    f"Contract {recommended['supplier_name']} for {recommended['volume_bpd']:,.0f} bpd",
                    f"Negotiate {recommended.get('lead_time_days', 30)}-day delivery terms",
                    "File RFQ for remaining volume across 3 backup suppliers" if len(options) > 1 else "Negotiate exclusive supply agreement",
                ],
            },
        ]

        if pareto:
            cards.append({
                "title": "Cost-Risk Pareto Analysis",
                "summary": (
                    f"Found {len(pareto)} Pareto-optimal options. Cost range: "
                    f"${min(o['cost_bbl'] for o in pareto):.2f} to ${max(o['cost_bbl'] for o in pareto):.2f}/bbl. "
                    f"Risk range: {min(o['risk_score'] for o in pareto):.2f} to {max(o['risk_score'] for o in pareto):.2f}."
                ),
                "severity": "info",
                "category": "pareto_analysis",
                "financial_impact": {
                    "cost_min_bbl": min(o["cost_bbl"] for o in pareto),
                    "cost_max_bbl": max(o["cost_bbl"] for o in pareto),
                },
                "operational_impact": {
                    "risk_min": min(o["risk_score"] for o in pareto),
                    "risk_max": max(o["risk_score"] for o in pareto),
                },
                "strategic_importance": 0.7,
                "confidence": 0.8,
                "time_horizon": "medium_term",
                "recommended_actions": [
                    "Use Pareto frontier to negotiate competitive pricing",
                    "Diversify across 2-3 Pareto-optimal suppliers",
                    "Build spot purchase capability for cost-optimal options",
                ],
            })

        if remaining > 0:
            cards.append({
                "title": "Residual Supply Risk Alert",
                "summary": (
                    f"Uncovered supply gap: {remaining:,.0f} bpd ({100 - gap_covered:.1f}% of total disruption). "
                    f"Recommended: SPR drawdown, demand rationing, or emergency procurement."
                ),
                "severity": "critical" if remaining > supply_gap * 0.3 else "warning",
                "category": "residual_risk",
                "financial_impact": {
                    "uncovered_volume_bpd": remaining,
                    "estimated_economic_loss_usd": remaining * 100 * 365,
                },
                "operational_impact": {
                    "uncovered_pct": round(100 - gap_covered, 1),
                    "days_until_critical": max(1, int(remaining / 10000)) if remaining > 0 else 999,
                },
                "strategic_importance": 0.95,
                "confidence": 0.85,
                "time_horizon": "immediate",
                "recommended_actions": [
                    f"Initiate SPR drawdown up to {remaining:,.0f} bpd",
                    "Activate emergency supplier network",
                    "Implement demand-side management measures",
                    "Accelerate alternative fuel switching programs",
                ],
            })

        for card in cards:
            await self.pool.execute(
                """INSERT INTO energy.executive_recommendations
                   (uuid, procurement_run_uuid, title, summary, severity, category,
                    financial_impact, operational_impact, strategic_importance,
                    confidence, time_horizon, recommended_actions, supporting_data, data_sources)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                str(uuid.uuid4()),
                run_uuid,
                card["title"],
                card["summary"],
                card["severity"],
                card["category"],
                json.dumps(card["financial_impact"]),
                json.dumps(card["operational_impact"]),
                card["strategic_importance"],
                card["confidence"],
                card["time_horizon"],
                json.dumps(card["recommended_actions"]),
                json.dumps({
                    "supply_gap_bpd": supply_gap,
                    "total_options": len(options),
                    "pareto_count": len(pareto),
                    "optimization_goal": self._get_last_goal(),
                }),
                ["procurement_orchestrator", "optimization_engine", "supplier_intelligence"],
            )

    _last_goal: str = "balanced"

    def _get_last_goal(self) -> str:
        return self._last_goal

    def _generate_executive_summary(
        self,
        name: str,
        supply_gap: float,
        opt_result: dict[str, Any],
        goal: str,
    ) -> str:
        self._last_goal = goal
        options = opt_result.get("options", [])
        pareto = opt_result.get("pareto_frontier", [])
        recommended = opt_result.get("recommended")

        if not options:
            return f"Procurement run '{name}' found no qualified options for {supply_gap:,.0f} bpd supply gap."

        total_vol = sum(o.get("volume_bpd", 0) for o in options)
        avg_cost = sum(o.get("cost_bbl", 0) for o in options) / len(options)

        summary = (
            f"Procurement optimization '{name}' completed for {supply_gap:,.0f} bpd supply gap. "
            f"Evaluated {opt_result['total_options']} options across cost, risk, and lead time. "
            f"Recommended {total_vol:,.0f} bpd at ${avg_cost:.2f}/bbl average. "
            f"Pareto frontier: {len(pareto)} optimal trade-off options identified. "
        )

        if recommended:
            summary += (
                f"Top recommendation: {recommended['supplier_name']} at ${recommended['cost_bbl']:.2f}/bbl "
                f"(risk: {recommended['risk_score']:.2f}, lead: {recommended.get('lead_time_days', 30)}d)."
            )

        summary += f" Optimization goal: {goal}."
        return summary

    async def get_run(self, run_uuid: str) -> dict[str, Any] | None:
        """Get a procurement run with all its recommendations."""
        run = await self.pool.fetchrow(
            "SELECT * FROM energy.procurement_runs WHERE uuid = $1::uuid", run_uuid,
        )
        if not run:
            return None

        recs = await self.pool.fetch(
            "SELECT * FROM energy.procurement_recommendations WHERE procurement_run_uuid = $1::uuid AND is_deleted = false ORDER BY priority, created_at",
            run_uuid,
        )
        exec_cards = await self.pool.fetch(
            "SELECT * FROM energy.executive_recommendations WHERE procurement_run_uuid = $1::uuid AND is_deleted = false ORDER BY created_at",
            run_uuid,
        )
        assumptions = await self.pool.fetch(
            "SELECT * FROM energy.procurement_assumptions WHERE procurement_run_uuid = $1::uuid",
            run_uuid,
        )

        return {
            "run": dict(run),
            "recommendations": [dict(r) for r in recs],
            "executive_cards": [normalize_executive_card(dict(r)) for r in exec_cards],
            "assumptions": [dict(r) for r in assumptions],
        }

    async def list_runs(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """List procurement runs."""
        if status:
            rows = await self.pool.fetch(
                "SELECT * FROM energy.procurement_runs WHERE status = $1 ORDER BY created_at DESC LIMIT $2",
                status, limit,
            )
        else:
            rows = await self.pool.fetch(
                "SELECT * FROM energy.procurement_runs ORDER BY created_at DESC LIMIT $1", limit,
            )
        return [dict(r) for r in rows]

    async def get_executive_summary(self, run_uuid: str) -> dict[str, Any] | None:
        """Get the executive summary and cards for a run."""
        run = await self.pool.fetchrow(
            "SELECT uuid, name, executive_summary, total_supply_gap_bpd, total_recommended_bpd, total_cost_estimate_usd, total_risk_score, execution_time_ms, created_at FROM energy.procurement_runs WHERE uuid = $1::uuid",
            run_uuid,
        )
        if not run:
            return None

        cards = await self.pool.fetch(
            "SELECT * FROM energy.executive_recommendations WHERE procurement_run_uuid = $1::uuid AND is_deleted = false ORDER BY created_at",
            run_uuid,
        )

        return {
            "run": dict(run),
            "executive_cards": [normalize_executive_card(dict(c)) for c in cards],
        }

    async def ack_card(self, card_uuid: str, acknowledged_by: str = "user") -> bool:
        """Acknowledge an executive recommendation card."""
        result = await self.pool.execute(
            """UPDATE energy.executive_recommendations
               SET is_acknowledged = TRUE, acknowledged_at = NOW(), acknowledged_by = $2
               WHERE uuid = $1::uuid""",
            card_uuid,
            acknowledged_by,
        )
        return "UPDATE 1" in result

    async def health(self) -> dict[str, Any]:
        """Get procurement system health."""
        run_count = await self.pool.fetchval("SELECT COUNT(*) FROM energy.procurement_runs") or 0
        rec_count = await self.pool.fetchval("SELECT COUNT(*) FROM energy.procurement_recommendations") or 0
        exec_count = await self.pool.fetchval("SELECT COUNT(*) FROM energy.executive_recommendations") or 0
        intel_count = await self.pool.fetchval("SELECT COUNT(*) FROM energy.supplier_intelligence WHERE is_deleted = false") or 0
        compat_count = await self.pool.fetchval("SELECT COUNT(*) FROM energy.refinery_crude_compatibility") or 0
        route_count = await self.pool.fetchval("SELECT COUNT(*) FROM energy.route_costs") or 0

        latest_run = await self.pool.fetchval(
            "SELECT name FROM energy.procurement_runs ORDER BY created_at DESC LIMIT 1",
        )

        return {
            "status": "ok",
            "procurement_runs": run_count,
            "recommendations": rec_count,
            "executive_cards": exec_count,
            "suppliers_with_intel": intel_count,
            "refinery_crude_pairs": compat_count,
            "route_costs": route_count,
            "latest_run": latest_run,
        }
