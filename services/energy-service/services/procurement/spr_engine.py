"""SPR Decision Intelligence Engine — release optimization, refill planning, demand modeling, policy engine, executive timeline."""

import json
import math
import time
import uuid
from datetime import date, datetime, timezone
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger

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
    """asyncpg doesn't auto-decode jsonb columns to Python objects (no codec
    registered on this pool), so a jsonb array column comes back as a raw
    JSON string unless explicitly parsed here."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


class SPREngine:
    """Strategic Petroleum Reserve Decision Engine — release optimization, refill, policy, timeline."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def initialize_facilities(self) -> dict[str, Any]:
        """Auto-create SPR facility records from existing strategic_petroleum_reserves."""
        existing = await self.pool.fetch(
            "SELECT slug FROM energy.spr_facilities WHERE is_deleted = false"
        )
        existing_slugs = {r["slug"] for r in existing}

        reserves = await self.pool.fetch(
            """SELECT s.*, l.name as country_name
               FROM energy.strategic_petroleum_reserves s
               LEFT JOIN energy.locations l ON l.uuid = s.location_id
               WHERE s.is_deleted = false"""
        )

        count = 0
        for r in reserves:
            if r["slug"] in existing_slugs:
                # Update existing
                await self.pool.execute(
                    """UPDATE energy.spr_facilities SET
                       storage_capacity_barrels = $2, current_inventory_barrels = $3,
                       max_drawdown_rate_bpd = $4, max_refill_rate_bpd = $5,
                       country = $6, location_id = $7,
                       latitude = $8, longitude = $9,
                       updated_at = NOW()
                       WHERE slug = $1""",
                    r["slug"],
                    r["capacity_barrels"] or 0,
                    r["current_inventory_barrels"] or 0,
                    r["max_drawdown_rate_bpd"] or 0,
                    r["replenishment_rate_bpd"] or 0,
                    r.get("country_name") or "unknown",
                    r["location_id"],
                    r["latitude"],
                    r["longitude"],
                )
                continue

            await self.pool.execute(
                """INSERT INTO energy.spr_facilities
                   (uuid, name, slug, location_id, country, latitude, longitude,
                    storage_capacity_barrels, current_inventory_barrels,
                    max_drawdown_rate_bpd, max_refill_rate_bpd, criticality)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                str(uuid.uuid4()),
                r["name"],
                r["slug"],
                r["location_id"],
                r.get("country_name") or "unknown",
                r["latitude"],
                r["longitude"],
                r["capacity_barrels"] or 0,
                r["current_inventory_barrels"] or 0,
                r["max_drawdown_rate_bpd"] or 0,
                r["replenishment_rate_bpd"] or 0,
                "critical",
            )
            count += 1

        # Record initial inventory snapshot
        facilities = await self.pool.fetch(
            "SELECT uuid, current_inventory_barrels, fill_pct FROM energy.spr_facilities WHERE is_deleted = false"
        )
        for f in facilities:
            await self.pool.execute(
                """INSERT INTO energy.spr_inventory
                   (uuid, facility_uuid, inventory_barrels, fill_pct, source)
                   VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
                str(uuid.uuid4()),
                f["uuid"],
                f["current_inventory_barrels"],
                f["fill_pct"],
                "system_initialize",
            )

        return {"facilities_initialized": count, "total_facilities": len(facilities)}

    async def get_facilities(self) -> list[dict[str, Any]]:
        """Get all SPR facilities with current status."""
        rows = await self.pool.fetch(
            """SELECT f.*,
                      (SELECT inventory_barrels FROM energy.spr_inventory
                       WHERE facility_uuid = f.uuid ORDER BY recorded_at DESC LIMIT 1) as latest_inventory,
                      (SELECT COUNT(*) FROM energy.spr_release_plans rp
                       JOIN energy.spr_release_runs rr ON rr.uuid = rp.release_run_uuid
                       WHERE rp.facility_uuid = f.uuid AND rr.status = 'completed') as total_releases
               FROM energy.spr_facilities f
               WHERE f.is_deleted = false
               ORDER BY f.country, f.name"""
        )
        return [dict(r) for r in rows]

    async def get_inventory_history(self, facility_uuid: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Get inventory time-series data."""
        if facility_uuid:
            rows = await self.pool.fetch(
                "SELECT * FROM energy.spr_inventory WHERE facility_uuid = $1::uuid ORDER BY recorded_at DESC LIMIT $2",
                facility_uuid, limit,
            )
        else:
            rows = await self.pool.fetch(
                "SELECT * FROM energy.spr_inventory ORDER BY recorded_at DESC LIMIT $1", limit,
            )
        return [dict(r) for r in rows]

    async def get_policies(self) -> list[dict[str, Any]]:
        """Get all SPR policies."""
        rows = await self.pool.fetch(
            "SELECT * FROM energy.spr_policy_constraints WHERE is_active = true ORDER BY name"
        )
        return [dict(r) for r in rows]

    async def create_policy(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new SPR policy."""
        puuid = str(uuid.uuid4())
        await self.pool.execute(
            """INSERT INTO energy.spr_policy_constraints
               (uuid, name, description, min_reserve_threshold_pct, max_daily_release_bpd,
                emergency_only, strategic_preservation, economic_optimization,
                critical_infrastructure_first, max_consecutive_release_days,
                min_days_between_releases, refill_trigger_pct, refill_priority)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
            puuid,
            body.get("name"),
            body.get("description", ""),
            body.get("min_reserve_threshold_pct", 20.0),
            body.get("max_daily_release_bpd", 5000000),
            body.get("emergency_only", False),
            body.get("strategic_preservation", False),
            body.get("economic_optimization", True),
            body.get("critical_infrastructure_first", True),
            body.get("max_consecutive_release_days", 90),
            body.get("min_days_between_releases", 30),
            body.get("refill_trigger_pct", 30.0),
            body.get("refill_priority", "balanced"),
        )
        return {"uuid": puuid, "name": body.get("name")}

    # ── Demand Model ──────────────────────────────────────────────────────

    async def compute_demand(self, release_run_uuid: str | None = None) -> dict[str, Any]:
        """Compute national/regional demand from Digital Twin demand profiles."""
        profiles = await self.pool.fetch(
            "SELECT * FROM energy.demand_profiles WHERE is_active = true"
        )
        total_national = 0
        regional = []
        for p in profiles:
            total_national += p["daily_demand_bpd"] or 0
            regional.append({
                "region": p["region"],
                "daily_demand_bpd": p["daily_demand_bpd"] or 0,
                "peak_demand_bpd": p.get("peak_demand_bpd") or p["daily_demand_bpd"] or 0,
            })

        # Get SPR facilities for days-of-supply calculation
        facilities = await self.pool.fetch(
            "SELECT uuid, current_inventory_barrels, max_drawdown_rate_bpd FROM energy.spr_facilities WHERE is_deleted = false AND status != 'depleted'"
        )
        total_inventory = sum(f["current_inventory_barrels"] or 0 for f in facilities)
        total_drawdown = sum(f["max_drawdown_rate_bpd"] or 0 for f in facilities)

        days_supply = total_inventory / total_national if total_national > 0 else 0
        burn_rate = min(total_drawdown, total_national)

        result = {
            "total_national_demand_bpd": total_national,
            "regional_demands": regional,
            "total_spr_inventory": total_inventory,
            "total_drawdown_capacity_bpd": total_drawdown,
            "days_of_supply_remaining": round(days_supply, 1),
            "inventory_burn_rate_bpd": burn_rate,
            "demand_covered_by_spr_pct": round(min(burn_rate / total_national * 100, 100), 1) if total_national > 0 else 0,
        }

        if release_run_uuid:
            for reg in regional:
                await self.pool.execute(
                    """INSERT INTO energy.spr_consumption_forecasts
                       (uuid, release_run_uuid, region, daily_demand_bpd, peak_demand_bpd,
                        emergency_demand_bpd, days_of_supply_remaining, inventory_burn_rate_bpd, source)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                    str(uuid.uuid4()),
                    release_run_uuid,
                    reg["region"],
                    reg["daily_demand_bpd"],
                    reg["peak_demand_bpd"],
                    reg["daily_demand_bpd"] * 1.2,
                    days_supply,
                    burn_rate,
                    "digital_twin",
                )
        return result

    # ── Optimization Engine ──────────────────────────────────────────────

    async def run_optimization(
        self,
        name: str = "SPR Release Analysis",
        description: str = "",
        scenario_uuid: str | None = None,
        simulation_run_uuid: str | None = None,
        procurement_run_uuid: str | None = None,
        disruption_reason: str = "supply_disruption",
        disruption_days: int = 90,
        supply_gap_bpd: float | None = None,
        strategy: str = "balanced",
        policy_name: str = "default",
    ) -> dict[str, Any]:
        """Run a complete SPR optimization and generate recommendations."""
        t0 = time.time()
        run_uuid = str(uuid.uuid4())

        # Get facilities
        # This product is India-first. A global seed catalog is useful for
        # research, but foreign reserves must never be offered as an Indian
        # SPR action in an operational recommendation.
        facilities = await self.pool.fetch(
            """SELECT * FROM energy.spr_facilities
               WHERE is_deleted = false AND status = 'operational' AND country = 'India'"""
        )
        if not facilities:
            raise ValueError("No operational Indian SPR facilities are configured")

        # Get policy
        policy = await self.pool.fetchrow(
            "SELECT * FROM energy.spr_policy_constraints WHERE name = $1 AND is_active = true",
            policy_name,
        )
        if not policy:
            policy = await self.pool.fetchrow(
                "SELECT * FROM energy.spr_policy_constraints WHERE name = 'default' AND is_active = true"
            )

        # Get supply gap from simulation if not provided
        if supply_gap_bpd is None and simulation_run_uuid:
            sim = await self.pool.fetchrow(
                "SELECT aggregate_impacts, supply_gap_bpd FROM energy.digital_twin_runs WHERE uuid = $1::uuid",
                simulation_run_uuid,
            )
            if sim:
                impacts = _ensure_dict(sim.get("aggregate_impacts"))
                supply_gap_bpd = impacts.get("supply_gap_bpd", 0) or sim.get("supply_gap_bpd", 0)
        if supply_gap_bpd is None:
            # Default: 20% of national demand
            demand = await self.compute_demand()
            supply_gap_bpd = demand["total_national_demand_bpd"] * 0.2

        total_capacity = sum(f["storage_capacity_barrels"] or 0 for f in facilities)
        total_inventory = sum(f["current_inventory_barrels"] or 0 for f in facilities)
        total_drawdown = sum(f["max_drawdown_rate_bpd"] or 0 for f in facilities)
        total_refill = sum(f["max_refill_rate_bpd"] or 0 for f in facilities)

        min_threshold = policy["min_reserve_threshold_pct"] / 100.0 if policy else 0.2
        strategic_reserve = total_capacity * min_threshold
        releasable_inventory = max(0, total_inventory - strategic_reserve)

        # ── Drawdown calculation
        daily_draw = min(total_drawdown, supply_gap_bpd)
        days_until_depletion = int(releasable_inventory / daily_draw) if daily_draw > 0 else 999
        max_drawdown_days = min(disruption_days, days_until_depletion)
        total_drawdown_volume = min(releasable_inventory, daily_draw * max_drawdown_days)
        remaining = total_inventory - total_drawdown_volume

        # ── Gap analysis
        uncovered_gap = max(0, supply_gap_bpd - daily_draw)
        coverage_pct = round(min(daily_draw / supply_gap_bpd * 100, 100), 1) if supply_gap_bpd > 0 else 0

        # ── Refill planning
        refill_needed = total_drawdown_volume
        refill_days = int(refill_needed / total_refill) if total_refill > 0 else 999
        replenishment_days = min(refill_days, 365)

        # ── Emergency procurement
        emergency_volume = uncovered_gap * max_drawdown_days
        emergency_cost = emergency_volume * 95.0  # ~$95/bbl emergency premium

        # ── Economic impact
        economic_loss = uncovered_gap * 100 * max_drawdown_days  # $100/bbl economic impact
        economic_savings = total_drawdown_volume * 15.0  # SPR oil cheaper than spot

        # ── Facility selection and release plan
        release_plan = self._optimize_release_plan(
            facilities, releasable_inventory, supply_gap_bpd,
            max_drawdown_days, strategy, policy,
        )

        # ── Decision timeline
        timeline = self._build_decision_timeline(
            release_plan, max_drawdown_days, replenishment_days,
            uncovered_gap, policy,
        )

        # ── Recommendations
        recommendations = self._build_recommendations(
            release_plan, total_drawdown_volume, coverage_pct,
            economic_savings, uncovered_gap, remaining,
            replenishment_days, strategy, policy_name,
        )

        results = {
            "total_capacity_barrels": total_capacity,
            "total_inventory_barrels": total_inventory,
            "strategic_reserve_barrels": strategic_reserve,
            "releasable_inventory_barrels": releasable_inventory,
            "supply_gap_bpd": supply_gap_bpd,
            "daily_draw_bpd": daily_draw,
            "max_drawdown_days": max_drawdown_days,
            "days_until_depletion": days_until_depletion,
            "total_drawdown_volume": total_drawdown_volume,
            "remaining_inventory": remaining,
            "remaining_pct": round(remaining / total_capacity * 100, 1) if total_capacity > 0 else 0,
            "uncovered_gap_bpd": uncovered_gap,
            "coverage_pct": coverage_pct,
            "refill_volume_needed": refill_needed,
            "refill_days_needed": replenishment_days,
            "emergency_purchase_volume": emergency_volume,
            "emergency_purchase_cost": emergency_cost,
            "economic_loss_avoided": economic_savings,
            "remaining_economic_loss": economic_loss,
        }

        # Persist run
        await self.pool.execute(
            """INSERT INTO energy.spr_release_runs
               (uuid, name, description, scenario_uuid, simulation_run_uuid,
                procurement_run_uuid, disruption_reason, disruption_days, supply_gap_bpd,
                total_spr_capacity, total_current_inventory, total_max_drawdown_bpd,
                total_refill_rate_bpd, strategy, policy_name, results,
                decision_timeline, recommendations)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)""",
            run_uuid,
            name,
            description,
            scenario_uuid,
            simulation_run_uuid,
            procurement_run_uuid,
            disruption_reason,
            disruption_days,
            supply_gap_bpd,
            total_capacity,
            total_inventory,
            total_drawdown,
            total_refill,
            strategy,
            policy_name,
            json.dumps(results),
            json.dumps(timeline),
            json.dumps(recommendations),
        )

        # Persist release plans
        for rp in release_plan:
            await self.pool.execute(
                """INSERT INTO energy.spr_release_plans
                   (uuid, release_run_uuid, facility_uuid, release_volume_barrels,
                    release_rate_bpd, start_day, duration_days, priority,
                    target_refinery_uuids, reason, cost_per_barrel, total_cost_usd)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                str(uuid.uuid4()),
                run_uuid,
                rp["facility_uuid"],
                rp["volume"],
                rp["rate"],
                rp["start_day"],
                rp["duration"],
                rp["priority"],
                rp.get("target_refineries", []),
                rp.get("reason", ""),
                rp.get("cost_per_bbl", 0),
                rp["volume"] * rp.get("cost_per_bbl", 0),
            )

        # Persist refill plans
        for rp in release_plan:
            refill_vol = rp["volume"] * 0.8
            refill_dur = max(1, int(refill_vol / total_refill)) if total_refill > 0 else 365
            await self.pool.execute(
                """INSERT INTO energy.spr_refill_plans
                   (uuid, release_run_uuid, facility_uuid, refill_volume_barrels,
                    refill_rate_bpd, start_day, duration_days, estimated_cost_bbl, total_cost_usd)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                str(uuid.uuid4()),
                run_uuid,
                rp["facility_uuid"],
                refill_vol,
                total_refill / max(len(release_plan), 1),
                max_drawdown_days + 1,
                refill_dur,
                80.0,
                refill_vol * 80.0,
            )

        # Persist recommendations
        for rec in recommendations[:5]:
            await self.pool.execute(
                """INSERT INTO energy.spr_recommendations
                   (uuid, release_run_uuid, title, summary, recommendation_type,
                    severity, release_volume_barrels, primary_facility, reason,
                    expected_supply_extension_days, economic_savings_usd, confidence,
                    alternative_strategy, alternative_cost_delta, policy_used,
                    strategy_used, timeline_phase, data_sources)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)""",
                str(uuid.uuid4()),
                run_uuid,
                rec["title"],
                rec["summary"],
                rec.get("type", "release"),
                rec.get("severity", "info"),
                rec.get("volume", 0),
                rec.get("primary_facility"),
                rec.get("reason", ""),
                rec.get("supply_extension_days", 0),
                rec.get("economic_savings", 0),
                rec.get("confidence", 0.7),
                rec.get("alternative_strategy"),
                rec.get("alternative_cost_delta", 0),
                policy_name,
                strategy,
                rec.get("timeline_phase", "immediate"),
                ["spr_engine", "digital_twin", "policy_engine"],
            )

        # Persist timeline events
        for i, tl in enumerate(timeline):
            await self.pool.execute(
                """INSERT INTO energy.spr_decision_timeline
                   (uuid, release_run_uuid, phase, sequence_order, timing_label,
                    action, details, volume_barrels, facility, expected_impact, confidence)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                str(uuid.uuid4()),
                run_uuid,
                tl.get("phase", "immediate"),
                i + 1,
                tl["timing_label"],
                tl["action"],
                tl.get("details", ""),
                tl.get("volume", 0),
                tl.get("facility"),
                tl.get("expected_impact", ""),
                tl.get("confidence", 0.7),
            )

        # Persist cost analysis
        cost_items = [
            ("release_cost", "SPR crude release operational cost", total_drawdown_volume, 5.0),
            ("refill_cost", "SPR crude refill procurement cost", refill_needed, policy.get("refill_trigger_pct", 30) / 100 * 80 if policy else 65),
            ("transport_cost", "Distribution and transport", total_drawdown_volume, 3.0),
            ("emergency_procurement", "Emergency spot market procurement", emergency_volume, 95.0),
            ("economic_impact", "Estimated economic loss from uncovered gap", emergency_volume, 100.0),
        ]
        for cat, desc, vol, ucost in cost_items:
            await self.pool.execute(
                """INSERT INTO energy.spr_cost_analysis
                   (uuid, release_run_uuid, cost_category, description, volume_barrels, unit_cost, total_cost)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()),
                run_uuid,
                cat,
                desc,
                vol,
                ucost,
                vol * ucost,
            )

        # Persist assumptions
        assumptions = [
            ("disruption_days", str(disruption_days)),
            ("supply_gap_bpd", str(supply_gap_bpd)),
            ("strategy", strategy),
            ("policy", policy_name),
            ("min_reserve_threshold_pct", str(policy["min_reserve_threshold_pct"] if policy else 20.0)),
            ("strategic_reserve_barrels", str(strategic_reserve)),
            ("releasable_inventory", str(releasable_inventory)),
            ("total_facilities", str(len(facilities))),
        ]
        for key, val in assumptions:
            await self.pool.execute(
                """INSERT INTO energy.spr_assumptions (uuid, release_run_uuid, assumption_key, assumption_value) VALUES ($1,$2,$3,$4)""",
                str(uuid.uuid4()), run_uuid, key, val,
            )

        elapsed = (time.time() - t0) * 1000
        await self.pool.execute(
            "UPDATE energy.spr_release_runs SET execution_time_ms = $2 WHERE uuid = $1::uuid",
            run_uuid, round(elapsed, 2),
        )

        return {
            "run_uuid": run_uuid,
            "name": name,
            "results": results,
            "recommendations": recommendations,
            "timeline": timeline,
            "execution_time_ms": round(elapsed, 2),
        }

    def _optimize_release_plan(
        self, facilities: list[asyncpg.Record],
        releasable_inventory: float, supply_gap: float,
        max_days: int, strategy: str, policy: asyncpg.Record | None,
    ) -> list[dict[str, Any]]:
        """Generate optimal release plan across facilities."""
        sorted_facilities = sorted(
            [dict(f) for f in facilities],
            key=lambda f: (
                -f.get("reliability_score", 0.95),
                f.get("fill_pct", 100),
                f.get("criticality", "medium") == "critical",
            ),
            reverse=True,
        )

        if strategy == "conservative":
            reserve_factor = 0.5
        elif strategy == "aggressive":
            reserve_factor = 0.1
        elif strategy == "economic":
            reserve_factor = 0.15
        elif strategy == "strategic_preservation":
            reserve_factor = 0.6
        else:
            reserve_factor = 0.3

        # Critical infra first: prioritize facilities near critical refineries
        if strategy == "critical_infrastructure_first":
            sorted_facilities.sort(key=lambda f: f.get("criticality", "medium") == "critical", reverse=True)

        remaining_demand = supply_gap
        plan = []
        total_released = 0
        max_releasable = releasable_inventory * (1 - reserve_factor)

        for f in sorted_facilities:
            if total_released >= max_releasable or remaining_demand <= 0:
                break

            facility_inventory = f.get("current_inventory_barrels") or 0
            facility_drawdown = f.get("max_drawdown_rate_bpd") or 0
            facility_min = facility_inventory * reserve_factor
            facility_available = max(0, facility_inventory - facility_min)

            if facility_available <= 0:
                continue

            daily_from_facility = min(facility_drawdown, remaining_demand)
            days_active = min(max_days, int(facility_available / daily_from_facility)) if daily_from_facility > 0 else 0
            volume = min(facility_available, daily_from_facility * days_active)

            if volume <= 0:
                continue

            priority = 1 if f.get("criticality") in ("critical",) else (3 if f.get("criticality") == "high" else 5)
            cost = 3.0 + (1.0 - f.get("reliability_score", 0.95)) * 10.0

            plan.append({
                "facility_uuid": str(f["uuid"]),
                "facility_name": f["name"],
                "volume": volume,
                "rate": daily_from_facility,
                "start_day": 1,
                "duration": days_active,
                "priority": priority,
                "reason": f"Strategic release from {f['name']} ({f.get('country', 'unknown')})",
                "cost_per_bbl": round(cost, 2),
                "target_refineries": f.get("connected_refinery_uuids") or [],
            })

            total_released += volume
            remaining_demand -= daily_from_facility

        return plan

    def _build_decision_timeline(
        self, release_plan: list[dict[str, Any]],
        drawdown_days: int, refill_days: int,
        uncovered_gap: float, policy: asyncpg.Record | None,
    ) -> list[dict[str, Any]]:
        """Build executive decision timeline."""
        timeline = []
        total_volume = sum(rp["volume"] for rp in release_plan)
        primary = release_plan[0] if release_plan else None

        # Immediate (Now)
        if primary:
            timeline.append({
                "phase": "immediate",
                "timing_label": "Now",
                "action": f"Release {total_volume:,.0f} barrels from SPR facilities",
                "details": f"Primary: {primary['facility_name']} ({primary['volume']:,.0f} bbl at {primary['rate']:,.0f} bpd)",
                "volume": total_volume,
                "facility": primary["facility_name"],
                "expected_impact": f"Covers {drawdown_days} days of supply disruption",
                "confidence": 0.92,
            })
        else:
            timeline.append({
                "phase": "immediate", "timing_label": "Now",
                "action": "No SPR release recommended at this time",
                "details": "Sufficient commercial inventory or low disruption severity",
                "volume": 0, "facility": None,
                "expected_impact": "Preserve strategic reserves",
                "confidence": 0.85,
            })

        # +24 hours
        if uncovered_gap > 0:
            timeline.append({
                "phase": "short_term",
                "timing_label": "+24 hours",
                "action": f"Initiate emergency procurement for {uncovered_gap:,.0f} bpd uncovered gap",
                "details": "Contact alternative suppliers, activate spot market purchases",
                "volume": uncovered_gap * 30,
                "facility": None,
                "expected_impact": "Reduce supply shortfall",
                "confidence": 0.75,
            })

        # +72 hours
        timeline.append({
            "phase": "short_term",
            "timing_label": "+72 hours",
            "action": "Re-route shipping through alternative corridors",
            "details": "Divert cargoes via Cape of Good Hope or alternative routes",
            "volume": 0,
            "facility": None,
            "expected_impact": "Restore supply chain flow",
            "confidence": 0.65,
        })

        # +7 days
        timeline.append({
            "phase": "medium_term",
            "timing_label": "+7 days",
            "action": "Begin phased SPR replenishment planning",
            "details": f"Target refill of {total_volume:,.0f} barrels over {refill_days} days",
            "volume": total_volume,
            "facility": None,
            "expected_impact": f"Restore reserves in {refill_days} days",
            "confidence": 0.7,
        })

        # +30 days
        timeline.append({
            "phase": "long_term",
            "timing_label": "+30 days",
            "action": "Initiate strategic reserve refill program",
            "details": f"Scheduled procurement of {total_volume:,.0f} barrels at estimated ${80:.0f}/bbl",
            "volume": total_volume,
            "facility": None,
            "expected_impact": "Full reserve restoration within 12 months",
            "confidence": 0.6,
        })

        return timeline

    def _build_recommendations(
        self, release_plan: list[dict[str, Any]],
        total_volume: float, coverage_pct: float,
        economic_savings: float, uncovered_gap: float,
        remaining_inventory: float, refill_days: int,
        strategy: str, policy_name: str,
    ) -> list[dict[str, Any]]:
        """Build executive recommendations."""
        recs = []
        primary = release_plan[0] if release_plan else None

        if primary:
            supply_ext = primary["duration"] if "duration" in primary else 30
            alt_cost = uncovered_gap * 95 * 30 * 12 if uncovered_gap > 0 else 0
            recs.append({
                "type": "release",
                "severity": "critical" if coverage_pct < 50 else "warning",
                "title": f"SPR Release: {total_volume:,.0f} barrels from {len(release_plan)} facilities",
                "summary": (
                    f"Release {total_volume:,.0f} barrels from strategic reserves to cover {coverage_pct}% "
                    f"of supply disruption. Primary facility: {primary['facility_name']}. "
                    f"Coverage: {supply_ext} days. Economic savings: ${economic_savings:,.0f}."
                ),
                "volume": total_volume,
                "primary_facility": primary["facility_name"],
                "reason": f"Strategic release under {strategy} policy to mitigate supply disruption",
                "supply_extension_days": supply_ext,
                "economic_savings": economic_savings,
                "confidence": round(0.7 + coverage_pct / 500, 2),
                "alternative_strategy": "Increase procurement instead of SPR release",
                "alternative_cost_delta": alt_cost,
                "timeline_phase": "immediate",
            })

        if uncovered_gap > 0:
            recs.append({
                "type": "procurement",
                "severity": "warning",
                "title": f"Residual Gap: {uncovered_gap:,.0f} bpd requires procurement",
                "summary": (
                    f"SPR coverage leaves {uncovered_gap:,.0f} bpd ({100 - coverage_pct:.1f}%) uncovered. "
                    f"Recommended: emergency procurement or demand-side measures."
                ),
                "volume": uncovered_gap * 30,
                "reason": "SPR capacity insufficient to cover full disruption",
                "supply_extension_days": 0,
                "economic_savings": 0,
                "confidence": 0.8,
                "alternative_strategy": "Demand rationing and fuel switching",
                "alternative_cost_delta": uncovered_gap * 100 * 90,
                "timeline_phase": "short_term",
            })

        recs.append({
            "type": "refill",
            "severity": "info",
            "title": f"SPR Refill Plan: {total_volume:,.0f} barrels over {refill_days} days",
            "summary": (
                f"Initiate phased refill of strategic reserves. Total volume: {total_volume:,.0f} barrels. "
                f"Estimated duration: {refill_days} days. Remaining inventory post-release: "
                f"{remaining_inventory:,.0f} barrels."
            ),
            "volume": total_volume,
            "reason": "Strategic reserve restoration",
            "supply_extension_days": 0,
            "economic_savings": 0,
            "confidence": 0.65,
            "alternative_strategy": "Accelerated refill at premium prices",
            "alternative_cost_delta": total_volume * 15,
            "timeline_phase": "medium_term",
        })

        recs.append({
            "type": "policy",
            "severity": "info",
            "title": f"Policy Assessment: {policy_name.replace('_', ' ').title()} Strategy",
            "summary": (
                f"Under {strategy} strategy with '{policy_name}' policy, SPR covers {coverage_pct}% of disruption. "
                f"Strategic reserve threshold preserved. Recommend review of policy settings for optimal balance."
            ),
            "volume": 0,
            "reason": "Policy evaluation",
            "supply_extension_days": 0,
            "economic_savings": 0,
            "confidence": 0.9,
            "alternative_strategy": "Switch to aggressive policy for higher coverage",
            "alternative_cost_delta": 0,
            "timeline_phase": "long_term",
        })

        return recs

    # ── Query Methods ─────────────────────────────────────────────────────

    async def get_run(self, run_uuid: str) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM energy.spr_release_runs WHERE uuid = $1::uuid", run_uuid,
        )
        if not row:
            return None
        result = dict(row)
        result["results"] = _ensure_dict(result.get("results"))
        result["recommendations"] = _ensure_list(result.get("recommendations"))
        result["decision_timeline"] = _ensure_list(result.get("decision_timeline"))

        plans = await self.pool.fetch(
            "SELECT * FROM energy.spr_release_plans WHERE release_run_uuid = $1::uuid ORDER BY facility_uuid",
            run_uuid,
        )
        result["release_plans"] = [dict(r) for r in plans]

        refills = await self.pool.fetch(
            "SELECT * FROM energy.spr_refill_plans WHERE release_run_uuid = $1::uuid ORDER BY facility_uuid",
            run_uuid,
        )
        result["refill_plans"] = [dict(r) for r in refills]

        recs = await self.pool.fetch(
            "SELECT * FROM energy.spr_recommendations WHERE release_run_uuid = $1::uuid ORDER BY created_at",
            run_uuid,
        )
        result["recommendations_list"] = [dict(r) for r in recs]

        timeline = await self.pool.fetch(
            "SELECT * FROM energy.spr_decision_timeline WHERE release_run_uuid = $1::uuid ORDER BY sequence_order",
            run_uuid,
        )
        result["timeline_entries"] = [dict(r) for r in timeline]

        costs = await self.pool.fetch(
            "SELECT * FROM energy.spr_cost_analysis WHERE release_run_uuid = $1::uuid ORDER BY cost_category",
            run_uuid,
        )
        result["cost_analysis"] = [dict(r) for r in costs]

        return result

    async def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT uuid, name, status, strategy, policy_name, disruption_reason, disruption_days, supply_gap_bpd, execution_time_ms, created_at FROM energy.spr_release_runs ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return [dict(r) for r in rows]

    async def health(self) -> dict[str, Any]:
        facilities = await self.pool.fetchval("SELECT COUNT(*) FROM energy.spr_facilities WHERE is_deleted = false") or 0
        total_capacity = await self.pool.fetchval("SELECT COALESCE(SUM(storage_capacity_barrels), 0) FROM energy.spr_facilities WHERE is_deleted = false") or 0
        total_inventory = await self.pool.fetchval("SELECT COALESCE(SUM(current_inventory_barrels), 0) FROM energy.spr_facilities WHERE is_deleted = false") or 0
        runs = await self.pool.fetchval("SELECT COUNT(*) FROM energy.spr_release_runs") or 0
        recs = await self.pool.fetchval("SELECT COUNT(*) FROM energy.spr_recommendations") or 0
        policies = await self.pool.fetchval("SELECT COUNT(*) FROM energy.spr_policy_constraints WHERE is_active = true") or 0

        fill_pct = round(total_inventory / total_capacity * 100, 1) if total_capacity > 0 else 0
        latest_run = await self.pool.fetchval("SELECT name FROM energy.spr_release_runs ORDER BY created_at DESC LIMIT 1")

        return {
            "status": "ok",
            "spr_facilities": facilities,
            "total_capacity_barrels": total_capacity,
            "total_inventory_barrels": total_inventory,
            "overall_fill_pct": fill_pct,
            "optimization_runs": runs,
            "recommendations": recs,
            "active_policies": policies,
            "latest_run": latest_run,
        }
