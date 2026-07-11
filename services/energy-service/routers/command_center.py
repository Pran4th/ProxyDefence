"""Command Center — the signal→decision golden thread.

Chains the four engines that already exist (disruption signals, digital twin,
SPR optimizer, procurement orchestrator) into a single response pipeline,
invoked in-process rather than HTTP-to-self so the measured latency is the
engines' own compute time. Writes one energy.response_telemetry row per
response — the first writer this table has ever had — so "end-to-end time
from signal to recommendation" is a real, queryable number instead of a
claim.
"""

import statistics
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from db import get_pool
from backend.shared.logging_config import get_logger
from services.digital_twin.engine import SimulationEngine
from services.procurement.orchestrator import ProcurementOrchestrator
from services.procurement.spr_engine import SPREngine

logger = get_logger(__name__)

# Nested under /intelligence so the modular-api gateway's existing intel proxy
# (backend/api/energy/router.py) forwards it with JWT auth, zero gateway changes.
router = APIRouter(prefix="/api/v1/intelligence/command", tags=["Command Center"])

# Keyword → scenario-template name (energy.simulation_scenarios.is_template=true).
# Ordered: first match wins, most specific phrases first.
SCENARIO_KEYWORD_MAP: list[tuple[tuple[str, ...], str]] = [
    (("hormuz",), "Strait of Hormuz Partial Closure"),
    (("red sea", "houthi", "bab el-mandeb", "bab al-mandab", "suez"), "Red Sea Shipping Disruption"),
    (("jamnagar", "refinery fire", "refinery blaze"), "Refinery Fire — Jamnagar"),
    (("cyclone", "gujarat"), "Gujarat Cyclone"),
    (("opec",), "OPEC Coordinated Production Cut"),
    (("russia", "russian"), "Russian Export Ban"),
    (("grid", "blackout", "power outage"), "Power Grid Failure"),
]
FALLBACK_SCENARIO = "India Supply Chain Stress Test"

DEFAULT_MAX_TICKS = 30  # 30-day horizon keeps the pipeline responsive

# signal risk_dimension → energy.spr_release_reason enum value
SPR_REASON_BY_DIMENSION = {
    "geopolitical": "conflict",
    "operational": "supply_disruption",
    "economic": "price_stabilization",
    "environmental": "natural_disaster",
}


def _signal_text(signal: asyncpg.Record) -> str:
    parts = [signal["title"] or "", signal["description"] or ""]
    parts.extend(signal["affected_regions"] or [])
    parts.extend(signal["affected_commodities"] or [])
    return " ".join(parts).lower()


async def _match_scenario(pool: asyncpg.Pool, signal: asyncpg.Record) -> asyncpg.Record:
    """Map a live signal to the most relevant scenario template by keyword,
    falling back to the India-wide stress test when nothing specific matches."""
    text = _signal_text(signal)
    matched_name = FALLBACK_SCENARIO
    for keywords, scenario_name in SCENARIO_KEYWORD_MAP:
        if any(kw in text for kw in keywords):
            matched_name = scenario_name
            break

    row = await pool.fetchrow(
        """SELECT * FROM energy.simulation_scenarios
           WHERE name = $1 AND is_template = true LIMIT 1""",
        matched_name,
    )
    if row is None and matched_name != FALLBACK_SCENARIO:
        row = await pool.fetchrow(
            """SELECT * FROM energy.simulation_scenarios
               WHERE name = $1 AND is_template = true LIMIT 1""",
            FALLBACK_SCENARIO,
        )
    if row is None:
        # Last resort: any template, so the pipeline degrades rather than 500s
        row = await pool.fetchrow(
            "SELECT * FROM energy.simulation_scenarios WHERE is_template = true ORDER BY id LIMIT 1"
        )
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="No scenario templates seeded — run digital-twin bootstrap first",
        )
    return row


async def _pick_auto_signal(pool: asyncpg.Pool) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """SELECT * FROM energy.disruption_signals
           WHERE expires_at > NOW()
           ORDER BY CASE severity
                        WHEN 'critical' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'elevated' THEN 2
                        WHEN 'moderate' THEN 1
                        ELSE 0
                    END DESC,
                    confidence DESC, created_at DESC
           LIMIT 1"""
    )


