"""Command Center — the signal→decision golden thread.

Chains the four engines that already exist (disruption signals, digital twin,
SPR optimizer, procurement orchestrator) into a single response pipeline,
invoked in-process rather than HTTP-to-self so the measured latency is the
engines' own compute time. Writes one energy.response_telemetry row per
response — the first writer this table has ever had — so "end-to-end time
from signal to recommendation" is a real, queryable number instead of a
claim.
"""

import json
import statistics
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from db import get_pool
from backend.shared.logging_config import get_logger
from services.digital_twin.engine import SimulationEngine
from services.evidence import EvidenceService
from services.historical_replays import REPLAY_CASES
from services.procurement.orchestrator import ProcurementOrchestrator
from services.procurement.spr_engine import SPREngine
from services.risk_engine import SignalDetector

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


async def _resolve_refinery_target(pool: asyncpg.Pool, refinery_uuid: str | None) -> dict[str, Any] | None:
    """Resolve an explicit operator target without pretending national results
    are refinery-specific. The target is recorded in procurement assumptions and
    evidence; supplier-grade pairing remains conditional on catalog coverage."""
    if not refinery_uuid:
        return None
    refinery = await pool.fetchrow(
        """SELECT r.uuid, r.name, l.name AS country, r.capacity_bpd, r.nelson_complexity_index,
                  r.crude_types_accepted, r.status
           FROM energy.refineries r
           LEFT JOIN energy.locations l ON l.uuid = r.location_id
           WHERE r.uuid = $1::uuid AND r.is_deleted = false""",
        refinery_uuid,
    )
    if refinery is None:
        raise HTTPException(status_code=404, detail="Target refinery not found")
    context = dict(refinery)
    context["uuid"] = str(context["uuid"])
    return context


@router.post("/respond")
async def respond_to_signal(
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Full response pipeline: signal → scenario → digital twin → SPR → procurement.

    Body: {"signal_uuid": "..."} or {"auto": true} (picks the highest-severity
    active signal). Optional "refinery_uuid" records the operator target and
    its known crude constraints; "max_ticks" (default 30) bounds the twin horizon.
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
    refinery_target = await _resolve_refinery_target(pool, body.get("refinery_uuid"))
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
            refinery_target=refinery_target,
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

    evidence = await EvidenceService(pool).create_bundle(
        telemetry_uuid=telemetry_uuid,
        signal=signal,
        scenario=scenario,
        twin=twin,
        spr_run=spr_run,
        procurement_run=procurement_run,
        max_ticks=max_ticks,
        refinery_target=refinery_target,
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
        "evidence_bundle": evidence,
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


@router.get("/evidence/{bundle_uuid}")
async def get_evidence_bundle(
    bundle_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Exportable, reproducible input-and-decision record for one response."""
    bundle = await EvidenceService(pool).get_bundle(bundle_uuid)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    return bundle


@router.post("/evidence/{bundle_uuid}/approval")
async def record_decision_approval(
    bundle_uuid: str,
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Record a human review step; this endpoint never executes a trade."""
    status = body.get("status")
    if status not in {"reviewed", "approved", "executed", "outcome_recorded"}:
        raise HTTPException(status_code=422, detail="status must be reviewed, approved, executed, or outcome_recorded")
    evidence = EvidenceService(pool)
    if await evidence.get_bundle(bundle_uuid) is None:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    actor = str(body.get("actor") or "operator")
    note = body.get("note")
    await evidence.record_approval(bundle_uuid, status, actor, note)
    return {"evidence_bundle_uuid": bundle_uuid, "status": status, "actor": actor, "note": note}


@router.get("/replays")
async def list_historical_replays() -> dict[str, Any]:
    """Available historical cases. Expected effects are directional checks."""
    return {"items": [{"key": key, "name": case["name"], "source_window": case["source_window"], "expected_effects": case["expected_effects"]} for key, case in REPLAY_CASES.items()]}


@router.post("/replays/{case_key}/run")
async def run_historical_replay(
    case_key: str,
    body: dict[str, Any] | None = None,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Run a curated historical case through the live decision engines."""
    case = REPLAY_CASES.get(case_key)
    if case is None:
        raise HTTPException(status_code=404, detail="Unknown replay case")
    signal = await SignalDetector(pool).ingest_signal(case["signal"])
    max_ticks = min(int((body or {}).get("max_ticks", DEFAULT_MAX_TICKS)), 90)
    response = await respond_to_signal({"signal_uuid": str(signal["uuid"]), "max_ticks": max_ticks}, pool)
    evidence = response["evidence_bundle"]
    impacts = response["twin_run"]["aggregate_impacts"]
    measured = {
        "pipeline_latency_seconds": response["telemetry"]["pipeline_latency_seconds"],
        "scenario_name": response["scenario"]["name"],
        "supply_gap_bpd": impacts.get("max_supply_gap_bpd") or impacts.get("supply_gap_bpd") or 0,
        "evidence_mode": evidence["mode"],
        "expected_directional_check": response["scenario"]["name"] == case["expected_effects"]["scenario"],
    }
    replay_uuid = str(uuid_mod.uuid4())
    await pool.execute(
        """INSERT INTO energy.historical_replay_runs
           (uuid, case_key, case_name, source_window, expected_effects, measured_results,
            evidence_bundle_uuid, status, completed_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7::uuid,'completed',NOW())""",
        replay_uuid, case_key, case["name"], json.dumps(case["source_window"]),
        json.dumps(case["expected_effects"]), json.dumps(measured), evidence["uuid"],
    )
    return {"replay_uuid": replay_uuid, "case_key": case_key, "expected_effects": case["expected_effects"], "measured_results": measured, "response": response}


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