@router.post("/respond")
async def respond_to_signal(
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Full response pipeline: signal → scenario → digital twin → SPR → procurement.

    Body: {"signal_uuid": "..."} or {"auto": true} (picks the highest-severity
    active signal). Optional "max_ticks" (default 30) bounds the twin horizon.
    """
    # ── Stage 0: resolve the signal ──────────────────────────────────────
    if body.get("signal_uuid"):
        signal = await pool.fetchrow(
            "SELECT * FROM energy.disruption_signals WHERE uuid = $1::uuid",
            body["signal_uuid"],
        )
        if signal is None:
            raise HTTPException(status_code=404, detail="Signal not found")
    elif body.get("auto"):
        signal = await _pick_auto_signal(pool)
        if signal is None:
            raise HTTPException(status_code=404, detail="No active signals to respond to")
    else:
        raise HTTPException(status_code=422, detail="Provide signal_uuid or auto=true")

    max_ticks = min(int(body.get("max_ticks", DEFAULT_MAX_TICKS)), 90)
    telemetry_uuid = str(uuid_mod.uuid4())
    signal_detected_at = signal["created_at"]
    analysis_started_at = datetime.now(timezone.utc)

    await pool.execute(
        """INSERT INTO energy.response_telemetry
           (uuid, signal_id, signal_type, signal_detected_at, analysis_started_at)
           VALUES ($1, $2::uuid, $3, $4, $5)""",
        telemetry_uuid, str(signal["uuid"]),
        (signal["risk_dimension"] or "operational")[:50],
        signal_detected_at, analysis_started_at,
    )

    stage = "scenario_match"
    try:
        # ── Stage 1: scenario match ──────────────────────────────────────
        scenario = await _match_scenario(pool, signal)

        # ── Stage 2: digital twin ────────────────────────────────────────
        stage = "digital_twin"
        engine = SimulationEngine(pool)
        twin = await engine.run_simulation(
            scenario_id=scenario["id"],
            name=f"Response: {(signal['title'] or 'signal')[:80]}",
            description=f"Auto-response to signal {signal['uuid']}",
            max_ticks=max_ticks,
        )
        analysis_completed_at = datetime.now(timezone.utc)

        impacts = twin.get("aggregate_impacts") or {}
        supply_gap_bpd = float(
            impacts.get("max_supply_gap_bpd") or impacts.get("supply_gap_bpd") or 0
        )

        # ── Stage 3: SPR optimization ────────────────────────────────────
        stage = "spr"
        spr = SPREngine(pool)
        spr_run = await spr.run_optimization(
            name=f"SPR response: {(signal['title'] or 'signal')[:60]}",
            description=f"Triggered by signal {signal['uuid']}",
            simulation_run_uuid=twin["run_uuid"],
            disruption_reason=SPR_REASON_BY_DIMENSION.get(
                signal["risk_dimension"], "supply_disruption"
            ),
            disruption_days=max_ticks,
            supply_gap_bpd=supply_gap_bpd or None,
            strategy=body.get("strategy", "balanced"),
        )

        # ── Stage 4: procurement orchestration ───────────────────────────
        stage = "procurement"
        orchestrator = ProcurementOrchestrator(pool)
        procurement_run = await orchestrator.run_procurement(
            simulation_run_uuid=twin["run_uuid"],
            name=f"Procurement response: {(signal['title'] or 'signal')[:60]}",
            description=f"Triggered by signal {signal['uuid']}",
            supply_gap_bpd=supply_gap_bpd or None,
            optimization_goal=body.get("optimization_goal", "balanced"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("command_respond_failed", stage=stage, signal=str(signal["uuid"]), error=str(exc))
        raise HTTPException(status_code=502, detail=f"Response pipeline failed at stage '{stage}': {exc}")

    recommendation_generated_at = datetime.now(timezone.utc)
    total_latency = int((recommendation_generated_at - signal_detected_at).total_seconds())
    pipeline_latency = round(
        (recommendation_generated_at - analysis_started_at).total_seconds(), 2
    )

    await pool.execute(
        """UPDATE energy.response_telemetry
           SET analysis_completed_at = $2,
               recommendation_generated_at = $3,
               total_latency_seconds = $4
           WHERE uuid = $1""",
        telemetry_uuid, analysis_completed_at,
        recommendation_generated_at, total_latency,
    )

    return {
        "signal": dict(signal),
        "scenario": {
            "uuid": str(scenario["uuid"]),
            "name": scenario["name"],
            "severity": scenario["severity"],
        },
        "twin_run": {
            "run_uuid": twin["run_uuid"],
            "ticks_executed": twin["ticks_executed"],
            "execution_time_ms": twin["execution_time_ms"],
            "aggregate_impacts": impacts,
        },
        "spr_run": spr_run,
        "procurement_run": procurement_run,
        "telemetry": {
            "uuid": telemetry_uuid,
            "signal_detected_at": signal_detected_at.isoformat(),
            "analysis_started_at": analysis_started_at.isoformat(),
            "analysis_completed_at": analysis_completed_at.isoformat(),
            "recommendation_generated_at": recommendation_generated_at.isoformat(),
            "total_latency_seconds": total_latency,
            "pipeline_latency_seconds": pipeline_latency,
        },
    }


@router.get("/telemetry")
async def get_response_telemetry(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Recent response telemetry plus latency percentiles — the evidence
    behind the signal→recommendation response-time claim."""
    rows = await pool.fetch(
        """SELECT rt.*, ds.title AS signal_title, ds.severity AS signal_severity
           FROM energy.response_telemetry rt
           LEFT JOIN energy.disruption_signals ds ON ds.uuid = rt.signal_id
           WHERE rt.recommendation_generated_at IS NOT NULL
           ORDER BY rt.created_at DESC LIMIT 50"""
    )

    pipeline_latencies = [
        (r["recommendation_generated_at"] - r["analysis_started_at"]).total_seconds()
        for r in rows
        if r["analysis_started_at"] and r["recommendation_generated_at"]
    ]

    def _pct(vals: list[float], q: float) -> float | None:
        if not vals:
            return None
        if len(vals) == 1:
            return round(vals[0], 2)
        return round(statistics.quantiles(vals, n=100)[int(q) - 1], 2)

    return {
        "items": [dict(r) for r in rows],
        "total": len(rows),
        "pipeline_latency_p50_seconds": _pct(pipeline_latencies, 50),
        "pipeline_latency_p95_seconds": _pct(pipeline_latencies, 95),
    }
